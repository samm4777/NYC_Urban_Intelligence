/* =========================================================
   PHASE 17 — IDEMPOTENT RERUN VALIDATION
   ========================================================= */

------------------------------------------------------------
-- Full Gold fact row count
------------------------------------------------------------
SELECT
    COUNT_BIG(*) AS total_gold_rows
FROM dw.FactZoneHourlyActivity;
GO


------------------------------------------------------------
-- July 2025 row count
------------------------------------------------------------
SELECT
    COUNT_BIG(*) AS july_2025_rows
FROM dw.FactZoneHourlyActivity f
JOIN dw.DimDate d
    ON f.date_key = d.date_key
WHERE
    d.full_date >= '2025-07-01'
    AND d.full_date < '2025-08-01';
GO


------------------------------------------------------------
-- Duplicate Gold business grain
------------------------------------------------------------
SELECT
    date_key,
    time_key,
    zone_key,
    COUNT_BIG(*) AS duplicate_count
FROM dw.FactZoneHourlyActivity
GROUP BY
    date_key,
    time_key,
    zone_key
HAVING COUNT_BIG(*) > 1;
GO


------------------------------------------------------------
-- Expected Phase 17 mandatory-test result
--
-- Before rerun:
-- total Gold rows = 2,303,880
-- July rows       =   195,672
--
-- Same July source rerun twice:
-- pipeline action = SKIP
-- processed       = 0
-- skipped         = 1
--
-- After rerun:
-- total Gold rows = 2,303,880
-- July rows       =   195,672
--
-- Duplicate Gold grains = 0
------------------------------------------------------------
