from __future__ import annotations

import argparse
import sys

import load_gold_to_azure_sql as base


PIPELINE_NAME = "gold_zone_hourly_incremental_to_azure_sql"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Phase 19 Azure SQL post-load validation."
    )

    parser.add_argument("--server", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--year", type=int, default=2025)

    parser.add_argument(
        "--start-month",
        type=int,
        required=True,
        choices=range(1, 13),
    )

    parser.add_argument(
        "--end-month",
        type=int,
        required=True,
        choices=range(1, 13),
    )

    return parser.parse_args()


def scalar(cursor, query, params=()):
    cursor.execute(query, params)
    return cursor.fetchone()[0]


def main():
    args = parse_args()

    if args.start_month > args.end_month:
        raise ValueError(
            "--start-month cannot exceed --end-month."
        )

    conn = None

    try:
        conn = base.connect(
            args.server,
            args.database,
            args.user,
        )

        base.test_connection(conn)

        cursor = conn.cursor()

        failures = []

        # -------------------------------------------------
        # 1. No incomplete incremental registrations
        # -------------------------------------------------
        incomplete_files = scalar(
            cursor,
            """
            SELECT COUNT(*)
            FROM etl.ProcessedFileRegistry
            WHERE pipeline_name = ?
              AND status <> 'SUCCESS';
            """,
            (PIPELINE_NAME,),
        )

        print(
            "Incomplete processed-file registrations:",
            incomplete_files,
        )

        if incomplete_files != 0:
            failures.append(
                f"{incomplete_files} incomplete file registration(s)"
            )

        # -------------------------------------------------
        # 2. Requested month registrations must exist
        # -------------------------------------------------
        for month in range(
            args.start_month,
            args.end_month + 1,
        ):
            partition_pattern = (
                f"%year={args.year}/month={month:02d}%"
            )

            success_count = scalar(
                cursor,
                """
                SELECT COUNT(*)
                FROM etl.ProcessedFileRegistry
                WHERE pipeline_name = ?
                  AND status = 'SUCCESS'
                  AND source_partition LIKE ?;
                """,
                (
                    PIPELINE_NAME,
                    partition_pattern,
                ),
            )

            print(
                f"{args.year}-{month:02d} SUCCESS registration:",
                success_count,
            )

            if success_count < 1:
                failures.append(
                    f"Missing SUCCESS registry entry for "
                    f"{args.year}-{month:02d}"
                )

        # -------------------------------------------------
        # 3. Gold fact business-grain uniqueness
        # -------------------------------------------------
        cursor.execute(
            """
            SELECT
                COUNT_BIG(*) AS fact_rows,
                COUNT_BIG(
                    DISTINCT CONCAT(
                        date_key, ':',
                        time_key, ':',
                        zone_key
                    )
                ) AS distinct_grain_rows
            FROM dw.FactZoneHourlyActivity;
            """
        )

        fact_rows, distinct_rows = cursor.fetchone()

        print("Fact rows          :", fact_rows)
        print("Distinct grain rows:", distinct_rows)

        if fact_rows != distinct_rows:
            failures.append(
                "FactZoneHourlyActivity contains "
                "duplicate business-grain rows"
            )

        # -------------------------------------------------
        # 4. ETL reconciliation integrity
        # -------------------------------------------------
        reconciliation_violations = scalar(
            cursor,
            """
            SELECT COUNT(*)
            FROM audit.ETLRunLog
            WHERE status = 'SUCCESS'
              AND
              (
                     rows_processed IS NULL
                  OR rows_valid IS NULL
                  OR rows_rejected IS NULL
                  OR quarantine_rows IS NULL
                  OR rows_processed <>
                     rows_valid + rows_rejected
                  OR rows_rejected <>
                     quarantine_rows
              );
            """,
        )

        print(
            "ETL reconciliation violations:",
            reconciliation_violations,
        )

        if reconciliation_violations != 0:
            failures.append(
                f"{reconciliation_violations} ETL "
                "reconciliation violation(s)"
            )

        # -------------------------------------------------
        # 5. Completed ETL runs require end_time
        # -------------------------------------------------
        missing_end_times = scalar(
            cursor,
            """
            SELECT COUNT(*)
            FROM audit.ETLRunLog
            WHERE status IN ('SUCCESS', 'FAILED')
              AND end_time IS NULL;
            """,
        )

        print(
            "Completed runs missing end_time:",
            missing_end_times,
        )

        if missing_end_times != 0:
            failures.append(
                f"{missing_end_times} completed run(s) "
                "missing end_time"
            )

        # -------------------------------------------------
        # 6. No stale STARTED executions
        # -------------------------------------------------
        stale_started = scalar(
            cursor,
            """
            SELECT COUNT(*)
            FROM audit.ETLRunLog
            WHERE status = 'STARTED';
            """,
        )

        print("Stale STARTED executions:", stale_started)

        if stale_started != 0:
            failures.append(
                f"{stale_started} stale STARTED execution(s)"
            )

        print()
        print("=" * 60)

        if failures:
            print("PHASE 19 POST-LOAD VALIDATION: FAILED")

            for failure in failures:
                print(" -", failure)

            raise RuntimeError(
                "Warehouse post-load validation failed."
            )

        print("PHASE 19 POST-LOAD VALIDATION: SUCCESS")
        print("=" * 60)

    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"\nERROR: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
