/* =========================================================
   PHASE 17 — DUPLICATE PREVENTION VALIDATION
   ========================================================= */

SET NOCOUNT ON;
GO


/* =========================================================
   1. GOLD BUSINESS KEY
   Business key:
   date_key + time_key + zone_key
   ========================================================= */

SELECT
    COUNT_BIG(*) AS gold_rows,
    COUNT_BIG(
        DISTINCT CONCAT(
            date_key, ':',
            time_key, ':',
            zone_key
        )
    ) AS distinct_gold_business_keys
FROM dw.FactZoneHourlyActivity;
GO


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


/* =========================================================
   2. 311 BUSINESS KEY
   Business key:
   unique_key
   ========================================================= */

SELECT
    unique_key,
    COUNT_BIG(*) AS duplicate_count
FROM dw.Fact311Complaints
GROUP BY unique_key
HAVING COUNT_BIG(*) > 1;
GO


/* =========================================================
   3. DIMENSION NATURAL KEYS
   ========================================================= */

SELECT
    full_date,
    COUNT(*) AS duplicate_count
FROM dw.DimDate
GROUP BY full_date
HAVING COUNT(*) > 1;
GO


SELECT
    hour_of_day,
    COUNT(*) AS duplicate_count
FROM dw.DimTime
WHERE hour_of_day IS NOT NULL
GROUP BY hour_of_day
HAVING COUNT(*) > 1;
GO


SELECT
    location_id,
    COUNT(*) AS duplicate_count
FROM dw.DimZone
GROUP BY location_id
HAVING COUNT(*) > 1;
GO


SELECT
    payment_type_code,
    COUNT(*) AS duplicate_count
FROM dw.DimPaymentType
GROUP BY payment_type_code
HAVING COUNT(*) > 1;
GO


SELECT
    complaint_type,
    COUNT(*) AS duplicate_count
FROM dw.DimComplaintType
GROUP BY complaint_type
HAVING COUNT(*) > 1;
GO


SELECT
    weather_code,
    COUNT(*) AS duplicate_count
FROM dw.DimWeatherCondition
GROUP BY weather_code
HAVING COUNT(*) > 1;
GO


/* =========================================================
   4. VERIFY UNIQUE INDEX / CONSTRAINT PROTECTION
   ========================================================= */

SELECT
    s.name AS schema_name,
    t.name AS table_name,
    i.name AS index_name,
    i.is_unique,
    i.type_desc
FROM sys.indexes i
JOIN sys.tables t
    ON i.object_id = t.object_id
JOIN sys.schemas s
    ON t.schema_id = s.schema_id
WHERE
    s.name = 'dw'
    AND i.is_unique = 1
    AND t.name IN
    (
        'FactZoneHourlyActivity',
        'Fact311Complaints',
        'DimDate',
        'DimTime',
        'DimZone',
        'DimPaymentType',
        'DimComplaintType',
        'DimWeatherCondition'
    )
ORDER BY
    t.name,
    i.name;
GO
