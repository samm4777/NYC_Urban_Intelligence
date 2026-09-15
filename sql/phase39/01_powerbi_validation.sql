/* ============================================================
   PHASE 39 — POWER BI VALIDATION
   NYC Urban Intelligence Platform

   Purpose:
   Independently validate key Power BI metrics against Azure SQL.
   ============================================================ */

SET NOCOUNT ON;

PRINT '============================================================';
PRINT 'PHASE 39 — POWER BI VALIDATION';
PRINT '============================================================';


/* ============================================================
   1. TOTAL TAXI TRIPS
   Power BI Measure: [Total Trips]
   Expected full-year value: 48,617,295
   ============================================================ */

SELECT
    'Total Taxi Trips' AS metric,
    SUM(CAST(taxi_trips AS BIGINT)) AS sql_result
FROM dw.FactZoneHourlyActivity;


/* ============================================================
   2. TOTAL TAXI REVENUE
   Power BI Measure: [Total Revenue]
   ============================================================ */

SELECT
    'Total Revenue' AS metric,
    CAST(
        SUM(CAST(taxi_revenue AS DECIMAL(20,2)))
        AS DECIMAL(20,2)
    ) AS sql_result
FROM dw.FactZoneHourlyActivity;


/* ============================================================
   3. TOTAL 311 COMPLAINTS
   Power BI Measure: [Total Complaints]
   Expected full-year value: 3,603,396
   ============================================================ */

SELECT
    'Total Complaints' AS metric,
    SUM(CAST(complaints_311 AS BIGINT)) AS sql_result
FROM dw.FactZoneHourlyActivity;


/* ============================================================
   4. TOP TAXI ZONE BY TRIPS
   Power BI Visual: Top Pickup Zones
   ============================================================ */

SELECT TOP (10)
    z.location_id,
    z.zone_name,
    z.borough,
    SUM(CAST(f.taxi_trips AS BIGINT)) AS total_trips
FROM dw.FactZoneHourlyActivity AS f
INNER JOIN dw.DimZone AS z
    ON f.zone_key = z.zone_key
GROUP BY
    z.location_id,
    z.zone_name,
    z.borough
ORDER BY
    total_trips DESC;


/* ============================================================
   5. MONTHLY TAXI TRIPS
   Compare against Trips by Month / Executive Overview.
   ============================================================ */

SELECT
    d.month_number,
    d.month_name,
    SUM(CAST(f.taxi_trips AS BIGINT)) AS total_trips
FROM dw.FactZoneHourlyActivity AS f
INNER JOIN dw.DimDate AS d
    ON f.date_key = d.date_key
WHERE YEAR(d.full_date) = 2025
GROUP BY
    d.month_number,
    d.month_name
ORDER BY
    d.month_number;


/* ============================================================
   6. MONTHLY TAXI REVENUE
   ============================================================ */

SELECT
    d.month_number,
    d.month_name,
    CAST(
        SUM(CAST(f.taxi_revenue AS DECIMAL(20,2)))
        AS DECIMAL(20,2)
    ) AS total_revenue
FROM dw.FactZoneHourlyActivity AS f
INNER JOIN dw.DimDate AS d
    ON f.date_key = d.date_key
WHERE YEAR(d.full_date) = 2025
GROUP BY
    d.month_number,
    d.month_name
ORDER BY
    d.month_number;


/* ============================================================
   7. MONTHLY 311 COMPLAINTS
   ============================================================ */

SELECT
    d.month_number,
    d.month_name,
    SUM(CAST(f.complaints_311 AS BIGINT)) AS total_complaints
FROM dw.FactZoneHourlyActivity AS f
INNER JOIN dw.DimDate AS d
    ON f.date_key = d.date_key
WHERE YEAR(d.full_date) = 2025
GROUP BY
    d.month_number,
    d.month_name
ORDER BY
    d.month_number;


/* ============================================================
   8. CONTROL TOTAL
   Monthly trips must sum back to full-year trips.
   ============================================================ */

WITH monthly AS
(
    SELECT
        d.month_number,
        SUM(CAST(f.taxi_trips AS BIGINT)) AS monthly_trips
    FROM dw.FactZoneHourlyActivity AS f
    INNER JOIN dw.DimDate AS d
        ON f.date_key = d.date_key
    WHERE YEAR(d.full_date) = 2025
    GROUP BY d.month_number
)
SELECT
    SUM(monthly_trips) AS monthly_sum,
    CAST(48617295 AS BIGINT) AS expected_full_year_trips,
    SUM(monthly_trips) - CAST(48617295 AS BIGINT) AS variance,
    CASE
        WHEN SUM(monthly_trips) = 48617295
        THEN 'PASS'
        ELSE 'FAIL'
    END AS status
FROM monthly;