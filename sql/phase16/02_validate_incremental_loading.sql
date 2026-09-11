/* =========================================================
   PHASE 16 — FINAL INCREMENTAL LOADING VALIDATION
   ========================================================= */

-- Processed-file registry summary
SELECT
    status,
    COUNT(*) AS file_count
FROM etl.ProcessedFileRegistry
WHERE pipeline_name =
    'gold_zone_hourly_incremental_to_azure_sql'
GROUP BY status;


-- Final watermark
SELECT
    pipeline_name,
    source_entity,
    last_successful_watermark,
    last_successful_run_id,
    updated_at
FROM etl.LoadWatermark
WHERE pipeline_name =
    'gold_zone_hourly_incremental_to_azure_sql';


-- Incremental audit summary
SELECT
    status,
    COUNT(*) AS batch_count,
    SUM(rows_read) AS total_rows_read,
    SUM(rows_inserted) AS total_rows_inserted,
    SUM(rows_updated) AS total_rows_updated,
    SUM(rows_rejected) AS total_rows_rejected
FROM audit.LoadBatch
WHERE pipeline_name =
    'gold_zone_hourly_incremental_to_azure_sql'
GROUP BY status;


-- Any incomplete file registrations?
SELECT
    source_partition,
    status,
    last_error
FROM etl.ProcessedFileRegistry
WHERE pipeline_name =
    'gold_zone_hourly_incremental_to_azure_sql'
    AND status <> 'SUCCESS'
ORDER BY source_partition;


-- Final Gold fact integrity
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
GO

/*
Expected:
Processed files       = 12 SUCCESS
Watermark             = 2025-12-31 23:59:59.999
Successful batches    = 12
Rows read             = 2,303,880
Rows inserted         = 0
Rows updated          = 2,303,880
Rows rejected         = 0
Incomplete files      = 0
Fact rows             = 2,303,880
Distinct fact grains  = 2,303,880
*/
