# Phase 24 - Taxi Demand Prediction Feature Specification

## Prediction Objective

Predict hourly NYC Yellow Taxi demand.

## Prediction Grain

    Taxi Zone x Hour

Each observation represents one authoritative TLC Taxi Zone during one
hour of 2025.

Source Gold grain:

    Date x Hour x Taxi Zone

Expected source observations:

    365 days
    x 24 hours
    x 263 zones
    = 2,303,880 rows

## Target

    taxi_trips

The model predicts the number of taxi pickups in a zone during the target
hour.

## Time Key

A timestamp is constructed from:

    date + hour

All lag calculations are ordered by this timestamp within each taxi zone.

## Model Features

### Historical Demand

    lag_1h
    lag_24h
    lag_168h

Definitions:

    lag_1h   = taxi demand one hour earlier
    lag_24h  = taxi demand at the same relative hour one day earlier
    lag_168h = taxi demand at the same relative hour one week earlier

These values use only historical demand and therefore avoid target leakage.

### Calendar

    hour
    day_of_week
    month
    is_weekend

day_of_week convention:

    Monday = 0
    Sunday = 6

### Location

    taxi_zone_id
    borough

### Weather

    temperature_c
    rain_mm
    snowfall_cm
    weather_condition

Historical observed weather is used during model development.

For future operational prediction, equivalent forecast weather would need
to be available for the prediction hour.

### 311 Urban Activity

    complaints_lag_1h
    complaints_lag_24h

Current-hour complaints_311 is excluded from the ML feature dataset because
the full complaint count may not be known when the target-hour prediction
is generated. Historical complaint activity is represented through lagged
features instead.

## Explicit Leakage Exclusions

The following Gold columns are not predictive features:

    taxi_revenue
    average_fare
    average_trip_distance

They are outcomes associated with taxi activity in the target hour.

The target itself:

    taxi_trips

is never used directly as an input feature for the same observation.

## Lag Warm-Up

lag_168h requires seven days of historical observations.

With 263 zones:

    263 x 168 = 44,184

initial zone-hour observations cannot have a complete weekly lag.

Expected model-ready rows:

    2,303,880 - 44,184
    = 2,259,696

The source Gold dataset remains unchanged.

## Time-Based Modeling

Rows must never be randomly shuffled before train/test splitting.

Later phases will use historical time ordering, with a candidate split such as:

    Training: January through October 2025
    Testing:  November through December 2025

This prevents future observations from leaking into historical training data.

## Output

Feature dataset:

    data/gold/ml_features/

Partitioned by:

    year
    month

Feature-building code:

    model/build_demand_features.py

