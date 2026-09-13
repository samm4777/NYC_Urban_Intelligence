# Phase 24 - Taxi Demand Prediction Setup

Status: VALIDATED

## Objective

Prepare a leakage-safe machine-learning feature dataset for hourly NYC taxi
demand prediction.

## Prediction Grain

    Taxi Zone x Hour

Each observation represents one authoritative TLC Taxi Zone during one hour.

## Target

    taxi_trips

The prediction objective is the number of taxi pickups occurring in a zone
during the target hour.

## Source

    data/gold/zone_hourly/

Source Gold grain:

    Date x Hour x Taxi Zone

Source rows:

    2,303,880

Source coverage:

    263 authoritative taxi zones
    365 dates
    8,760 hours per zone
    January 2025 through December 2025

## Feature Dataset

Output:

    data/gold/ml_features/

Partitioning:

    year=2025/month=MM

Model-ready rows:

    2,259,696

The first seven days per zone are excluded from the model-ready feature
dataset because the longest demand lag is 168 hours.

Warm-up rows:

    44,184

Calculation:

    263 zones x 168 hours = 44,184

## Historical Demand Features

    lag_1h
    lag_24h
    lag_168h

These represent demand:

    1 hour earlier
    24 hours earlier
    168 hours earlier

## Calendar Features

    hour
    day_of_week
    month
    year
    is_weekend

Day-of-week convention:

    Monday = 0
    Sunday = 6

## Location Features

    taxi_zone_id
    taxi_zone_name
    borough

## Weather Features

    temperature_c
    rain_mm
    snowfall_cm
    weather_condition

Historical observed weather is used during development.

Operational future prediction would require corresponding forecast weather
for the prediction horizon.

## Urban Activity Features

    complaints_lag_1h
    complaints_lag_24h

Current-hour complaints_311 is intentionally excluded from the ML feature
dataset to avoid depending on information that may not yet be available at
prediction time.

## Leakage Prevention

The following same-hour outcome variables are excluded:

    taxi_revenue
    average_fare
    average_trip_distance
    complaints_311

The target:

    taxi_trips

is retained only as the supervised-learning target and is never used as a
same-observation predictor.

Historical taxi demand enters the feature set only through lag variables.

## Validation Results

Feature validation confirmed:

    Model-ready rows:       2,259,696
    Zones:                  263
    Months:                 12
    Duplicate zone-hours:   0
    Null lag values:        0

First model-ready timestamp:

    2025-01-08 00:00:00

Last model-ready timestamp:

    2025-12-31 23:00:00

Rows per zone:

    8,592

## Monthly Model-Ready Rows

    January       151,488
    February      176,736
    March         195,672
    April         189,360
    May           195,672
    June          189,360
    July          195,672
    August        195,672
    September     189,360
    October       195,672
    November      189,360
    December      195,672

## Lag Alignment Validation

Lag correctness was independently validated against the original Gold data.

Representative zones:

    1
    132
    263

Rows compared:

    25,776

Validated fields:

    lag_1h
    lag_24h
    lag_168h
    complaints_lag_1h
    complaints_lag_24h

All values matched their corresponding historical Gold records.

Result:

    PHASE24_LAG_ALIGNMENT_SUCCESS

## Time-Based Modeling Requirement

The feature dataset preserves chronological ordering.

Future model phases must not randomly mix future observations into historical
training data.

Planned candidate split:

    Training:
    January 2025 through October 2025

    Testing:
    November 2025 through December 2025

The final train/test design will be implemented in the dedicated time-based
testing phase.

## Files

Feature specification:

    model/feature_spec.md

Feature builder:

    model/build_demand_features.py

Dataset validator:

    model/validate_demand_features.py

Lag-alignment validator:

    model/validate_lag_alignment.py

## Result

Phase 24 now provides a validated, full-year, leakage-aware feature dataset
at Taxi Zone x Hour grain for the subsequent baseline and machine-learning
model phases.

Status:

    VALIDATED
