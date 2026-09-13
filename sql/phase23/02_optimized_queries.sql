/*
===============================================================================
PHASE 23 - OPTIMIZED ANALYTICAL QUERIES
===============================================================================

Queries optimized:
Q5  - Month-over-month taxi-demand growth
Q14 - Simultaneous taxi-demand and complaint spikes
Q15 - 7-day rolling taxi demand

Optimization basis:
dw.AggZoneDailyActivity
===============================================================================
*/


-------------------------------------------------------------------------------
-- OPTIMIZED Q5
-- Which zones show strongest month-over-month taxi-demand growth?
-------------------------------------------------------------------------------

WITH monthly_zone AS
(
    SELECT
        a.zone_key,
        DATEFROMPARTS(d.year, d.month_number, 1) AS month_start,
        SUM(a.daily_trips) AS monthly_trips
    FROM dw.AggZoneDailyActivity a
    JOIN dw.DimDate d
        ON a.date_key = d.date_key
    GROUP BY
        a.zone_key,
        DATEFROMPARTS(d.year, d.month_number, 1)
),
lagged AS
(
    SELECT
        zone_key,
        month_start,
        monthly_trips,
        LAG(monthly_trips) OVER
        (
            PARTITION BY zone_key
            ORDER BY month_start
        ) AS previous_month_trips
    FROM monthly_zone
),
growth AS
(
    SELECT
        zone_key,
        month_start,
        monthly_trips,
        previous_month_trips,
        CAST(
            100.0 * (monthly_trips - previous_month_trips)
            / NULLIF(previous_month_trips, 0)
            AS decimal(12,2)
        ) AS growth_pct
    FROM lagged
    WHERE previous_month_trips IS NOT NULL
),
ranked AS
(
    SELECT
        *,
        DENSE_RANK() OVER
        (
            PARTITION BY month_start
            ORDER BY growth_pct DESC
        ) AS growth_rank
    FROM growth
)
SELECT
    r.month_start,
    z.zone_name,
    z.borough,
    r.previous_month_trips,
    r.monthly_trips,
    r.growth_pct,
    r.growth_rank
FROM ranked r
JOIN dw.DimZone z
    ON r.zone_key = z.zone_key
WHERE r.growth_rank <= 10
ORDER BY
    r.month_start,
    r.growth_rank;
GO


-------------------------------------------------------------------------------
-- OPTIMIZED Q14
-- Which zone/date combinations show simultaneous taxi and complaint spikes?
-------------------------------------------------------------------------------

WITH zone_stats AS
(
    SELECT
        zone_key,
        AVG(CAST(daily_trips AS float)) AS avg_daily_trips,
        STDEV(CAST(daily_trips AS float)) AS sd_daily_trips,
        AVG(CAST(daily_complaints AS float)) AS avg_daily_complaints,
        STDEV(CAST(daily_complaints AS float)) AS sd_daily_complaints
    FROM dw.AggZoneDailyActivity
    GROUP BY zone_key
),
scored AS
(
    SELECT
        a.zone_key,
        a.date_key,
        a.daily_trips,
        a.daily_complaints,

        (a.daily_trips - s.avg_daily_trips)
            / NULLIF(s.sd_daily_trips, 0)
            AS taxi_z_score,

        (a.daily_complaints - s.avg_daily_complaints)
            / NULLIF(s.sd_daily_complaints, 0)
            AS complaint_z_score
    FROM dw.AggZoneDailyActivity a
    JOIN zone_stats s
        ON a.zone_key = s.zone_key
)
SELECT
    z.zone_name,
    z.borough,
    d.full_date,
    s.daily_trips,
    s.daily_complaints,
    CAST(s.taxi_z_score AS decimal(10,2)) AS taxi_z_score,
    CAST(s.complaint_z_score AS decimal(10,2)) AS complaint_z_score
FROM scored s
JOIN dw.DimZone z
    ON s.zone_key = z.zone_key
JOIN dw.DimDate d
    ON s.date_key = d.date_key
WHERE
    s.taxi_z_score >= 2.0
    AND s.complaint_z_score >= 2.0
ORDER BY
    s.taxi_z_score + s.complaint_z_score DESC;
GO


-------------------------------------------------------------------------------
-- OPTIMIZED Q15
-- What is the 7-day rolling average taxi demand for each zone?
-------------------------------------------------------------------------------

WITH rolling_demand AS
(
    SELECT
        a.zone_key,
        a.date_key,
        a.daily_trips,

        CAST(
            AVG(CAST(a.daily_trips AS decimal(18,2)))
            OVER
            (
                PARTITION BY a.zone_key
                ORDER BY a.date_key
                ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            )
            AS decimal(18,2)
        ) AS rolling_7_day_avg_trips

    FROM dw.AggZoneDailyActivity a
)
SELECT
    z.zone_name,
    z.borough,
    d.full_date,
    r.daily_trips,
    r.rolling_7_day_avg_trips
FROM rolling_demand r
JOIN dw.DimZone z
    ON r.zone_key = z.zone_key
JOIN dw.DimDate d
    ON r.date_key = d.date_key
ORDER BY
    z.zone_name,
    d.full_date;
GO
