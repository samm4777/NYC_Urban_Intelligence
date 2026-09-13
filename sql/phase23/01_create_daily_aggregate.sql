/*
===============================================================================
PHASE 23 - DAILY ANALYTICAL AGGREGATE
===============================================================================

Purpose:
Reduce repeated scans of the 2,303,880-row hourly Gold fact for analyses
whose natural grain is Zone x Date.

Expected rows:
263 zones x 365 dates = 95,995
===============================================================================
*/

SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dw.AggZoneDailyActivity', N'U') IS NULL
BEGIN
    CREATE TABLE dw.AggZoneDailyActivity
    (
        date_key          int    NOT NULL,
        zone_key          int    NOT NULL,
        daily_trips       bigint NOT NULL,
        daily_complaints  bigint NOT NULL,

        CONSTRAINT PK_AggZoneDailyActivity
            PRIMARY KEY CLUSTERED
            (
                zone_key,
                date_key
            )
    );
END;

TRUNCATE TABLE dw.AggZoneDailyActivity;

INSERT INTO dw.AggZoneDailyActivity
(
    date_key,
    zone_key,
    daily_trips,
    daily_complaints
)
SELECT
    date_key,
    zone_key,
    SUM(taxi_trips),
    SUM(CAST(complaints_311 AS bigint))
FROM dw.FactZoneHourlyActivity
GROUP BY
    date_key,
    zone_key;

IF (SELECT COUNT_BIG(*) FROM dw.AggZoneDailyActivity) <> 95995
BEGIN
    THROW 52023,
        'AggZoneDailyActivity reconciliation failed. Expected 95,995 rows.',
        1;
END;

SELECT
    COUNT_BIG(*) AS daily_aggregate_rows,
    SUM(daily_trips) AS taxi_trips,
    SUM(daily_complaints) AS complaints_311
FROM dw.AggZoneDailyActivity;
