# Phase 26 - Machine Learning Models

Status: VALIDATED

## Objective

Train and compare at least two appropriate machine-learning regression models
for hourly NYC taxi-demand prediction using the same feature set, training
period, test period, and evaluation metrics.

The models are compared against the Phase 25 weekly-naive baseline.

The final Phase 26 candidate is selected from measured performance rather
than from assumptions about which algorithm should perform best.


## Prediction Objective

Prediction grain:

    Taxi Zone x Hour

Target:

    taxi_trips

The task is a supervised regression problem because taxi demand is represented
as a numeric trip count for each zone-hour observation.


## Data Used

Feature source:

    data/gold/ml_features/

Total model-ready observations:

    2,259,696

Training observations:

    1,874,664

Test observations:

    385,032


## Temporal Split

Training period:

    2025-01-08 00:00:00
    through
    2025-10-31 23:00:00

Test period:

    2025-11-01 00:00:00
    through
    2025-12-31 23:00:00

A random train/test split was intentionally not used.

All training observations occur before all test observations.

This preserves the forecasting nature of the problem and prevents future
observations from leaking into model training.


## Features

Both machine-learning models use the same 15 predictors.

### Historical Taxi Demand

    lag_1h
    lag_24h
    lag_168h

These features capture:

    immediate demand persistence
    daily demand seasonality
    weekly demand seasonality


### Calendar Features

    hour
    day_of_week
    month
    is_weekend

These allow the models to learn temporal demand patterns such as:

    morning and evening peaks
    weekday versus weekend behavior
    day-of-week effects
    monthly seasonality


### Location Feature

    taxi_zone_id

Taxi demand differs substantially by location, making zone identity an
important predictor.


### Weather Features

    temperature_c
    rain_mm
    snowfall_cm
    weather_condition

These variables allow the models to learn nonlinear relationships between
weather conditions and transportation demand.


### Urban Activity Features

    complaints_lag_1h
    complaints_lag_24h

Lagged 311 activity provides recent urban-activity context without exposing
the model to the complete complaint count of the prediction hour.


### Additional Categorical Context

    borough

Borough provides broader geographic context in addition to the individual
taxi-zone identifier.


## Leakage Prevention

The following same-hour taxi outcome variables are excluded:

    taxi_revenue
    average_fare
    average_trip_distance

Current-hour:

    complaints_311

is also excluded because its final value would not necessarily be available
when predicting demand at the beginning of the target hour.

The target:

    taxi_trips

is not used as a same-observation predictor.

Historical taxi demand is available only through explicitly lagged features.


# Model Selection Rationale

Two tree-based regression algorithms were selected:

    HistGradientBoostingRegressor
    RandomForestRegressor

These models were selected because the taxi-demand problem has several
properties that favor nonlinear tree-based algorithms.


## Why Tree-Based Models Are Appropriate

Taxi demand is unlikely to have a purely linear relationship with its
predictors.

Examples include:

    demand at 08:00 may behave differently from demand at 14:00
    weekend effects depend on both location and hour
    rain can affect different taxi zones differently
    previous-hour demand can have different effects at low-demand and
    high-demand locations
    borough, zone, weather, and calendar variables interact with each other

Tree-based models can represent these nonlinear relationships and feature
interactions without requiring the analyst to manually specify every
interaction term.

They also do not require standard feature scaling in the way many
distance-based or coefficient-based models do.


# Model 1 - HistGradientBoostingRegressor

## Why HistGradientBoostingRegressor Was Selected

HistGradientBoostingRegressor was selected because it is specifically well
suited to large tabular regression datasets.

The training dataset contains approximately:

    1.87 million observations

Traditional gradient-boosting implementations can become computationally
expensive at this scale.

Histogram-based gradient boosting improves efficiency by grouping continuous
feature values into discrete bins during training.

This can substantially reduce computation while retaining the ability to
learn complex nonlinear relationships.


## Advantages for This Project

HistGradientBoostingRegressor provides several useful characteristics:

    efficient training on large tabular datasets
    strong nonlinear modeling capability
    ability to learn interactions automatically
    relatively low training time
    regularization controls
    effective handling of mixed demand, calendar, location, and weather signals

It is particularly useful as a production-oriented candidate because it can
provide strong predictive accuracy while remaining computationally efficient.


## Phase 26 Configuration

    loss = squared_error
    learning_rate = 0.08
    max_iter = 200
    max_leaf_nodes = 31
    min_samples_leaf = 30
    l2_regularization = 1.0
    random_state = 42


## Measured Training Time

    10.3 seconds


## Performance

MAE:

    4.2347

RMSE:

    12.1401

R?:

    0.9615


## Interpretation

HistGradientBoosting achieved a major improvement over the weekly-naive
baseline while requiring only about ten seconds of model-training time.

This demonstrates a strong accuracy-versus-computation trade-off.


# Model 2 - RandomForestRegressor

## Why RandomForestRegressor Was Selected

Random Forest was selected as a second independent tree-based modeling
approach.

Rather than building trees sequentially like gradient boosting, Random Forest
trains many decision trees using randomized observations and feature subsets
and combines their predictions.

This makes it a useful comparison model because it reaches predictions using
a substantially different ensemble-learning strategy.


## Advantages for This Project

RandomForestRegressor is appropriate because it:

    models nonlinear relationships
    captures complex feature interactions
    requires no feature standardization
    is generally robust to noisy predictors
    combines multiple trees to reduce individual-tree variance
    works well with heterogeneous tabular features
    provides a useful later path for feature-importance analysis

Taxi demand depends on many interacting effects involving:

    previous demand
    zone
    hour
    weekday
    weather
    borough
    urban activity

Random Forest can capture these relationships without requiring manually
specified interaction equations.


## Resource-Aware Configuration

The dataset is large and the development machine has:

    6 logical CPUs

The Random Forest was therefore deliberately constrained rather than using
an unrestricted forest.

Configuration:

    n_estimators = 50
    max_depth = 18
    min_samples_leaf = 5
    max_features = 0.75
    bootstrap = True
    max_samples = 0.70
    n_jobs = 5
    random_state = 42

Using:

    n_jobs = 5

allows parallel tree training while leaving some system capacity available.

The restricted tree depth and training sample fraction also prevent excessive
memory and CPU consumption.


## Measured Training Time

    92.1 seconds


## Performance

MAE:

    4.1399

RMSE:

    12.0792

R?:

    0.9618


# Why Linear Regression and Ridge Regression Were Not Selected

Linear Regression and Ridge Regression were valid candidate algorithms, but
they were not selected as the primary Phase 26 models.

The reason is that the expected structure of taxi demand is highly nonlinear.

A basic linear model assumes largely additive linear relationships unless
interaction terms and nonlinear transformations are engineered explicitly.

For example, the effect of:

    hour

may depend on:

    taxi zone
    weekday
    weekend status
    weather

Similarly, the relationship between previous taxi demand and future demand
may differ substantially between high-volume Manhattan zones and low-volume
outer-borough zones.

Representing those relationships with linear models would require substantial
manual feature engineering.

HistGradientBoosting and Random Forest can learn many of these nonlinear
relationships and interactions directly.

Linear and Ridge Regression remain useful simpler benchmark algorithms, but
Phase 26 required at least two appropriate models rather than every possible
candidate.


# Model Comparison

Measured results on the identical November-December holdout set:

| Model | MAE | RMSE | R? | Training Time |
| --- | ---: | ---: | ---: | ---: |
| Weekly Naive Baseline | 6.7707 | 22.9201 | 0.8626 | 0.0 s |
| HistGradientBoosting | 4.2347 | 12.1401 | 0.9615 | 10.3 s |
| Random Forest | 4.1399 | 12.0792 | 0.9618 | 92.1 s |


# Baseline Improvement

Random Forest versus weekly-naive baseline:

MAE improvement:

    38.86%

RMSE improvement:

    47.30%

The Random Forest therefore reduces both primary error measures substantially.


# Final Phase 26 Model Selection

Selected ML model:

    RandomForestRegressor

The selection is based on measured test-set performance.

Random Forest achieved:

    lowest MAE
    lowest RMSE
    highest R?

among the three evaluated approaches.


## Why Random Forest Was Selected Despite Longer Training Time

HistGradientBoosting trained substantially faster:

    HistGradientBoosting: approximately 10.3 seconds
    Random Forest:        approximately 92.1 seconds

However, Random Forest produced the best measured predictive accuracy:

    HGB MAE: 4.2347
    RF MAE:  4.1399

    HGB RMSE: 12.1401
    RF RMSE:  12.0792

For Phase 26, model selection is based primarily on predictive performance,
therefore Random Forest is selected as the leading ML candidate.

HistGradientBoosting remains operationally important because its accuracy is
very close to Random Forest while its training cost is much lower.

If production latency, retraining frequency, or computing cost later becomes
a stronger constraint, HistGradientBoosting could therefore be reconsidered.


# Validation

Independent Phase 26 validation confirmed:

    Prediction rows:          385,032
    Taxi zones:               263
    Duplicate predictions:    0
    Null values:              0

First test timestamp:

    2025-11-01 00:00:00

Last test timestamp:

    2025-12-31 23:00:00

Recalculated metrics matched the stored model-comparison report.


## Validated Metrics

Weekly Naive Baseline:

    MAE:   6.7707
    RMSE: 22.9201
    R?:    0.8626

HistGradientBoosting:

    MAE:   4.2347
    RMSE: 12.1401
    R?:    0.9615

Random Forest:

    MAE:   4.1399
    RMSE: 12.0792
    R?:    0.9618


Validation result:

    PHASE26_MODEL_VALIDATION_SUCCESS


# Generated Artifacts

Training and model-comparison code:

    model/train_ml_models.py

Independent validation:

    model/validate_ml_models.py

Comparison evidence:

    reports/model_comparison_metrics.csv

Generated prediction dataset:

    data/gold/model_predictions/phase26_model_predictions.parquet

Serialized preprocessing artifact:

    data/models/phase26/categorical_encoder.joblib

Serialized HistGradientBoosting model:

    data/models/phase26/hist_gradient_boosting.joblib

Serialized Random Forest model:

    data/models/phase26/random_forest.joblib


The generated Parquet and serialized model files are runtime/data artifacts
and are not intended to be committed to Git.


# Result

Phase 26 successfully trained and evaluated two machine-learning models using
the same feature set and temporal holdout.

Both machine-learning models substantially outperform the Phase 25 baseline.

RandomForestRegressor produced the strongest measured predictive accuracy and
is therefore the selected Phase 26 ML candidate.

Status:

    VALIDATED
