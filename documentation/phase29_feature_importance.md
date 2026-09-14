# Phase 29 - Feature Importance

Status: VALIDATED PENDING FINAL ARTIFACT CHECK

## Objective

Measure the actual influence of model features on the selected taxi-demand
model rather than assuming which predictors are important.

Selected model:

    RandomForestRegressor

Evaluation dataset:

    November 2025 through December 2025

Chronological holdout observations:

    385,032

Baseline Random Forest MAE:

    4.1399


# Importance Methods

Phase 29 uses two complementary feature-importance methods:

    1. Random Forest impurity importance
    2. Test-set permutation importance

It also performs:

    3. Grouped permutation importance

The three approaches answer different questions.


## Tree Impurity Importance

Random Forest impurity importance measures how much each feature contributes
to reducing prediction error across decision-tree splits.

Advantages:

    computationally efficient
    directly available from the fitted Random Forest
    useful for understanding which features trees frequently use

Limitations:

    may favor continuous or high-cardinality predictors
    can distribute importance unpredictably across correlated variables
    describes fitted tree structure rather than direct out-of-sample impact


## Permutation Importance

Permutation importance measures how much predictive performance deteriorates
when the information in one feature is disrupted on the unseen test set.

The Phase 29 implementation uses:

    scoring = negative mean absolute error

Therefore:

    larger MAE increase
    =
    greater measured predictive influence

Permutation importance is treated as the preferred individual-feature
interpretation because it measures impact directly on the chronological
holdout.


## Grouped Permutation Importance

Several predictors represent related concepts.

For example:

    lag_1h
    lag_24h
    lag_168h

all represent historical taxi demand.

Because correlated variables may partially substitute for one another,
permuting one feature at a time can understate the combined importance of a
feature family.

Phase 29 therefore additionally permutes complete conceptual groups:

    historical demand
    time/calendar
    location
    weather
    311 activity


# Individual Permutation Importance

Measured ranking:

| Rank | Feature | Mean MAE Increase | Std. Dev. |
| ---: | --- | ---: | ---: |
| 1 | lag_1h | 12.127860 | 0.012145 |
| 2 | lag_168h | 4.146489 | 0.009599 |
| 3 | lag_24h | 1.793671 | 0.008853 |
| 4 | hour | 0.452660 | 0.003807 |
| 5 | day_of_week | 0.108788 | 0.001274 |
| 6 | taxi_zone_id | 0.077720 | 0.002020 |
| 7 | borough | 0.049280 | 0.000685 |
| 8 | complaints_lag_1h | 0.016805 | 0.000275 |
| 9 | complaints_lag_24h | 0.014653 | 0.000247 |
| 10 | is_weekend | 0.007294 | 0.000383 |
| 11 | temperature_c | 0.002054 | 0.000517 |
| 12 | snowfall_cm | 0.000063 | 0.000013 |
| 13 | month | 0.000000 | 0.000000 |
| 14 | rain_mm | -0.000163 | 0.000323 |
| 15 | weather_condition | -0.003820 | 0.000554 |


# Most Influential Feature

The most influential individual feature is:

    lag_1h

Mean MAE increase after permutation:

    +12.1279 trips

The model's normal test MAE is:

    4.1399

Disrupting the previous-hour demand signal therefore causes a very large
deterioration in prediction quality.

This indicates strong short-term persistence in taxi demand.

Demand in a taxi zone during the immediately preceding hour contains highly
valuable information about demand in the next hour.


# Weekly Historical Demand

Second-ranked feature:

    lag_168h

Permutation MAE increase:

    +4.1465

This represents taxi demand in the same zone and relative hour one week
earlier.

Its importance demonstrates that NYC taxi activity contains substantial
weekly repetition.

Examples may include recurring:

    commuting behavior
    weekday schedules
    weekend activity
    airport travel patterns
    commercial activity
    entertainment patterns


# Daily Historical Demand

Third-ranked feature:

    lag_24h

Permutation MAE increase:

    +1.7937

This shows that previous-day demand also contributes substantial information.

The three historical demand variables therefore capture different temporal
structures:

    lag_1h   = short-term momentum
    lag_24h  = daily repetition
    lag_168h = weekly repetition


# Time Features

The most important non-lag predictor is:

    hour

Permutation MAE increase:

    +0.4527

This confirms that hour-of-day contributes information beyond the historical
lag variables.

Taxi demand changes systematically across:

    overnight periods
    morning travel
    daytime activity
    commuting periods
    evening activity
    nightlife periods


## Day of Week

Feature:

    day_of_week

MAE increase:

    +0.1088

The model therefore obtains additional value from distinguishing Monday,
Tuesday, Wednesday, and other days even after historical lag features are
included.


## Weekend Flag

Feature:

    is_weekend

MAE increase:

    +0.0073

Its incremental value is relatively small.

This is reasonable because much of the weekend information is already
represented by:

    day_of_week
    historical demand lags


## Month

Feature:

    month

MAE increase:

    approximately 0

Within the November-December holdout, permutation of month produced no
measurable MAE deterioration.

This does not prove that month can never matter.

It means that the fitted Random Forest obtained no measurable incremental
out-of-sample value from month in this particular test period after the
remaining predictors were available.


# Location Features

## Taxi Zone

Feature:

    taxi_zone_id

MAE increase:

    +0.0777


## Borough

Feature:

    borough

MAE increase:

    +0.0493


## Interpretation

Location provides measurable predictive value, but considerably less than
recent historical demand.

This does not mean geography is unimportant to NYC taxi demand.

Instead, much of a zone's typical behavior may already be encoded indirectly
inside its recent:

    lag_1h
    lag_24h
    lag_168h

values.

Historical demand therefore contains both temporal and location-specific
information.


# 311 Activity

Measured individual importance:

    complaints_lag_1h
        MAE increase = +0.0168

    complaints_lag_24h
        MAE increase = +0.0147


Grouped 311 activity importance:

    MAE increase = +0.0303


## Interpretation

Historical 311 activity provides a small but measurable out-of-sample signal.

Its predictive contribution is much smaller than historical taxi demand,
time, or location.

This suggests that 311 complaints provide additional urban-activity context
but are not a primary driver of taxi-demand forecasting performance.


# Weather Features

Individual permutation results:

    temperature_c
        +0.002054

    snowfall_cm
        +0.000063

    rain_mm
        -0.000163

    weather_condition
        -0.003820


Grouped weather permutation:

    MAE increase = -0.000108


## Interpretation

Weather showed essentially no incremental out-of-sample predictive value in
the selected Random Forest during the November-December holdout.

The grouped result is extremely close to zero.

A small negative permutation value does not mean that worse weather improves
taxi forecasting.

It means that disrupting the weather variables did not degrade holdout MAE
and produced a tiny improvement within normal measurement variation.

Possible reasons include:

    historical taxi lags already capture weather-related demand changes
    normal weather variability may have limited incremental effect
    weather variables may overlap with information captured by other features
    unusual severe-weather events may be too rare to dominate this holdout

The conclusion is therefore:

    weather showed negligible incremental importance

rather than:

    weather never affects taxi demand


# Tree Impurity Importance

Random Forest impurity ranking:

| Rank | Feature | Impurity Importance |
| ---: | --- | ---: |
| 1 | lag_168h | 0.744490 |
| 2 | lag_1h | 0.206601 |
| 3 | lag_24h | 0.033078 |
| 4 | hour | 0.004467 |
| 5 | temperature_c | 0.002272 |
| 6 | taxi_zone_id | 0.001952 |
| 7 | day_of_week | 0.001881 |
| 8 | borough | 0.001622 |
| 9 | month | 0.001013 |
| 10 | weather_condition | 0.000720 |
| 11 | complaints_lag_1h | 0.000656 |
| 12 | complaints_lag_24h | 0.000591 |
| 13 | rain_mm | 0.000449 |
| 14 | is_weekend | 0.000197 |
| 15 | snowfall_cm | 0.000010 |


# Why Impurity and Permutation Rankings Differ

The impurity method ranks:

    lag_168h

first.

Permutation importance ranks:

    lag_1h

first.

This difference is not a contradiction.

The historical-demand features are strongly related to one another and
represent overlapping temporal signals.

Tree impurity importance describes how the fitted forest distributed its
splits among those correlated predictors.

Permutation importance instead asks:

    How much does unseen-test MAE deteriorate if this feature's information
    is disrupted?

On this criterion, lag_1h has the greatest individual out-of-sample impact.

Therefore, permutation importance is preferred for the final individual
feature interpretation.


# Grouped Permutation Importance

Measured group ranking:

| Rank | Feature Group | Mean MAE Increase |
| ---: | --- | ---: |
| 1 | Historical Demand | 33.850883 |
| 2 | Time / Calendar | 0.514346 |
| 3 | Location | 0.117520 |
| 4 | 311 Activity | 0.030265 |
| 5 | Weather | -0.000108 |


# Historical Demand Dominates

The most important feature family is:

    historical_demand

Features:

    lag_1h
    lag_24h
    lag_168h

Grouped MAE increase:

    +33.8509

This is dramatically larger than every other feature family.

The selected model is therefore primarily a historical-demand forecasting
model enhanced by calendar, geographic, urban-activity, and weather context.


# Time and Calendar

Grouped MAE increase:

    +0.5143

This is the second-most influential feature family.

It confirms that explicit temporal information provides useful predictive
signal beyond taxi-demand lags.


# Location

Grouped MAE increase:

    +0.1175

Location contributes measurable incremental value after historical demand and
calendar patterns are already known.


# 311 Activity

Grouped MAE increase:

    +0.0303

This is a small but positive measured contribution.


# Weather

Grouped MAE increase:

    -0.0001

Weather did not provide measurable incremental improvement on this holdout
after the other feature families were present.


# Overall Feature Importance Ranking

The measured evidence supports the following conceptual ranking:

    1. Historical taxi demand
    2. Time and calendar
    3. Location
    4. Historical 311 activity
    5. Weather

The ranking was measured rather than assumed.


# Relationship to Model Performance

The selected Random Forest achieved:

    MAE  = 4.1399
    RMSE = 12.0792
    R?   = 0.9618

Phase 29 helps explain this strong performance.

The model relies heavily on recurring and recent taxi-demand patterns,
especially:

    previous hour
    previous week
    previous day

This is consistent with the recurring temporal structure of urban
transportation demand.


# Operational Interpretation

For an operational prediction system, the most critical upstream inputs are:

    recent hourly taxi demand
    previous-day demand
    previous-week demand

If these historical-demand features are unavailable, stale, or incorrect,
model performance can deteriorate substantially.

Calendar and location features should also remain reliable.

311 information contributes a smaller amount.

Weather information is retained as an evaluated candidate but did not
demonstrate meaningful incremental importance in this specific model and
holdout.


# Cautions

Feature importance does not establish causality.

For example:

    lag_1h being highly important

does not mean previous-hour taxi trips cause future taxi trips.

It means that previous-hour demand is highly informative for prediction.

Similarly, low measured weather importance does not prove weather has no
causal effect on taxi activity.

Feature importance describes predictive influence within:

    this fitted model
    this feature set
    this chronological holdout


# Phase 29 Artifacts

Feature-importance implementation:

    model/feature_importance.py

Tree impurity evidence:

    reports/feature_importance/random_forest_impurity.csv

Individual permutation evidence:

    reports/feature_importance/random_forest_permutation.csv

Grouped permutation evidence:

    reports/feature_importance/grouped_permutation.csv


# Conclusion

Phase 29 measured actual feature influence using both Random Forest impurity
importance and out-of-sample permutation importance.

The strongest individual predictor according to permutation importance is:

    lag_1h

followed by:

    lag_168h
    lag_24h

Grouped analysis confirms that:

    Historical Demand

dominates model performance by a very large margin.

Time/calendar and location add meaningful secondary information.

311 activity contributes a small positive signal.

Weather provides negligible incremental predictive value in the evaluated
holdout after historical demand and other predictors are already available.

The final feature-importance conclusions are based on measured model behavior
rather than assumed domain importance.

Status:

    VALIDATED
