/*
===============================================================================
NYC URBAN INTELLIGENCE PLATFORM
PHASE 22 - SQL ANALYSIS
===============================================================================

Purpose:
Provide meaningful analytical SQL queries against the dimensional warehouse.

Techniques demonstrated:
- CTEs
- Window functions
- LAG
- DENSE_RANK / NTILE
- Joins
- Aggregations
- Date analysis
- CASE logic
- Rolling averages
- Standard deviation / volatility
- Spike detection

Primary analytical source:
    dw.FactZoneHourlyActivity

Detailed fact analyses at the end use:
    dw.FactTaxiTrips
    dw.Fact311Complaints
===============================================================================
*/

SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;

-------------------------------------------------------------------------------
-- Q1. Which taxi zones have the highest overall taxi demand?
-------------------------------------------------------------------------------
SELECT TOP (20)
    z.location_id,
    z.zone_name,
    z.borough,
    SUM(f.taxi_trips) AS total_taxi_trips
FROM dw.FactZoneHourlyActivity f
JOIN dw.DimZone z
    ON f.zone_key = z.zone_key
GROUP BY
    z.location_id,
    z.zone_name,
    z.borough
ORDER BY total_taxi_trips DESC;
GO


-------------------------------------------------------------------------------
-- Q2. Which hours of the day are busiest for taxi demand?
-------------------------------------------------------------------------------
SELECT
    t.hour_of_day,
    t.hour_label,
    t.daypart,
    SUM(f.taxi_trips) AS total_taxi_trips,
    AVG(CAST(f.taxi_trips AS decimal(18,2))) AS avg_trips_per_zone_hour
FROM dw.FactZoneHourlyActivity f
JOIN dw.DimTime t
    ON f.time_key = t.time_key
GROUP BY
    t.hour_of_day,
    t.hour_label,
    t.daypart
ORDER BY total_taxi_trips DESC;
GO


-------------------------------------------------------------------------------
-- Q3. Which taxi zones generate the most revenue?
-------------------------------------------------------------------------------
SELECT TOP (20)
    z.location_id,
    z.zone_name,
    z.borough,
    SUM(f.taxi_revenue) AS total_revenue,
    SUM(f.taxi_trips) AS total_trips
FROM dw.FactZoneHourlyActivity f
JOIN dw.DimZone z
    ON f.zone_key = z.zone_key
GROUP BY
    z.location_id,
    z.zone_name,
    z.borough
ORDER BY total_revenue DESC;
GO


-------------------------------------------------------------------------------
-- Q4. Which borough has the highest weighted average taxi fare?
-------------------------------------------------------------------------------
SELECT
    z.borough,
    SUM(f.taxi_trips) AS total_trips,
    SUM(f.taxi_revenue) AS total_revenue,
    CAST(
        SUM(
            CAST(f.average_fare AS decimal(38,6))
            * CAST(f.taxi_trips AS decimal(38,6))
        )
        / NULLIF(SUM(CAST(f.taxi_trips AS decimal(38,6))), 0)
        AS decimal(18,2)
    ) AS weighted_average_fare
FROM dw.FactZoneHourlyActivity f
JOIN dw.DimZone z
    ON f.zone_key = z.zone_key
WHERE f.taxi_trips > 0
GROUP BY z.borough
ORDER BY weighted_average_fare DESC;
GO


-------------------------------------------------------------------------------
-- Q5. Which zones show the strongest month-over-month taxi-demand growth?
-- Demonstrates CTE + LAG + ranking.
-------------------------------------------------------------------------------
WITH monthly_zone AS
(
    SELECT
        f.zone_key,
        DATEFROMPARTS(d.year, d.month_number, 1) AS month_start,
        SUM(f.taxi_trips) AS monthly_trips
    FROM dw.FactZoneHourlyActivity f
    JOIN dw.DimDate d
        ON f.date_key = d.date_key
    GROUP BY
        f.zone_key,
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
-- Q6. How does taxi demand change during rainy versus dry conditions?
-- Demonstrates CASE logic.
-------------------------------------------------------------------------------
SELECT
    CASE
        WHEN f.rain_mm > 0 THEN 'Rain'
        ELSE 'Dry'
    END AS weather_group,
    SUM(f.taxi_trips) AS total_trips,
    AVG(CAST(f.taxi_trips AS decimal(18,2))) AS avg_trips_per_zone_hour,
    AVG(CAST(f.taxi_revenue AS decimal(18,2))) AS avg_revenue_per_zone_hour
FROM dw.FactZoneHourlyActivity f
GROUP BY
    CASE
        WHEN f.rain_mm > 0 THEN 'Rain'
        ELSE 'Dry'
    END
ORDER BY total_trips DESC;
GO


-------------------------------------------------------------------------------
-- Q7. How does snowfall correspond with taxi activity?
-------------------------------------------------------------------------------
SELECT
    CASE
        WHEN f.snowfall_cm = 0 THEN 'No Snow'
        WHEN f.snowfall_cm > 0 AND f.snowfall_cm < 1 THEN 'Light Snow'
        WHEN f.snowfall_cm >= 1 AND f.snowfall_cm < 5 THEN 'Moderate Snow'
        ELSE 'Heavy Snow'
    END AS snowfall_band,
    COUNT_BIG(*) AS zone_hour_records,
    SUM(f.taxi_trips) AS total_trips,
    AVG(CAST(f.taxi_trips AS decimal(18,2))) AS avg_trips_per_zone_hour,
    SUM(f.taxi_revenue) AS total_revenue
FROM dw.FactZoneHourlyActivity f
GROUP BY
    CASE
        WHEN f.snowfall_cm = 0 THEN 'No Snow'
        WHEN f.snowfall_cm > 0 AND f.snowfall_cm < 1 THEN 'Light Snow'
        WHEN f.snowfall_cm >= 1 AND f.snowfall_cm < 5 THEN 'Moderate Snow'
        ELSE 'Heavy Snow'
    END
ORDER BY total_trips DESC;
GO


-------------------------------------------------------------------------------
-- Q8. Among the highest-demand zones, which also generate the most 311
-- complaints?
-- Demonstrates NTILE window function.
-------------------------------------------------------------------------------
WITH zone_totals AS
(
    SELECT
        zone_key,
        SUM(taxi_trips) AS total_trips,
        SUM(complaints_311) AS total_complaints
    FROM dw.FactZoneHourlyActivity
    GROUP BY zone_key
),
classified AS
(
    SELECT
        *,
        NTILE(4) OVER
        (
            ORDER BY total_trips DESC
        ) AS demand_quartile
    FROM zone_totals
)
SELECT
    z.zone_name,
    z.borough,
    c.total_trips,
    c.total_complaints,
    c.demand_quartile
FROM classified c
JOIN dw.DimZone z
    ON c.zone_key = z.zone_key
WHERE c.demand_quartile = 1
ORDER BY c.total_complaints DESC;
GO


-------------------------------------------------------------------------------
-- Q9. Which zones have high complaint activity but comparatively low
-- taxi demand?
-------------------------------------------------------------------------------
WITH zone_totals AS
(
    SELECT
        zone_key,
        SUM(taxi_trips) AS total_trips,
        SUM(complaints_311) AS total_complaints
    FROM dw.FactZoneHourlyActivity
    GROUP BY zone_key
),
scored AS
(
    SELECT
        *,
        NTILE(4) OVER
        (
            ORDER BY total_trips DESC
        ) AS demand_quartile,
        NTILE(4) OVER
        (
            ORDER BY total_complaints DESC
        ) AS complaint_quartile
    FROM zone_totals
)
SELECT
    z.zone_name,
    z.borough,
    s.total_trips,
    s.total_complaints,
    CASE
        WHEN s.complaint_quartile = 1
             AND s.demand_quartile >= 3
            THEN 'High Complaints / Low Taxi Demand'
        ELSE 'Other'
    END AS zone_profile
FROM scored s
JOIN dw.DimZone z
    ON s.zone_key = z.zone_key
WHERE
    s.complaint_quartile = 1
    AND s.demand_quartile >= 3
ORDER BY
    s.total_complaints DESC,
    s.total_trips ASC;
GO


-------------------------------------------------------------------------------
-- Q10. Which hours generate the highest taxi revenue?
-------------------------------------------------------------------------------
SELECT
    t.hour_of_day,
    t.hour_label,
    t.daypart,
    SUM(f.taxi_revenue) AS total_revenue,
    SUM(f.taxi_trips) AS total_trips,
    CAST(
        SUM(f.taxi_revenue)
        / NULLIF(SUM(CAST(f.taxi_trips AS decimal(38,6))), 0)
        AS decimal(18,2)
    ) AS revenue_per_trip
FROM dw.FactZoneHourlyActivity f
JOIN dw.DimTime t
    ON f.time_key = t.time_key
GROUP BY
    t.hour_of_day,
    t.hour_label,
    t.daypart
ORDER BY total_revenue DESC;
GO


-------------------------------------------------------------------------------
-- Q11. How does weekday taxi demand compare with weekend demand?
-------------------------------------------------------------------------------
SELECT
    CASE
        WHEN d.is_weekend = 1 THEN 'Weekend'
        ELSE 'Weekday'
    END AS day_type,
    SUM(f.taxi_trips) AS total_trips,
    SUM(f.taxi_revenue) AS total_revenue,
    AVG(CAST(f.taxi_trips AS decimal(18,2))) AS avg_trips_per_zone_hour
FROM dw.FactZoneHourlyActivity f
JOIN dw.DimDate d
    ON f.date_key = d.date_key
GROUP BY
    CASE
        WHEN d.is_weekend = 1 THEN 'Weekend'
        ELSE 'Weekday'
    END;
GO


-------------------------------------------------------------------------------
-- Q12. Which zones show the greatest hourly revenue volatility?
-------------------------------------------------------------------------------
SELECT TOP (20)
    z.zone_name,
    z.borough,
    AVG(CAST(f.taxi_revenue AS decimal(18,2))) AS avg_hourly_revenue,
    STDEV(CAST(f.taxi_revenue AS float)) AS revenue_stddev,
    MAX(f.taxi_revenue) AS max_hourly_revenue
FROM dw.FactZoneHourlyActivity f
JOIN dw.DimZone z
    ON f.zone_key = z.zone_key
GROUP BY
    z.zone_name,
    z.borough
HAVING SUM(f.taxi_trips) > 0
ORDER BY revenue_stddev DESC;
GO


-------------------------------------------------------------------------------
-- Q13. Which zones show the most consistently increasing complaint
-- activity month-over-month?
-------------------------------------------------------------------------------
WITH monthly_complaints AS
(
    SELECT
        f.zone_key,
        DATEFROMPARTS(d.year, d.month_number, 1) AS month_start,
        SUM(f.complaints_311) AS monthly_complaints
    FROM dw.FactZoneHourlyActivity f
    JOIN dw.DimDate d
        ON f.date_key = d.date_key
    GROUP BY
        f.zone_key,
        DATEFROMPARTS(d.year, d.month_number, 1)
),
lagged AS
(
    SELECT
        zone_key,
        month_start,
        monthly_complaints,
        LAG(monthly_complaints) OVER
        (
            PARTITION BY zone_key
            ORDER BY month_start
        ) AS previous_month_complaints
    FROM monthly_complaints
),
summary AS
(
    SELECT
        zone_key,
        SUM(
            CASE
                WHEN previous_month_complaints IS NOT NULL
                     AND monthly_complaints > previous_month_complaints
                THEN 1
                ELSE 0
            END
        ) AS increasing_months,
        COUNT(previous_month_complaints) AS comparable_months
    FROM lagged
    GROUP BY zone_key
)
SELECT TOP (20)
    z.zone_name,
    z.borough,
    s.increasing_months,
    s.comparable_months,
    CAST(
        100.0 * s.increasing_months
        / NULLIF(s.comparable_months, 0)
        AS decimal(10,2)
    ) AS increasing_month_pct
FROM summary s
JOIN dw.DimZone z
    ON s.zone_key = z.zone_key
WHERE s.comparable_months > 0
ORDER BY
    increasing_month_pct DESC,
    increasing_months DESC;
GO


-------------------------------------------------------------------------------
-- Q14. Which zone/date combinations show simultaneous taxi-demand and
-- complaint spikes?
-- Spike definition: >= 2 standard deviations above the zone's daily mean.
-------------------------------------------------------------------------------
WITH daily_zone AS
(
    SELECT
        f.zone_key,
        d.full_date,
        SUM(f.taxi_trips) AS daily_trips,
        SUM(f.complaints_311) AS daily_complaints
    FROM dw.FactZoneHourlyActivity f
    JOIN dw.DimDate d
        ON f.date_key = d.date_key
    GROUP BY
        f.zone_key,
        d.full_date
),
stats AS
(
    SELECT
        *,
        AVG(CAST(daily_trips AS float))
            OVER (PARTITION BY zone_key) AS avg_daily_trips,
        STDEV(CAST(daily_trips AS float))
            OVER (PARTITION BY zone_key) AS sd_daily_trips,
        AVG(CAST(daily_complaints AS float))
            OVER (PARTITION BY zone_key) AS avg_daily_complaints,
        STDEV(CAST(daily_complaints AS float))
            OVER (PARTITION BY zone_key) AS sd_daily_complaints
    FROM daily_zone
),
scored AS
(
    SELECT
        *,
        (daily_trips - avg_daily_trips)
            / NULLIF(sd_daily_trips, 0) AS taxi_z_score,

        (daily_complaints - avg_daily_complaints)
            / NULLIF(sd_daily_complaints, 0) AS complaint_z_score
    FROM stats
)
SELECT
    z.zone_name,
    z.borough,
    s.full_date,
    s.daily_trips,
    s.daily_complaints,
    CAST(s.taxi_z_score AS decimal(10,2)) AS taxi_z_score,
    CAST(s.complaint_z_score AS decimal(10,2)) AS complaint_z_score
FROM scored s
JOIN dw.DimZone z
    ON s.zone_key = z.zone_key
WHERE
    s.taxi_z_score >= 2.0
    AND s.complaint_z_score >= 2.0
ORDER BY
    s.taxi_z_score + s.complaint_z_score DESC;
GO


-------------------------------------------------------------------------------
-- Q15. What is the 7-day rolling average taxi demand for each zone?
-------------------------------------------------------------------------------
WITH daily_zone AS
(
    SELECT
        f.zone_key,
        d.full_date,
        SUM(f.taxi_trips) AS daily_trips
    FROM dw.FactZoneHourlyActivity f
    JOIN dw.DimDate d
        ON f.date_key = d.date_key
    GROUP BY
        f.zone_key,
        d.full_date
)
SELECT
    z.zone_name,
    z.borough,
    dz.full_date,
    dz.daily_trips,
    CAST(
        AVG(CAST(dz.daily_trips AS decimal(18,2)))
        OVER
        (
            PARTITION BY dz.zone_key
            ORDER BY dz.full_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        )
        AS decimal(18,2)
    ) AS rolling_7_day_avg_trips
FROM daily_zone dz
JOIN dw.DimZone z
    ON dz.zone_key = z.zone_key
ORDER BY
    z.zone_name,
    dz.full_date;
GO


-------------------------------------------------------------------------------
-- Q16. How do taxi zones rank by revenue within their own borough?
-------------------------------------------------------------------------------
WITH zone_revenue AS
(
    SELECT
        f.zone_key,
        SUM(f.taxi_revenue) AS total_revenue,
        SUM(f.taxi_trips) AS total_trips
    FROM dw.FactZoneHourlyActivity f
    GROUP BY f.zone_key
),
ranked AS
(
    SELECT
        z.borough,
        z.zone_name,
        zr.total_revenue,
        zr.total_trips,
        DENSE_RANK() OVER
        (
            PARTITION BY z.borough
            ORDER BY zr.total_revenue DESC
        ) AS revenue_rank_in_borough
    FROM zone_revenue zr
    JOIN dw.DimZone z
        ON zr.zone_key = z.zone_key
)
SELECT
    borough,
    zone_name,
    total_revenue,
    total_trips,
    revenue_rank_in_borough
FROM ranked
WHERE revenue_rank_in_borough <= 10
ORDER BY
    borough,
    revenue_rank_in_borough;
GO


-------------------------------------------------------------------------------
-- Q17. How does taxi activity vary across recorded weather conditions?
-------------------------------------------------------------------------------
SELECT
    wc.weather_condition,
    COUNT_BIG(*) AS zone_hour_records,
    SUM(f.taxi_trips) AS total_trips,
    SUM(f.taxi_revenue) AS total_revenue,
    AVG(CAST(f.taxi_trips AS decimal(18,2))) AS avg_trips_per_zone_hour,
    AVG(CAST(f.temperature_c AS decimal(18,2))) AS avg_temperature_c,
    AVG(CAST(f.rain_mm AS decimal(18,2))) AS avg_rain_mm,
    AVG(CAST(f.snowfall_cm AS decimal(18,2))) AS avg_snowfall_cm
FROM dw.FactZoneHourlyActivity f
JOIN dw.DimWeatherCondition wc
    ON f.weather_condition_key = wc.weather_condition_key
GROUP BY wc.weather_condition
ORDER BY total_trips DESC;
GO

