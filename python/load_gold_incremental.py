from __future__ import annotations

import argparse
import calendar
import sys
import uuid
from datetime import datetime
from pathlib import Path

import load_gold_to_azure_sql as base


PROJECT_ROOT = Path(__file__).resolve().parents[1]

PIPELINE_NAME = "gold_zone_hourly_incremental_to_azure_sql"
SOURCE_ENTITY = "gold_zone_hourly"
TARGET_SCHEMA = "dw"
TARGET_TABLE = "FactZoneHourlyActivity"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Phase 16 incremental Gold loader."
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


def source_metadata(year: int, month: int):
    source_file = base.find_month_file(
        year,
        month,
    )

    relative_source = str(
        source_file.relative_to(PROJECT_ROOT)
    ).replace("\\", "/")

    partition = (
        f"year={year}/month={month:02d}"
    )

    file_hash = base.sha256_file(
        source_file
    )

    file_size = source_file.stat().st_size

    return (
        source_file,
        relative_source,
        partition,
        file_hash,
        file_size,
    )


def ensure_registry_row(
    conn,
    *,
    relative_source: str,
    partition: str,
    file_hash: str,
    file_size: int,
):
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            processed_file_id,
            status,
            load_batch_id
        FROM etl.ProcessedFileRegistry
        WHERE
            pipeline_name = ?
            AND source_file = ?
            AND file_sha256 = ?;
        """,
        PIPELINE_NAME,
        relative_source,
        file_hash,
    )

    row = cursor.fetchone()

    if row:
        return (
            row.processed_file_id,
            row.status,
            row.load_batch_id,
        )

    cursor.execute(
        """
        INSERT INTO etl.ProcessedFileRegistry
        (
            pipeline_name,
            source_entity,
            source_partition,
            source_file,
            file_sha256,
            file_size_bytes,
            status
        )
        OUTPUT INSERTED.processed_file_id
        VALUES
        (
            ?, ?, ?, ?, ?, ?, 'DISCOVERED'
        );
        """,
        PIPELINE_NAME,
        SOURCE_ENTITY,
        partition,
        relative_source,
        file_hash,
        file_size,
    )

    processed_file_id = cursor.fetchone()[0]

    conn.commit()

    return (
        processed_file_id,
        "DISCOVERED",
        None,
    )


def prepare_batch(
    conn,
    *,
    year: int,
    month: int,
    relative_source: str,
    partition: str,
    file_hash: str,
):
    idempotency_key = (
        f"phase16_incremental|"
        f"{partition}|"
        f"sha256={file_hash}"
    )

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            load_batch_id,
            status
        FROM audit.LoadBatch
        WHERE idempotency_key = ?;
        """,
        idempotency_key,
    )

    existing = cursor.fetchone()

    if existing:
        batch_id = existing.load_batch_id

        if existing.status == "SUCCESS":
            return batch_id, True

        cursor.execute(
            """
            DELETE FROM etl.StageZoneHourlyActivity
            WHERE load_batch_id = ?;
            """,
            batch_id,
        )

        cursor.execute(
            """
            UPDATE audit.LoadBatch
            SET
                status = 'STARTED',
                started_at = SYSUTCDATETIME(),
                completed_at = NULL,
                rows_read = NULL,
                rows_inserted = NULL,
                rows_updated = NULL,
                rows_rejected = NULL,
                error_message = NULL
            WHERE load_batch_id = ?;
            """,
            batch_id,
        )

        conn.commit()

        return batch_id, False

    batch_id = uuid.uuid4()

    cursor.execute(
        """
        INSERT INTO audit.LoadBatch
        (
            load_batch_id,
            pipeline_name,
            source_system,
            source_object,
            source_partition,
            target_schema,
            target_table,
            idempotency_key,
            load_type,
            status
        )
        VALUES
        (
            ?, ?, ?, ?, ?, ?, ?, ?, 'INCREMENTAL', 'STARTED'
        );
        """,
        batch_id,
        PIPELINE_NAME,
        "local_gold_parquet",
        relative_source,
        partition,
        TARGET_SCHEMA,
        TARGET_TABLE,
        idempotency_key,
    )

    conn.commit()

    return batch_id, False


def mark_processing(
    conn,
    processed_file_id: int,
    batch_id,
):
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE etl.ProcessedFileRegistry
        SET
            status = 'PROCESSING',
            load_batch_id = ?,
            processing_started_at = SYSUTCDATETIME(),
            processed_at = NULL,
            last_error = NULL
        WHERE processed_file_id = ?;
        """,
        batch_id,
        processed_file_id,
    )

    conn.commit()


def advance_watermark(
    conn,
    *,
    year: int,
    month: int,
    batch_id,
):
    last_day = calendar.monthrange(
        year,
        month,
    )[1]

    watermark = datetime(
        year,
        month,
        last_day,
        23,
        59,
        59,
        999000,
    )

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            last_successful_watermark
        FROM etl.LoadWatermark
        WHERE
            pipeline_name = ?
            AND source_entity = ?;
        """,
        PIPELINE_NAME,
        SOURCE_ENTITY,
    )

    existing = cursor.fetchone()

    if existing is None:
        cursor.execute(
            """
            INSERT INTO etl.LoadWatermark
            (
                pipeline_name,
                source_entity,
                last_successful_watermark,
                last_successful_run_id,
                updated_at
            )
            VALUES
            (
                ?, ?, ?, ?, SYSUTCDATETIME()
            );
            """,
            PIPELINE_NAME,
            SOURCE_ENTITY,
            watermark,
            batch_id,
        )

    elif (
        existing.last_successful_watermark is None
        or watermark >
        existing.last_successful_watermark
    ):
        cursor.execute(
            """
            UPDATE etl.LoadWatermark
            SET
                last_successful_watermark = ?,
                last_successful_run_id = ?,
                updated_at = SYSUTCDATETIME()
            WHERE
                pipeline_name = ?
                AND source_entity = ?;
            """,
            watermark,
            batch_id,
            PIPELINE_NAME,
            SOURCE_ENTITY,
        )

    conn.commit()


def mark_success(
    conn,
    *,
    processed_file_id: int,
    batch_id,
    year: int,
    month: int,
):
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE etl.ProcessedFileRegistry
        SET
            status = 'SUCCESS',
            load_batch_id = ?,
            processed_at = SYSUTCDATETIME(),
            last_error = NULL
        WHERE processed_file_id = ?;
        """,
        batch_id,
        processed_file_id,
    )

    conn.commit()

    advance_watermark(
        conn,
        year=year,
        month=month,
        batch_id=batch_id,
    )


def mark_failed(
    conn,
    *,
    processed_file_id: int,
    batch_id,
    error: Exception,
):
    conn.rollback()

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE etl.ProcessedFileRegistry
        SET
            status = 'FAILED',
            load_batch_id = ?,
            processed_at = NULL,
            last_error = ?
        WHERE processed_file_id = ?;
        """,
        batch_id,
        str(error)[:4000],
        processed_file_id,
    )

    cursor.execute(
        """
        UPDATE audit.LoadBatch
        SET
            status = 'FAILED',
            completed_at = SYSUTCDATETIME(),
            error_message = ?
        WHERE
            load_batch_id = ?
            AND status <> 'SUCCESS';
        """,
        str(error)[:4000],
        batch_id,
    )

    conn.commit()


def process_month(
    conn,
    *,
    year: int,
    month: int,
    chunk_size: int,
):
    print("\n" + "=" * 64)
    print(
        f"PHASE 16 INCREMENTAL MONTH "
        f"{year}-{month:02d}"
    )
    print("=" * 64)

    (
        source_file,
        relative_source,
        partition,
        file_hash,
        file_size,
    ) = source_metadata(
        year,
        month,
    )

    print("Source :", relative_source)
    print("SHA256 :", file_hash)

    (
        processed_file_id,
        registry_status,
        registry_batch,
    ) = ensure_registry_row(
        conn,
        relative_source=relative_source,
        partition=partition,
        file_hash=file_hash,
        file_size=file_size,
    )

    if registry_status == "SUCCESS":
        print(
            "Registry status: SUCCESS"
        )
        print(
            "Action         : SKIP — file version already processed"
        )
        return "SKIPPED"

    batch_id, batch_already_success = (
        prepare_batch(
            conn,
            year=year,
            month=month,
            relative_source=relative_source,
            partition=partition,
            file_hash=file_hash,
        )
    )

    if batch_already_success:
        print(
            "Audit batch already SUCCESS."
        )

        mark_success(
            conn,
            processed_file_id=processed_file_id,
            batch_id=batch_id,
            year=year,
            month=month,
        )

        print(
            "Registry repaired to SUCCESS."
        )

        return "SKIPPED"

    mark_processing(
        conn,
        processed_file_id,
        batch_id,
    )

    try:
        df = base.prepare_dataframe(
            source_file,
            year,
            month,
        )

        base.stage_dataframe(
            conn,
            df,
            str(batch_id),
            source_file,
            chunk_size,
        )

        base.execute_upsert(
            conn,
            str(batch_id),
        )

        base.verify_month(
            conn,
            year,
            month,
        )

        mark_success(
            conn,
            processed_file_id=processed_file_id,
            batch_id=batch_id,
            year=year,
            month=month,
        )

        print(
            "Processed-file registry: SUCCESS"
        )

        return "PROCESSED"

    except Exception as exc:
        mark_failed(
            conn,
            processed_file_id=processed_file_id,
            batch_id=batch_id,
            error=exc,
        )

        raise


def show_control_state(conn):
    cursor = conn.cursor()

    print("\n===== PHASE 16 CONTROL STATE =====")

    cursor.execute(
        """
        SELECT
            source_partition,
            status
        FROM etl.ProcessedFileRegistry
        WHERE pipeline_name = ?
        ORDER BY source_partition;
        """,
        PIPELINE_NAME,
    )

    rows = cursor.fetchall()

    for row in rows:
        print(
            f"{row.source_partition}: "
            f"{row.status}"
        )

    cursor.execute(
        """
        SELECT
            last_successful_watermark
        FROM etl.LoadWatermark
        WHERE
            pipeline_name = ?
            AND source_entity = ?;
        """,
        PIPELINE_NAME,
        SOURCE_ENTITY,
    )

    watermark = cursor.fetchone()

    print(
        "Watermark:",
        (
            watermark.last_successful_watermark
            if watermark
            else None
        ),
    )


def main():
    args = parse_args()

    if args.start_month > args.end_month:
        raise ValueError(
            "--start-month cannot be greater than --end-month."
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
            result = process_month(
                conn,
                year=args.year,
                month=month,
                chunk_size=args.chunk_size,
            )

            if result == "PROCESSED":
                processed += 1
            else:
                skipped += 1

        show_control_state(conn)

        print("\n===== RUN SUMMARY =====")
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
            "\nIncremental load cancelled.",
            file=sys.stderr,
        )
        sys.exit(130)

    except Exception as exc:
        print(
            f"\nERROR: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
