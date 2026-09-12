from __future__ import annotations

from datetime import date
from typing import Optional


def _fetch_result_row(cursor):
    if cursor.description:
        row = cursor.fetchone()
        if row is not None:
            return row

    while cursor.nextset():
        if cursor.description:
            row = cursor.fetchone()
            if row is not None:
                return row

    return None


def log_start(
    conn,
    *,
    pipeline_name: str,
    source: str,
    processing_month: Optional[date],
    stage: str,
    load_batch_id=None,
) -> str:
    cursor = conn.cursor()

    cursor.execute(
        """
        DECLARE @run_id UNIQUEIDENTIFIER;

        EXEC etl.usp_LogETLStart
            @pipeline_name = ?,
            @source = ?,
            @processing_month = ?,
            @stage = ?,
            @load_batch_id = ?,
            @run_id = @run_id OUTPUT;

        SELECT @run_id AS run_id;
        """,
        pipeline_name,
        source,
        processing_month,
        stage,
        load_batch_id,
    )

    row = _fetch_result_row(cursor)

    if row is None:
        raise RuntimeError(
            "ETL logging START did not return run_id."
        )

    conn.commit()

    return str(row[0])


def log_success(
    conn,
    *,
    run_id: str,
    rows_processed: int,
    rows_valid: int,
    rows_rejected: int,
    quarantine_rows: int,
):
    cursor = conn.cursor()

    cursor.execute(
        """
        EXEC etl.usp_LogETLSuccess
            @run_id = ?,
            @rows_processed = ?,
            @rows_valid = ?,
            @rows_rejected = ?,
            @quarantine_rows = ?;
        """,
        run_id,
        rows_processed,
        rows_valid,
        rows_rejected,
        quarantine_rows,
    )

    conn.commit()


def log_failure(
    conn,
    *,
    run_id: str,
    error_message: str,
):
    cursor = conn.cursor()

    cursor.execute(
        """
        EXEC etl.usp_LogETLFailure
            @run_id = ?,
            @error_message = ?,
            @rows_processed = NULL,
            @rows_valid = NULL,
            @rows_rejected = NULL,
            @quarantine_rows = NULL;
        """,
        run_id,
        error_message[:4000],
    )

    conn.commit()
