# Phase 28 - Model Evaluation

Status: VALIDATED

## Objective

Evaluate the selected Random Forest taxi-demand model beyond a single overall
score and determine where the model performs well, where it performs poorly,
and what factors may explain the observed error patterns.

The model is evaluated on the same chronological holdout used in Phases 26
and 27.

Test period:

    2025-11-01 00:00:00
    through
    2025-12-31 23:00:00

Test observations:

    385,032

Taxi zones:

    263


# Primary and Supporting Metrics

Primary metrics:

    MAE
    RMSE

Supporting metric:

    R?

Additional diagnostic metrics:

    MAPE on observations where actual demand > 0
    sMAPE
    mean prediction-error bias


## Why MAE and RMSE Are Primary

Taxi-demand prediction is a regression problem.

MAE provides an intuitive measure of the average absolute difference between
predicted and observed taxi trips.

RMSE gives greater weight to large prediction errors and is therefore useful
for identifying whether occasional large misses remain important.

These two metrics are used as the principal measures of forecasting error.


## Why R? Is Supporting Rather Than Primary

R? measures how much of the observed variation in taxi demand is explained by
the model.

It is useful as an overall goodness-of-fit measure but does not directly state
the typical number of trips by which a prediction is wrong.

For operational forecasting, MAE and RMSE therefore remain more directly
interpretable.


# Overall Model Performance

Selected model:

    RandomForestRegressor

Observations:

    385,032

MAE:

    4.1399 trips

RMSE:

    12.0792 trips

R?:

    0.9618

MAPE where actual demand > 0:

    47.97%

sMAPE:

    101.33%

Mean prediction-error bias:

    +0.4635 trips


## Overall Interpretation

The model differs from observed demand by approximately:

    4.14 trips per zone-hour

on average.

RMSE is higher than MAE:

    MAE  = 4.1399
    RMSE = 12.0792

which indicates that some observations contain substantially larger errors
than the typical prediction.

R? = 0.9618 means that approximately 96.18% of the variation in demand within
the chronological holdout is explained by the model.

This must not be described as 96.18% classification accuracy because this is
a regression problem.

The overall mean-error bias is only:

    +0.4635 trips

indicating a small overall tendency toward overprediction rather than a large
systematic forecasting bias.


# Evaluation by Taxi Zone

All:

    263 zones

were evaluated independently.


## Lowest Absolute-Error Zones

Examples of lowest-MAE zones:

    Great Kills Park
        MAE  = 0.0020
        RMSE = 0.0029

    Governor's Island/Ellis Island/Liberty Island
        Zone 103
        MAE  = 0.0022
        RMSE = 0.0025

    Governor's Island/Ellis Island/Liberty Island
        Zone 104
        MAE  = 0.0022
        RMSE = 0.0025

    Freshkills Park
        MAE  = 0.0031
        RMSE = 0.0041


## Interpretation of Very Low Zone Errors

These extremely small errors must be interpreted together with demand volume.

Many of these zones have almost no taxi pickups.

Predicting approximately zero demand in a location where actual demand is
usually approximately zero naturally produces a very small absolute error.

Therefore, these zones should not be interpreted as evidence that the model
has solved the most difficult demand patterns.

They are predominantly low-volume forecasting cases.


## Highest Absolute-Error Zones

The largest MAEs were observed in:

    JFK Airport
        MAE  = 41.8402
        RMSE = 58.8362

    LaGuardia Airport
        MAE  = 35.8586
        RMSE = 53.3461

    Upper East Side South
        MAE  = 31.5419
        RMSE = 46.4566

    Penn Station/Madison Sq West
        MAE  = 31.1510
        RMSE = 43.8664

    Upper East Side North
        MAE  = 30.0354
        RMSE = 44.0555


## Why These Zones Are More Difficult

These locations are high-demand and highly dynamic transportation zones.

Possible causes of larger errors include:

    airport arrival and departure waves
    flight delays
    commuter surges
    rail activity
    major events
    congestion
    localized weather effects
    holidays
    irregular passenger movements
    abrupt short-term changes not fully represented by lag variables

The current feature set contains strong historical, calendar, location,
weather, and 311 signals, but it does not directly contain variables such as:

    airline schedules
    real-time flight delays
    train schedules
    event calendars
    real-time traffic congestion

These missing short-term drivers may contribute to the larger errors in major
transportation hubs.


# Evaluation by Hour of Day

Each hour contains:

    16,043 observations

representing all 263 zones across the 61-day test period.


## Lowest-MAE Hours

The three lowest-MAE hours were:

    03:00
        MAE  = 1.8141
        RMSE = 6.6851

    04:00
        MAE  = 1.8239
        RMSE = 5.4810

    05:00
        MAE  = 1.8845
        RMSE = 4.0787


## Highest-MAE Hours

The three highest-MAE hours were:

    19:00
        MAE  = 5.9110
        RMSE = 16.0244

    21:00
        MAE  = 5.8972
        RMSE = 17.1617

    22:00
        MAE  = 5.8312
        RMSE = 16.9859


## Hourly Interpretation

Overnight demand is generally lower.

At 03:00:

    mean actual demand = approximately 5.11 trips

while at 18:00:

    mean actual demand = approximately 36.32 trips

and at 19:00:

    mean actual demand = approximately 32.63 trips

Absolute forecasting error naturally tends to increase when more trips are
being predicted.

Evening demand may also be more variable because it is influenced by:

    commuting
    nightlife
    events
    restaurants and entertainment
    airport activity
    congestion
    weather changes

The model therefore performs best in absolute terms during low-demand
overnight periods and faces greater absolute error during busy evening hours.


# Evaluation by Day of Week

## Best Day by MAE

Monday:

    MAE  = 3.6044
    RMSE = 10.6952
    R?   = 0.9666


## Worst Day by MAE

Thursday:

    MAE  = 4.6864
    RMSE = 13.3865
    R?   = 0.9586


## Complete Pattern

Monday:

    MAE = 3.6044

Tuesday:

    MAE = 3.7219

Wednesday:

    MAE = 3.9835

Thursday:

    MAE = 4.6864

Friday:

    MAE = 4.2772

Saturday:

    MAE = 4.6085

Sunday:

    MAE = 4.1734


## Day-of-Week Interpretation

Performance remains strong across all seven days.

The higher Thursday and Saturday absolute errors may reflect greater
variability in travel behavior than the historical lag features fully capture.

Potential influences include:

    changing commuter patterns
    social and entertainment travel
    events
    airport travel
    week-specific variation

No day shows evidence of catastrophic model failure.

All daily R? values remain approximately:

    0.952 to 0.969


# Evaluation by Actual Demand Level

Demand was divided into interpretable fixed bands:

    Zero:
        0 trips

    Very Low:
        1-5 trips

    Low:
        6-20 trips

    Moderate:
        21-50 trips

    High:
        51-100 trips

    Very High:
        101+ trips


## Zero Demand

Observations:

    141,563

MAE:

    0.5329

RMSE:

    1.0884

Mean bias:

    +0.5329

MAPE:

    Not calculated

because actual demand equals zero.


## Very Low Demand - 1 to 5 Trips

Observations:

    130,562

Mean actual demand:

    2.20

MAE:

    1.2871

MAPE:

    65.88%


## Low Demand - 6 to 20 Trips

Observations:

    49,078

Mean actual demand:

    10.59

MAE:

    3.8108

MAPE:

    37.58%


## Moderate Demand - 21 to 50 Trips

Observations:

    20,498

Mean actual demand:

    32.65

MAE:

    8.4634

MAPE:

    26.37%


## High Demand - 51 to 100 Trips

Observations:

    15,497

Mean actual demand:

    73.50

MAE:

    14.3760

MAPE:

    19.91%

Mean bias:

    +4.6439 trips


## Very High Demand - 101+ Trips

Observations:

    27,834

Mean actual demand:

    210.32

MAE:

    27.5642

RMSE:

    39.9237

MAPE:

    13.82%

Mean bias:

    -0.8724 trips


# Absolute Error Versus Relative Error

A major finding is that absolute and relative error move differently as demand
increases.

Absolute MAE increases:

    Zero demand        0.53
    1-5 trips          1.29
    6-20 trips         3.81
    21-50 trips        8.46
    51-100 trips      14.38
    101+ trips        27.56

This is expected because forecasting a zone-hour containing hundreds of taxi
trips creates more opportunity for a large absolute deviation.

However, positive-demand MAPE decreases substantially:

    1-5 trips         65.88%
    6-20 trips        37.58%
    21-50 trips       26.37%
    51-100 trips      19.91%
    101+ trips        13.82%

Therefore, the model is proportionally more accurate on very high-demand
observations even though their absolute errors are larger.


# Why Overall MAPE Is Not the Primary Metric

Overall positive-demand MAPE is:

    47.97%

This value may initially appear high.

However, the test dataset contains a very large number of low-demand
observations.

For example:

    actual demand = 1 trip
    prediction    = 2 trips

produces:

    absolute error = 1 trip

but:

    percentage error = 100%

Thus, MAPE can heavily penalize small absolute deviations when actual demand
is close to zero.

For this reason:

    MAE
    RMSE

remain the primary project metrics.


# Why MAPE Is Excluded for Zero Demand

Normal MAPE divides prediction error by actual demand.

When:

    actual demand = 0

the denominator is zero and normal MAPE is undefined.

The Phase 28 implementation therefore computes MAPE only where:

    actual demand > 0

The validator independently confirmed that zero-demand MAPE is not calculated.


# sMAPE Interpretation

Overall sMAPE:

    101.33%

This value is also strongly affected by zero-demand observations.

There are:

    141,563

zero-demand zone-hours.

When:

    actual demand = 0

and the model predicts a positive value, sMAPE can reach:

    200%

Consequently, overall sMAPE is not used as the headline model-performance
measure.

It remains available as a diagnostic metric.


# Prediction Bias

Overall mean error:

    predicted - actual

equals:

    +0.4635 trips

This indicates a small overall overprediction tendency.

The bias varies by demand level.

For high demand of 51-100 trips:

    mean bias = +4.6439

indicating overprediction.

For very high demand of 101+ trips:

    mean bias = -0.8724

indicating slight underprediction.

These subgroup effects largely offset each other in the overall metric.


# Where the Model Performs Well

The model performs particularly well when:

    demand is low and stable
    the zone has regular historical patterns
    overnight travel is limited
    recent hourly/daily/weekly demand is representative
    demand follows recurring temporal patterns

The model also performs proportionally well at very high demand levels,
where MAPE falls to approximately:

    13.82%


# Where the Model Performs Poorly

The largest absolute errors occur in:

    major airports
    high-volume Manhattan zones
    major transport hubs
    busy evening hours
    high-demand zone-hour observations

These are conditions where demand may change rapidly because of exogenous
events that are not fully represented by the existing predictors.


# Likely Sources of Prediction Error

Potential error sources include:

    flight schedules and delays
    rail disruptions
    major sporting or cultural events
    holidays
    traffic congestion
    abrupt weather changes
    road closures
    unusual commuter patterns
    nonlinear high-volume demand surges
    information unavailable in historical lag features


# Evaluation Validation

The Phase 28 validator independently verified:

    Overall observations:       385,032
    Zones evaluated:            263
    Hours evaluated:            24
    Days evaluated:             7
    Demand levels evaluated:    6

Validated metrics:

    MAE:   4.1399
    RMSE: 12.0792
    R?:    0.9618

Best day by MAE:

    Monday
    MAE = 3.6044

Worst day by MAE:

    Thursday
    MAE = 4.6864

Best hour by MAE:

    03:00
    MAE = 1.8141

Worst hour by MAE:

    19:00
    MAE = 5.9110

Highest-error zone:

    JFK Airport
    MAE = 41.8402

MAPE zero-demand handling:

    PASS

Grouped observation reconciliation:

    PASS

Validation result:

    PHASE28_MODEL_EVALUATION_VALIDATION_SUCCESS


# Phase 28 Artifacts

Evaluation implementation:

    model/evaluate_model.py

Independent evaluation validator:

    model/validate_model_evaluation.py

Overall results:

    reports/model_evaluation/overall_metrics.csv

Zone-level results:

    reports/model_evaluation/by_zone.csv

Hour-level results:

    reports/model_evaluation/by_hour.csv

Day-level results:

    reports/model_evaluation/by_day_of_week.csv

Demand-level results:

    reports/model_evaluation/by_demand_level.csv


# Conclusion

The selected Random Forest model demonstrates strong overall predictive
performance on the chronological November-December holdout.

Headline performance:

    MAE  = 4.1399 trips
    RMSE = 12.0792 trips
    R?   = 0.9618

Performance is not uniform across all operating conditions.

Absolute errors are lowest in low-volume zones and overnight hours and highest
in airports, transportation hubs, busy Manhattan zones, evening periods, and
high-demand observations.

Percentage-error analysis shows that the model becomes proportionally more
accurate as actual taxi demand increases.

MAPE and sMAPE are not selected as primary metrics because the dataset
contains many zero and near-zero demand observations.

MAE and RMSE remain the principal measures of model quality.

Status:

    VALIDATED
