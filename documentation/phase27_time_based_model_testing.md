# Phase 27 - Time-Based Model Testing and Leakage Validation

Status: VALIDATED

## Objective

Verify that taxi-demand model evaluation follows a true temporal forecasting
design and that historical and future observations are never randomly mixed.

Phase 27 also verifies that all lagged predictors contain only information
that existed before each prediction timestamp.


## Prediction Protocol

The project uses:

    Rolling Hourly Forecasting

For every target hour t, the model may use information observed strictly
before t.

Examples:

    lag_1h   = observed demand at t - 1 hour
    lag_24h  = observed demand at t - 24 hours
    lag_168h = observed demand at t - 168 hours

This is different from predicting the entire November-December period once
on October 31.

Under the rolling-hour protocol, newly observed historical information may
become available for subsequent hourly predictions.


## Temporal Dataset Split

The model-ready feature dataset contains:

    2,259,696 rows

Training period:

    2025-01-08 00:00:00
    through
    2025-10-31 23:00:00

Training observations:

    1,874,664


Testing period:

    2025-11-01 00:00:00
    through
    2025-12-31 23:00:00

Testing observations:

    385,032


All training records occur before all testing records.

Result:

    Train/test temporal overlap: NONE

No random train/test split is used.


## Why Random Splitting Was Avoided

Randomly distributing zone-hour observations between training and testing
could allow future records to influence a model that is evaluated on earlier
records.

For time-series forecasting, this would produce an unrealistic evaluation
and could overstate model performance.

The project therefore preserves chronological ordering throughout model
testing.


# Historical Feature Leakage Audit

The Phase 27 validator independently reconstructed lagged variables directly
from the original full-year Gold dataset.

Gold source:

    data/gold/zone_hourly/

Gold observations:

    2,303,880

The Gold source was first validated as a complete hourly grid.

Validation confirmed:

    263 taxi zones
    continuous hourly ordering
    no duplicate zone-hours
    no unexpected hourly gaps


## Full-Dataset Lag Validation

All model-ready rows were independently checked.

Rows audited:

    2,259,696

Results:

    lag_1h:                 FULL-DATA PASS
    lag_24h:                FULL-DATA PASS
    lag_168h:               FULL-DATA PASS
    complaints_lag_1h:      FULL-DATA PASS
    complaints_lag_24h:     FULL-DATA PASS

This proves that the stored feature values match the corresponding historical
records in the original Gold dataset.


# First Test-Hour Boundary Check

First prediction timestamp:

    2025-11-01 00:00:00

Historical source timestamps:

    lag_1h:
    2025-10-31 23:00:00

    lag_24h:
    2025-10-31 00:00:00

    lag_168h:
    2025-10-25 00:00:00

Every lag source is earlier than the target timestamp.


# Same-Hour Leakage Prevention

The ML feature dataset intentionally excludes same-hour variables that would
not reliably be known at prediction time.

Excluded:

    taxi_revenue
    average_fare
    average_trip_distance
    complaints_311

The prediction target:

    taxi_trips

is never used as a same-hour predictor.

Taxi demand enters the predictor set only through historical lag variables.


# 311 Complaint Features

Current-hour:

    complaints_311

is excluded.

Only historical complaint information is used:

    complaints_lag_1h
    complaints_lag_24h

This ensures that final complaint counts from the target hour are not exposed
to the model.


# Weather Feature Assumption

The current model-development dataset contains observed weather for the target
hour:

    temperature_c
    rain_mm
    snowfall_cm
    weather_condition

For historical offline evaluation, these fields are treated as proxies for
weather information that would be available through a weather forecast in an
operational system.

This assumption is explicitly documented.

A production forecasting implementation should obtain forecast weather known
at prediction time rather than future observed weather.

Therefore, the Phase 27 leakage conclusion for taxi-demand and 311 lag
features is exact, while target-hour weather relies on the documented
forecast-availability assumption.


# Relationship to Phase 26 Performance

Phase 26 selected:

    RandomForestRegressor

Measured November-December holdout performance:

    MAE:   4.1399
    RMSE: 12.0792
    R?:    0.9618

Phase 27 does not retrain or optimize the model.

Its purpose is to validate that the evaluation design and historical lag
features do not mix future target information into model training or
prediction.

The Phase 26 results can therefore be described as performance on a future
chronological holdout under the project's rolling-hour forecasting protocol.


# Important Interpretation of R?

The model achieved:

    R? = 0.9618

This means approximately 96.18% of the variation in taxi demand within the
evaluated holdout is explained by the fitted model.

It should not be described as:

    96.18% classification accuracy

because taxi-demand prediction is a regression problem.


# Validation Evidence

Phase 27 validator:

    model/validate_time_based_testing.py

Validated:

    Gold rows:                    2,303,880
    Model-ready rows:             2,259,696
    Training rows:                1,874,664
    Testing rows:                   385,032
    Train/test overlap:           NONE
    Random temporal mixing:       NONE
    Same-hour outcome leakage:    NONE

All five historical lag variables passed full-dataset source reconciliation.

Final validator result:

    PHASE27_TIME_BASED_TESTING_SUCCESS


# Result

Phase 27 confirms that model testing follows chronological ordering and that
historical taxi-demand and 311 lag features contain only information from
timestamps earlier than their prediction target.

No random historical/future mixing was detected.

No same-hour taxi outcome or current-hour 311 leakage was detected.

The model evaluation therefore satisfies the project's time-based testing
requirement under the documented rolling-hour forecast design.

Status:

    VALIDATED
