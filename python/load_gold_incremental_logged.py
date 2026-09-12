from __future__ import annotations

import argparse
import sys
from datetime import date

import load_gold_incremental as incremental
import load_gold_to_azure_sql as base

from etl_logging import (
    log_failure,
    log_start,
    log_success,
)


PIPELINE_NAME = "gold_zone_hourly_incremental_logged"
STAGE_NAME = "INCREMENTAL_GOLD_MONTH"


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Phase 18 logging-enabled incremental Gold loader."
        )
    )

    parser.add_argument("--server", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--user", required=True)

    parser.add_argument(
        "--year",
        type=int,
        default=2025,
    )

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

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=5000,
    )

    return parser.parse_args()


def run_logged_month(
    conn,
    *,
    year: int,
    month: int,
    chunk_size: int,
):
    processing_month = date(
        year,
        month,
        1,
    )

    source = (
        "data/gold/zone_hourly/"
        f"year={year}/month={month:02d}"
    )

    run_id = log_start(
        conn,
        pipeline_name=PIPELINE_NAME,
        source=source,
        processing_month=processing_month,
        stage=STAGE_NAME,
    )

    print(
        f"\nETL log STARTED: {run_id}"
    )

    try:
        result = incremental.process_month(
            conn,
            year=year,
            month=month,
            chunk_size=chunk_size,
        )

        if result == "PROCESSED":
            rows_processed = (
                base.expected_month_rows(
                    year,
                    month,
                )
            )
        else:
            # A registry/idempotency skip means this
            # execution did not process warehouse rows.
            rows_processed = 0

        log_success(
            conn,
            run_id=run_id,
            rows_processed=rows_processed,
            rows_valid=rows_processed,
            rows_rejected=0,
            quarantine_rows=0,
        )

        print(
            "ETL formal log: SUCCESS"
        )

        return result

    except Exception as exc:

        try:
            log_failure(
                conn,
                run_id=run_id,
                error_message=str(exc),
            )

            print(
                "ETL formal log: FAILED"
            )

        except Exception as logging_error:
            print(
                "WARNING: unable to write failure log:",
                logging_error,
                file=sys.stderr,
            )

        raise


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

        processed = 0
        skipped = 0

        for month in range(
            args.start_month,
            args.end_month + 1,
        ):
            result = run_logged_month(
                conn,
                year=args.year,
                month=month,
                chunk_size=args.chunk_size,
            )

            if result == "PROCESSED":
                processed += 1
            else:
                skipped += 1

        print("\n===== LOGGED RUN SUMMARY =====")
        print("Processed:", processed)
        print("Skipped  :", skipped)
        print("Status   : SUCCESS")

    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        print(
            "\nLogged incremental run cancelled.",
            file=sys.stderr,
        )
        sys.exit(130)

    except Exception as exc:
        print(
            f"\nERROR: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
