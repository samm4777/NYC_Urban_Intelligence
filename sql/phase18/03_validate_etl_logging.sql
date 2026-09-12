/* =========================================================
   PHASE 18 — FINAL ETL LOGGING VALIDATION
   ========================================================= */

SET NOCOUNT ON;
GO


/* =========================================================
   1. Logging objects
   ========================================================= */

SELECT
    s.name AS schema_name,
    o.name AS object_name,
    o.type_desc
FROM sys.objects o
JOIN sys.schemas s
    ON o.schema_id = s.schema_id
WHERE
    (
        s.name = 'audit'
        AND o.name = 'ETLRunLog'
    )
    OR
    (
        s.name = 'etl'
        AND o.name IN
        (
            'usp_LogETLStart',
            'usp_LogETLSuccess',
            'usp_LogETLFailure'
        )
    )
ORDER BY
    s.name,
    o.name;
GO


/* =========================================================
   2. Framework test results
   ========================================================= */

SELECT
    pipeline_name,
    source,
    processing_month,
    stage,
    rows_processed,
    rows_valid,
    rows_rejected,
    quarantine_rows,
    status,
    error_message
FROM audit.ETLRunLog
WHERE pipeline_name = N'phase18_logging_test'
ORDER BY processing_month;
GO


/* =========================================================
   3. Real pipeline integration
   ========================================================= */

SELECT
    pipeline_name,
    source,
    processing_month,
    stage,
    start_time,
    end_time,
    rows_processed,
    rows_valid,
    rows_rejected,
    quarantine_rows,
    status,
    error_message
FROM audit.ETLRunLog
WHERE pipeline_name =
    N'gold_zone_hourly_incremental_logged'
ORDER BY start_time;
GO


/* =========================================================
   4. Completed-row reconciliation validation
   ========================================================= */

SELECT
    run_id,
    pipeline_name,
    processing_month,
    rows_processed,
    rows_valid,
    rows_rejected,
    quarantine_rows,
    status
FROM audit.ETLRunLog
WHERE
    status = 'SUCCESS'
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
GO


/* =========================================================
   5. Completed runs must have end_time
   ========================================================= */

SELECT
    run_id,
    pipeline_name,
    processing_month,
    status,
    start_time,
    end_time
FROM audit.ETLRunLog
WHERE
    status IN ('SUCCESS', 'FAILED')
    AND end_time IS NULL;
GO


/* =========================================================
   6. Stale STARTED executions
   ========================================================= */

SELECT
    run_id,
    pipeline_name,
    processing_month,
    stage,
    start_time
FROM audit.ETLRunLog
WHERE status = 'STARTED';
GO


/*
Expected Phase 18 results

Logging objects:
    ETLRunLog
    usp_LogETLStart
    usp_LogETLSuccess
    usp_LogETLFailure

Framework tests:
    SUCCESS test    -> SUCCESS
    FAILURE test    -> FAILED
    GUARDRAIL test  -> FAILED

Real pipeline:
    2025-07 -> SUCCESS
    2026-01 -> FAILED

Successful reconciliation violations:
    0 rows

Completed rows without end_time:
    0 rows

Stale STARTED test/pipeline runs:
    0 rows
*/
