# Phase 13 — Combined Gold Analytical Dataset

## Status

COMPLETE

## Objective

Create a consolidated analytical Gold dataset combining:

- NYC Yellow Taxi activity
- NYC 311 complaints
- Open-Meteo weather
- TLC Taxi Zone geography

The Gold dataset is designed for downstream SQL warehouse, machine learning, Power BI, and analytical workloads.

## Gold Dataset

Location:

`data/gold/zone_hourly/year=2025/month=MM`

Gold table:

`zone_hourly`

## Grain

The authoritative Gold grain is:

`1 row = 1 NYC local Date + 1 Hour + 1 authoritative TLC Taxi Zone`

Join key:

- `date`
- `hour`
- `taxi_zone_id`

The dataset is a dense zone-hourly grid.

## Full-Year Grid

Calendar year 2025 contains:

`8,760`

hours.

Authoritative TLC polygon Taxi Zones:

`263`

Therefore expected Gold rows:

`8,760 × 263 = 2,303,880`

Observed Gold rows:

`2,303,880`

Result:

`PASS`

## Authoritative Taxi Zone Domain

The Gold spatial domain includes only polygon-backed TLC Taxi Zone LocationIDs:

`1–263`

Taxi Zone lookup special values:

- `264 = Unknown`
- `265 = Outside of NYC`

These are not authoritative Taxi Zone polygons and are excluded from the spatial Gold table.

They remain explicitly reconciled rather than silently dropped.

Full-year Taxi special-ID exclusions:

`103,042`

## Zero-Trip Authoritative Zones

Three valid polygon Taxi Zones had no Yellow Taxi pickup trips during 2025:

- LocationID 103
- LocationID 104
- LocationID 110

These zones remain in the dense Gold grid.

Each contains:

`8,760`

zone-hour rows.

Observed Taxi trip counts:

- Zone 103: 0
- Zone 104: 0
- Zone 110: 0

Observed mapped 311 complaints:

- Zone 103: 4
- Zone 104: 0
- Zone 110: 56

This preserves the authoritative spatial domain even when Taxi activity is zero.

## Taxi Aggregation

Taxi geography is based on:

`PULocationID`

Taxi aggregation grain:

`pickup_date + pickup_hour + PULocationID`

### Taxi Trip Count

Definition:

`COUNT(*)`

Gold field:

`taxi_trips`

Full-year authoritative-zone Taxi trips:

`48,617,295`

### Revenue Definition

Gold Taxi revenue is defined as:

`SUM(total_amount)`

Gold field:

`taxi_revenue`

Full-year Gold Taxi revenue:

`1,306,369,662.27`

This revenue includes only trips whose pickup LocationID is an authoritative polygon-backed Taxi Zone in the range 1–263.

### Average Fare

Definition:

`AVG(fare_amount)`

Gold field:

`average_fare`

When a zone-hour contains no Taxi trips:

`average_fare = NULL`

It is not replaced with zero because an average fare is undefined when no trips occurred.

### Average Trip Distance

Definition:

`AVG(trip_distance)`

Gold field:

`average_trip_distance`

When a zone-hour contains no Taxi trips:

`average_trip_distance = NULL`

## Taxi Temporal Routing

The physical monthly Taxi Silver partition is not treated as authoritative for Gold month assignment.

Gold month membership is determined by:

`pickup_date`

A full-year audit identified:

`185`

Taxi Silver records physically stored in an adjacent monthly partition while their actual pickup timestamp belonged to another month.

Observed:

- Cross-partition Taxi rows: 185
- Outside calendar year 2025: 0

These rows are routed to their true event month using `pickup_date`.

No cross-partition Taxi record is silently deleted.

This corrected the original January reconciliation where one February 1 trip was physically stored in the January source partition.

## Taxi Full-Year Reconciliation

Total Taxi Silver rows:

`48,720,337`

Authoritative Taxi Zone rows 1–263:

`48,617,295`

Taxi rows with LocationID 264/265:

`103,042`

Other invalid Taxi LocationIDs:

`0`

Reconciliation:

`48,617,295 + 103,042 = 48,720,337`

Result:

`PASS`

## 311 Aggregation

311 source:

`data/silver/complaints_311_mapped/year=2025/month=MM`

Only complaints with:

`spatial_mapping_status = MAPPED`

are included in zone-level Gold aggregation.

Aggregation grain:

`created_date + created hour + taxi_zone_location_id`

Definition:

`COUNT(*)`

Gold field:

`complaints_311`

Full-year mapped complaint count:

`3,603,396`

311 valid Silver input:

`3,604,061`

Outside Taxi Zone polygons:

`665`

Reconciliation:

`3,603,396 + 665 = 3,604,061`

Result:

`PASS`

The 665 spatially outside complaints are not forced into a Taxi Zone.

## Weather Integration

Weather source:

`data/silver/weather/year=2025/month=MM`

Weather grain:

`1 row per NYC local hour`

Fields joined into Gold:

- `temperature_c`
- `rain_mm`
- `snowfall_cm`
- `weather_condition`

Weather is citywide and therefore repeated across all 263 Taxi Zones for each hour.

Full-year Weather rows:

`8,760`

Unique hourly Weather observations in Gold:

`8,760`

Weather-null Gold cells:

`0`

Weather join result:

`PASS`

Weather values are never silently imputed.

Missing Weather hours would cause Gold publication failure.

## Gold Measures

Core Gold fields include:

- `date`
- `hour`
- `taxi_zone_id`
- `taxi_zone_name`
- `borough`
- `taxi_trips`
- `taxi_revenue`
- `average_fare`
- `average_trip_distance`
- `complaints_311`
- `temperature_c`
- `rain_mm`
- `snowfall_cm`
- `weather_condition`

Audit metadata is also retained.

## Dense Grid Rules

Every valid Taxi Zone polygon exists for every hour in 2025.

For zone-hours with no Taxi activity:

- `taxi_trips = 0`
- `taxi_revenue = 0`
- `average_fare = NULL`
- `average_trip_distance = NULL`

For zone-hours with no 311 complaints:

`complaints_311 = 0`

Weather remains populated for every Gold row.

## Full-Year Key Audit

Gold rows:

`2,303,880`

Duplicate Gold keys:

`0`

Unique Taxi Zones:

`263`

Minimum Taxi Zone ID:

`1`

Maximum Taxi Zone ID:

`263`

Unique date-hours:

`8,760`

Minimum zones per hour:

`263`

Maximum zones per hour:

`263`

Gold grain audit:

`PASS`

## Zero-Activity Audit

Zone-hours with zero Taxi trips:

`888,975`

Zero-trip rows containing non-null average fare:

`0`

Zero-trip rows containing non-null average trip distance:

`0`

Average-null audit:

`PASS`

## Full-Year Reconciliation

| Metric | Value |
|---|---:|
| Taxi Silver rows | 48,720,337 |
| Taxi Gold-domain rows | 48,617,295 |
| Taxi cross-partition rows routed | 185 |
| Taxi special 264/265 exclusions | 103,042 |
| 311 mapped complaints | 3,603,396 |
| 311 outside-polygon exclusions | 665 |
| Weather hours | 8,760 |
| Gold rows | 2,303,880 |

Reconciliation result:

`PASS`

## Physical Reconciliation

Monthly Gold partitions:

`12`

Physical Gold rows:

`2,303,880`

Expected Gold rows:

`2,303,880`

Physical audit:

`PASS`

## Implementation

Gold builder:

`python/build_gold_zone_hourly.py`

Gold output:

`data/gold/zone_hourly/year=2025/month=MM`

Monthly reconciliation:

`reports/reconciliation/gold_zone_hourly_reconciliation.csv`

Full-year summary:

`reports/gold/phase13_zone_hourly_summary.json`

Pipeline audit log:

`logs/pipeline_runs.jsonl`

## Final Result

Phase 13 is COMPLETE.

The project now contains a fully reconciled, dense, zone-hourly analytical Gold dataset combining:

- Taxi activity
- Taxi revenue
- Taxi fares
- Taxi trip distance
- mapped 311 complaints
- hourly Weather
- authoritative TLC Taxi Zone geography

Final Gold rows:

`2,303,880`

Final reconciliation:

`PASS`
