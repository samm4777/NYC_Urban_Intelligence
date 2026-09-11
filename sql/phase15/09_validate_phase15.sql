/* =========================================================
   PHASE 15 — FINAL WAREHOUSE VALIDATION
   Database: NYC_Urban_Intelligence_DW
   ========================================================= */

------------------------------------------------------------
-- 1. Dimension row counts
------------------------------------------------------------
SELECT 'DimDate' AS object_name, COUNT_BIG(*) AS row_count
FROM dw.DimDate

UNION ALL
SELECT 'DimTime', COUNT_BIG(*)
FROM dw.DimTime

UNION ALL
SELECT 'DimZone', COUNT_BIG(*)
FROM dw.DimZone

UNION ALL
SELECT 'DimPaymentType', COUNT_BIG(*)
FROM dw.DimPaymentType

UNION ALL
SELECT 'DimComplaintType', COUNT_BIG(*)
FROM dw.DimComplaintType

UNION ALL
SELECT 'DimWeatherCondition', COUNT_BIG(*)
FROM dw.DimWeatherCondition;
GO


------------------------------------------------------------
-- 2. Full-year Gold reconciliation
------------------------------------------------------------
SELECT
    YEAR(d.full_date) AS [year],

    COUNT_BIG(*) AS zone_hourly_rows,

    SUM(f.taxi_trips) AS taxi_trips,

    CAST(
        SUM(f.taxi_revenue)
        AS DECIMAL(28,2)
    ) AS taxi_revenue,

    SUM(
        CONVERT(BIGINT, f.complaints_311)
    ) AS complaints_311,

    COUNT(DISTINCT d.full_date) AS distinct_dates

FROM dw.FactZoneHourlyActivity f

JOIN dw.DimDate d
    ON f.date_key = d.date_key

WHERE YEAR(d.full_date) = 2025

GROUP BY YEAR(d.full_date);
GO


------------------------------------------------------------
-- 3. Monthly ETL batches
------------------------------------------------------------
SELECT
    source_partition,
    status,
    rows_read,
    rows_inserted,
    rows_updated,
    rows_rejected
FROM audit.LoadBatch
WHERE pipeline_name =
    'gold_zone_hourly_to_azure_sql'
ORDER BY source_partition;
GO


------------------------------------------------------------
-- 4. ETL status summary
------------------------------------------------------------
SELECT
    status,
    COUNT(*) AS batch_count
FROM audit.LoadBatch
WHERE pipeline_name =
    'gold_zone_hourly_to_azure_sql'
GROUP BY status;
GO


------------------------------------------------------------
-- 5. Reconciliation summary
------------------------------------------------------------
SELECT
    r.status,
    COUNT(*) AS reconciliation_count
FROM audit.ReconciliationResult r

JOIN audit.LoadBatch b
    ON r.load_batch_id = b.load_batch_id

WHERE b.pipeline_name =
    'gold_zone_hourly_to_azure_sql'

GROUP BY r.status;
GO


------------------------------------------------------------
-- 6. Staging cleanup
------------------------------------------------------------
SELECT
    COUNT_BIG(*) AS remaining_stage_rows
FROM etl.StageZoneHourlyActivity;
GO


------------------------------------------------------------
-- 7. Fact grain integrity
------------------------------------------------------------
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


------------------------------------------------------------
-- Expected Phase 15 final results
--
-- Gold rows          : 2,303,880
-- Taxi trips         : 48,617,295
-- Taxi revenue       : 1,306,369,662.27
-- 311 complaints     : 3,603,396
-- Distinct dates     : 365
-- Successful batches : 12
-- PASS reconciliations: 12
-- Remaining staging  : 0
------------------------------------------------------------
