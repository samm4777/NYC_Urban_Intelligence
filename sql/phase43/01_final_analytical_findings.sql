/*
PHASE 43 — FINAL ANALYTICAL FINDINGS
NYC Urban Intelligence Platform

Purpose:
Generate evidence for final analytical findings from the implemented Azure SQL warehouse.

Important:
- This script does not invent conclusions.
- Run it against NYC_Urban_Intelligence_DW.
- Use the returned values to write the final "What happened? / Why it matters /
  Practical interpretation" narrative.
*/

SET NOCOUNT ON;

-------------------------------------------------------------------------------
-- FINDING 1 — WHERE IS TAXI DEMAND HIGHEST?
-------------------------------------------------------------------------------
SELECT TOP (15)
    z.location_id,
    z.zone_name,
    z.borough,
    SUM(a.taxi_trips) AS total_trips,
    CAST(
        100.0 * SUM(a.taxi_trips)
        / NULLIF(SUM(SUM(a.taxi_trips)) OVER (), 0)
        AS decimal(10,4)
    ) AS pct_of_city_trips
FROM dw.FactZoneHourlyActivity a
JOIN dw.DimZone z
    ON z.zone_key = a.zone_key
GROUP BY
    z.location_id,
    z.zone_name,
    z.borough
ORDER BY total_trips DESC;


-------------------------------------------------------------------------------
-- FINDING 2 — WHEN IS TAXI DEMAND HIGHEST?
-------------------------------------------------------------------------------
SELECT
    t.hour_of_day,
    t.daypart,
    SUM(a.taxi_trips) AS total_trips,
    CAST(AVG(CAST(a.taxi_trips AS decimal(18,4))) AS decimal(18,2))
        AS avg_zone_hour_trips
FROM dw.FactZoneHourlyActivity a
JOIN dw.DimTime t
    ON t.time_key = a.time_key
GROUP BY
    t.hour_of_day,
    t.daypart
ORDER BY total_trips DESC;


-------------------------------------------------------------------------------
-- FINDING 3 — WHICH AREAS GENERATE THE MOST REVENUE?
-- Also calculates revenue per represented trip so high-volume and high-yield zones
-- can be distinguished.
-------------------------------------------------------------------------------
SELECT TOP (15)
    z.location_id,
    z.zone_name,
    z.borough,
    SUM(a.taxi_trips) AS total_trips,
    CAST(SUM(a.taxi_revenue) AS decimal(20,2)) AS total_revenue,
    CAST(
        SUM(a.taxi_revenue) / NULLIF(SUM(a.taxi_trips), 0)
        AS decimal(18,2)
    ) AS revenue_per_trip
FROM dw.FactZoneHourlyActivity a
JOIN dw.DimZone z
    ON z.zone_key = a.zone_key
GROUP BY
    z.location_id,
    z.zone_name,
    z.borough
ORDER BY total_revenue DESC;


-------------------------------------------------------------------------------
-- FINDING 4 — WHICH MONTHS CARRY THE MOST TAXI ACTIVITY?
-------------------------------------------------------------------------------
SELECT
    d.month_number,
    d.month_name,
    SUM(a.taxi_trips) AS total_trips,
    CAST(SUM(a.taxi_revenue) AS decimal(20,2)) AS total_revenue,
    SUM(a.complaints_311) AS complaints_311
FROM dw.FactZoneHourlyActivity a
JOIN dw.DimDate d
    ON d.date_key = a.date_key
GROUP BY
    d.month_number,
    d.month_name
ORDER BY
    d.month_number;


-------------------------------------------------------------------------------
-- FINDING 5 — HOW DOES WEATHER CORRESPOND WITH TAXI DEMAND?
-- First aggregate to one city-wide row per hour so a weather condition is not
-- artificially multiplied by the 263 taxi zones.
-------------------------------------------------------------------------------
WITH city_hour AS (
    SELECT
        a.date_key,
        a.time_key,
        a.weather_condition_key,
        SUM(a.taxi_trips) AS city_trips,
        SUM(a.taxi_revenue) AS city_revenue,
        SUM(a.complaints_311) AS city_complaints
    FROM dw.FactZoneHourlyActivity a
    GROUP BY
        a.date_key,
        a.time_key,
        a.weather_condition_key
)
SELECT
    w.weather_condition,
    COUNT_BIG(*) AS observed_city_hours,
    CAST(AVG(CAST(ch.city_trips AS decimal(18,4))) AS decimal(18,2))
        AS avg_city_trips_per_hour,
    CAST(AVG(CAST(ch.city_revenue AS decimal(20,4))) AS decimal(18,2))
        AS avg_city_revenue_per_hour,
    CAST(AVG(CAST(ch.city_complaints AS decimal(18,4))) AS decimal(18,2))
        AS avg_city_complaints_per_hour
FROM city_hour ch
JOIN dw.DimWeatherCondition w
    ON w.weather_condition_key = ch.weather_condition_key
GROUP BY
    w.weather_condition
ORDER BY
    avg_city_trips_per_hour DESC;


-------------------------------------------------------------------------------
-- FINDING 6 — HOW DOES TEMPERATURE CORRESPOND WITH DEMAND AND COMPLAINTS?
-- Temperature is city-wide hourly weather, so again aggregate city first.
-------------------------------------------------------------------------------
WITH city_hour AS (
    SELECT
        a.date_key,
        a.time_key,
        AVG(CAST(a.temperature_c AS decimal(10,4))) AS temperature_c,
        SUM(a.taxi_trips) AS city_trips,
        SUM(a.complaints_311) AS city_complaints
    FROM dw.FactZoneHourlyActivity a
    GROUP BY
        a.date_key,
        a.time_key
),
banded AS (
    SELECT
        CASE
            WHEN temperature_c < 0 THEN 'Freezing (<0C)'
            WHEN temperature_c < 10 THEN 'Cold (0-10C)'
            WHEN temperature_c < 20 THEN 'Cool (10-20C)'
            WHEN temperature_c < 30 THEN 'Warm (20-30C)'
            ELSE 'Hot (30C+)'
        END AS temperature_band,
        city_trips,
        city_complaints
    FROM city_hour
)
SELECT
    temperature_band,
    COUNT_BIG(*) AS observed_city_hours,
    CAST(AVG(CAST(city_trips AS decimal(18,4))) AS decimal(18,2))
        AS avg_city_trips_per_hour,
    CAST(AVG(CAST(city_complaints AS decimal(18,4))) AS decimal(18,2))
        AS avg_city_complaints_per_hour
FROM banded
GROUP BY
    temperature_band
ORDER BY
    CASE temperature_band
        WHEN 'Freezing (<0C)' THEN 1
        WHEN 'Cold (0-10C)' THEN 2
        WHEN 'Cool (10-20C)' THEN 3
        WHEN 'Warm (20-30C)' THEN 4
        ELSE 5
    END;


-------------------------------------------------------------------------------
-- FINDING 7 — WHICH COMPLAINT CATEGORIES ARE GEOGRAPHICALLY CONCENTRATED?
-- Returns the dominant taxi zone for each high-volume complaint category and
-- the percentage of that category occurring in that top zone.
-------------------------------------------------------------------------------
WITH category_zone AS (
    SELECT
        ct.complaint_type,
        z.zone_name,
        z.borough,
        COUNT_BIG(*) AS complaint_count
    FROM dw.Fact311Complaints f
    JOIN dw.DimComplaintType ct
        ON ct.complaint_type_key = f.complaint_type_key
    JOIN dw.DimZone z
        ON z.zone_key = f.zone_key
    GROUP BY
        ct.complaint_type,
        z.zone_name,
        z.borough
),
ranked AS (
    SELECT
        complaint_type,
        zone_name,
        borough,
        complaint_count,
        SUM(complaint_count) OVER (
            PARTITION BY complaint_type
        ) AS category_total,
        ROW_NUMBER() OVER (
            PARTITION BY complaint_type
            ORDER BY complaint_count DESC
        ) AS zone_rank
    FROM category_zone
)
SELECT TOP (20)
    complaint_type,
    zone_name AS dominant_zone,
    borough,
    complaint_count AS dominant_zone_complaints,
    category_total,
    CAST(
        100.0 * complaint_count / NULLIF(category_total, 0)
        AS decimal(10,2)
    ) AS dominant_zone_share_pct
FROM ranked
WHERE
    zone_rank = 1
    AND category_total >= 1000
ORDER BY
    dominant_zone_share_pct DESC,
    category_total DESC;


-------------------------------------------------------------------------------
-- FINDING 8 — ARE HIGH-COMPLAINT AREAS ALSO HIGH-TRAFFIC AREAS?
-- Zone-level Pearson correlation. A value near +1 indicates that zones with
-- more taxi traffic also tend to have more complaints; near 0 means weak
-- linear correspondence.
-------------------------------------------------------------------------------
WITH zone_totals AS (
    SELECT
        zone_key,
        CAST(SUM(taxi_trips) AS float) AS trips,
        CAST(SUM(complaints_311) AS float) AS complaints
    FROM dw.FactZoneHourlyActivity
    GROUP BY zone_key
),
stats AS (
    SELECT
        COUNT(*) AS n,
        SUM(trips) AS sx,
        SUM(complaints) AS sy,
        SUM(trips * complaints) AS sxy,
        SUM(trips * trips) AS sx2,
        SUM(complaints * complaints) AS sy2
    FROM zone_totals
)
SELECT
    CAST(
        (n * sxy - sx * sy)
        /
        NULLIF(
            SQRT(
                (n * sx2 - sx * sx)
                *
                (n * sy2 - sy * sy)
            ),
            0
        )
        AS decimal(12,6)
    ) AS pearson_zone_trips_vs_complaints
FROM stats;

-- Supporting zone table for practical interpretation.
SELECT TOP (25)
    z.zone_name,
    z.borough,
    SUM(a.taxi_trips) AS total_trips,
    SUM(a.complaints_311) AS total_complaints,
    CAST(
        1000.0 * SUM(a.complaints_311)
        / NULLIF(SUM(a.taxi_trips), 0)
        AS decimal(18,2)
    ) AS complaints_per_1000_trips
FROM dw.FactZoneHourlyActivity a
JOIN dw.DimZone z
    ON z.zone_key = a.zone_key
GROUP BY
    z.zone_name,
    z.borough
HAVING
    SUM(a.taxi_trips) > 0
ORDER BY
    total_complaints DESC;


-------------------------------------------------------------------------------
-- FINDING 9 — WHERE DOES THE DEMAND MODEL PERFORM BEST?
-- We retain total actual demand so very-low-volume zones can be recognized.
-------------------------------------------------------------------------------
SELECT TOP (15)
    z.zone_name,
    z.borough,
    COUNT_BIG(*) AS prediction_rows,
    SUM(p.actual_taxi_trips) AS total_actual_demand,
    CAST(AVG(CAST(ABS(p.predicted_taxi_demand - p.actual_taxi_trips) AS decimal(18,6))) AS decimal(18,4))
        AS mae,
    CAST(
        SQRT(AVG(
            CAST(
                (p.predicted_taxi_demand - p.actual_taxi_trips)
                * (p.predicted_taxi_demand - p.actual_taxi_trips)
                AS float
            )
        ))
        AS decimal(18,4)
    ) AS rmse,
    CAST(
        AVG(CAST(p.predicted_taxi_demand - p.actual_taxi_trips AS decimal(18,6)))
        AS decimal(18,4)
    ) AS mean_bias
FROM dw.FactDemandPrediction p
JOIN dw.DimZone z
    ON z.zone_key = p.zone_key
GROUP BY
    z.zone_name,
    z.borough
ORDER BY
    mae ASC,
    total_actual_demand DESC;


-------------------------------------------------------------------------------
-- FINDING 10 — WHERE DOES THE MODEL STRUGGLE MOST?
-------------------------------------------------------------------------------
SELECT TOP (15)
    z.zone_name,
    z.borough,
    COUNT_BIG(*) AS prediction_rows,
    SUM(p.actual_taxi_trips) AS total_actual_demand,
    CAST(AVG(CAST(ABS(p.predicted_taxi_demand - p.actual_taxi_trips) AS decimal(18,6))) AS decimal(18,4))
        AS mae,
    CAST(
        SQRT(AVG(
            CAST(
                (p.predicted_taxi_demand - p.actual_taxi_trips)
                * (p.predicted_taxi_demand - p.actual_taxi_trips)
                AS float
            )
        ))
        AS decimal(18,4)
    ) AS rmse,
    CAST(
        AVG(CAST(p.predicted_taxi_demand - p.actual_taxi_trips AS decimal(18,6)))
        AS decimal(18,4)
    ) AS mean_bias
FROM dw.FactDemandPrediction p
JOIN dw.DimZone z
    ON z.zone_key = p.zone_key
GROUP BY
    z.zone_name,
    z.borough
ORDER BY
    mae DESC;


-------------------------------------------------------------------------------
-- FINDING 11 — WHICH HOURS ARE HARDEST / EASIEST TO PREDICT?
-------------------------------------------------------------------------------
SELECT
    t.hour_of_day,
    t.daypart,
    COUNT_BIG(*) AS prediction_rows,
    SUM(p.actual_taxi_trips) AS total_actual_demand,
    CAST(AVG(CAST(ABS(p.predicted_taxi_demand - p.actual_taxi_trips) AS decimal(18,6))) AS decimal(18,4))
        AS mae,
    CAST(
        AVG(CAST(p.predicted_taxi_demand - p.actual_taxi_trips AS decimal(18,6)))
        AS decimal(18,4)
    ) AS mean_bias
FROM dw.FactDemandPrediction p
JOIN dw.DimTime t
    ON t.time_key = p.time_key
GROUP BY
    t.hour_of_day,
    t.daypart
ORDER BY
    mae DESC;


-------------------------------------------------------------------------------
-- FINDING 12 — WHICH ZONES HAVE UNUSUAL DEMAND / REVENUE / COMPLAINT MIXES?
-- Rank gaps highlight zones whose complaint or revenue rank differs materially
-- from their demand rank.
-------------------------------------------------------------------------------
WITH zone_totals AS (
    SELECT
        a.zone_key,
        SUM(a.taxi_trips) AS trips,
        SUM(a.taxi_revenue) AS revenue,
        SUM(a.complaints_311) AS complaints
    FROM dw.FactZoneHourlyActivity a
    GROUP BY
        a.zone_key
),
ranked AS (
    SELECT
        zone_key,
        trips,
        revenue,
        complaints,
        RANK() OVER (ORDER BY trips DESC) AS demand_rank,
        RANK() OVER (ORDER BY revenue DESC) AS revenue_rank,
        RANK() OVER (ORDER BY complaints DESC) AS complaint_rank
    FROM zone_totals
)
SELECT TOP (25)
    z.zone_name,
    z.borough,
    r.trips,
    CAST(r.revenue AS decimal(20,2)) AS revenue,
    r.complaints,
    r.demand_rank,
    r.revenue_rank,
    r.complaint_rank,
    ABS(r.complaint_rank - r.demand_rank) AS complaint_demand_rank_gap,
    ABS(r.revenue_rank - r.demand_rank) AS revenue_demand_rank_gap,
    CAST(
        r.revenue / NULLIF(r.trips, 0)
        AS decimal(18,2)
    ) AS revenue_per_trip,
    CAST(
        1000.0 * r.complaints / NULLIF(r.trips, 0)
        AS decimal(18,2)
    ) AS complaints_per_1000_trips
FROM ranked r
JOIN dw.DimZone z
    ON z.zone_key = r.zone_key
WHERE
    r.trips > 0
ORDER BY
    (
        ABS(r.complaint_rank - r.demand_rank)
        +
        ABS(r.revenue_rank - r.demand_rank)
    ) DESC;


-------------------------------------------------------------------------------
-- CONTROL TOTALS — SHOULD MATCH PHASE 39 VALIDATION
-------------------------------------------------------------------------------
SELECT
    SUM(taxi_trips) AS total_taxi_trips,
    CAST(SUM(taxi_revenue) AS decimal(20,2)) AS total_revenue,
    SUM(complaints_311) AS total_complaints,
    COUNT_BIG(*) AS gold_rows
FROM dw.FactZoneHourlyActivity;
