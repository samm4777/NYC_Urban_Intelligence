# Phase 25 - Baseline Taxi Demand Model

Status: VALIDATED

## Objective

Establish a simple, reproducible demand-prediction baseline before training
machine-learning models.

The baseline provides the minimum performance that later ML models must beat.

## Baseline Model

Model:

    Weekly Naive Baseline

Prediction rule:

    predicted demand = demand for the same taxi zone and hour
                       168 hours earlier

Feature used:

    lag_168h

This provides a strong seasonal baseline because NYC taxi demand commonly
varies by both hour-of-day and day-of-week.

## Prediction Grain

    Taxi Zone x Hour

Target:

    taxi_trips

## Evaluation Period

The baseline is evaluated on the future holdout period:

    2025-11-01 00:00:00
    through
    2025-12-31 23:00:00

Test days:

    61

Taxi zones:

    263

Expected observations:

    61 days
    x 24 hours
    x 263 zones
    = 385,032

Actual observations:

    385,032

## Metrics

MAE:

    6.7707

RMSE:

    22.9201

R?:

    0.8626

Primary model-selection metrics for later phases:

    MAE
    RMSE

R? is retained as a supporting metric.

## Interpretation

MAE = 6.7707 means that, on average, the weekly-naive prediction differs
from observed hourly taxi demand by approximately 6.77 trips per zone-hour.

RMSE = 22.9201 gives greater weight to larger prediction errors and therefore
shows that some zone-hour combinations contain substantially larger misses
than the typical absolute error.

R? = 0.8626 indicates that the weekly seasonal baseline explains a large
share of observed variation in taxi demand.

This makes the baseline deliberately meaningful rather than trivial.

Subsequent machine-learning models must be compared against the same
holdout period and should improve primarily on MAE and RMSE.

## Validation

The independently validated prediction output contains:

    Prediction rows:          385,032
    Taxi zones:               263
    Test days:                61
    Duplicate zone-hours:     0
    Null actual values:       0
    Null predictions:         0

First timestamp:

    2025-11-01 00:00:00

Last timestamp:

    2025-12-31 23:00:00

Metrics were independently recalculated from the generated prediction file
and matched the baseline execution results:

    MAE:   6.7707
    RMSE: 22.9201
    R?:    0.8626

Validation result:

    PHASE25_BASELINE_VALIDATION_SUCCESS

## Artifacts

Baseline implementation:

    model/baseline_model.py

Baseline validation:

    model/validate_baseline_model.py

Metrics evidence:

    reports/baseline_model_metrics.csv

Generated baseline predictions:

    data/gold/baseline_predictions/weekly_naive_baseline.parquet

The generated prediction dataset remains in the data layer and is not
committed to Git.

## Future Model Comparison

Phase 26 models will be evaluated using the same future holdout period and
the same principal metrics.

Baseline to beat:

    MAE  < 6.7707
    RMSE < 22.9201

The final model will not be selected merely because it has a higher R?.
MAE, RMSE, consistency, and later time-based evaluation will all be considered.

## Result

A reproducible and independently validated weekly-naive taxi-demand baseline
has been established.

Status:

    VALIDATED
