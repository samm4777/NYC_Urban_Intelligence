/* ============================================================
   PHASE 38 — RECONCILIATION
   NYC Urban Intelligence Platform
   ============================================================ */

SET NOCOUNT ON;

PRINT '============================================================';
PRINT 'PHASE 38 — RECORD LEVEL RECONCILIATION';
PRINT '============================================================';


/* ============================================================
   1. RAW / VALID / REJECTED RECONCILIATION
   ============================================================ */

SELECT
    source_name,
    input_records       AS raw_records,
    valid_records       AS silver_valid_records,
    rejected_records    AS rejected_records,

    input_records
        - valid_records
        - rejected_records AS reconciliation_variance,

    CASE
        WHEN input_records =
             valid_records + rejected_records
        THEN 'PASS'
        ELSE 'FAIL'
    END AS reconciliation_status

FROM dw.vw_DataQualitySummary
ORDER BY source_name;



/* ============================================================
   2. OVERALL RECORD RECONCILIATION
   ============================================================ */

SELECT
    SUM(input_records) AS total_raw_records,
    SUM(valid_records) AS total_valid_records,
    SUM(rejected_records) AS total_rejected_records,

    SUM(input_records)
        - SUM(valid_records)
        - SUM(rejected_records)
        AS reconciliation_variance,

    CASE
        WHEN SUM(input_records) =
             SUM(valid_records) + SUM(rejected_records)
        THEN 'PASS'
        ELSE 'FAIL'
    END AS reconciliation_status

FROM dw.vw_DataQualitySummary;



PRINT '============================================================';
PRINT 'PHASE 38 — GOLD RECONCILIATION';
PRINT '============================================================';


/* ============================================================
   3. GOLD PHYSICAL GRAIN CHECK
   Expected:
       263 Taxi Zones × 8,760 hours
       = 2,303,880 rows
   ============================================================ */

SELECT
    COUNT_BIG(*) AS actual_gold_rows,
    CAST(263 AS BIGINT) * 8760 AS expected_gold_rows,

    COUNT_BIG(*) -
        (CAST(263 AS BIGINT) * 8760)
        AS variance,

    CASE
        WHEN COUNT_BIG(*) =
             CAST(263 AS BIGINT) * 8760
        THEN 'PASS'
        ELSE 'FAIL'
    END AS reconciliation_status

FROM dw.FactZoneHourlyActivity;



/* ============================================================
   4. TAXI SILVER → GOLD RECONCILIATION

   Silver valid taxi rows       = 48,720,337
   IDs 264/265 excluded         =    103,042
   Gold represented trips       = 48,617,295
   ============================================================ */

SELECT
    CAST(48720337 AS BIGINT) AS silver_valid_taxi_rows,
    CAST(103042 AS BIGINT) AS documented_special_zone_exclusions,
    CAST(48720337 - 103042 AS BIGINT)
        AS expected_gold_taxi_trips,

    SUM(CAST(taxi_trips AS BIGINT))
        AS actual_gold_taxi_trips,

    SUM(CAST(taxi_trips AS BIGINT))
        - CAST(48617295 AS BIGINT)
        AS variance,

    CASE
        WHEN SUM(CAST(taxi_trips AS BIGINT)) = 48617295
        THEN 'PASS'
        ELSE 'FAIL'
    END AS reconciliation_status

FROM dw.FactZoneHourlyActivity;



/* ============================================================
   5. 311 SILVER → GOLD RECONCILIATION

   Silver valid/mapped records  = 3,604,061
   Outside zone polygons        =       665
   Gold represented complaints  = 3,603,396
   ============================================================ */

SELECT
    CAST(3604061 AS BIGINT)
        AS silver_311_records,

    CAST(665 AS BIGINT)
        AS documented_spatial_exclusions,

    CAST(3604061 - 665 AS BIGINT)
        AS expected_gold_311_complaints,

    SUM(CAST(complaints_311 AS BIGINT))
        AS actual_gold_311_complaints,

    SUM(CAST(complaints_311 AS BIGINT))
        - CAST(3603396 AS BIGINT)
        AS variance,

    CASE
        WHEN SUM(CAST(complaints_311 AS BIGINT)) = 3603396
        THEN 'PASS'
        ELSE 'FAIL'
    END AS reconciliation_status

FROM dw.FactZoneHourlyActivity;



/* ============================================================
   6. EXISTING WAREHOUSE RECONCILIATION CHECKS
   ============================================================ */

SELECT *
FROM dw.vw_ReconciliationHealth;