from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pyarrow.dataset as ds

from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error


PROJECT_ROOT = Path(__file__).resolve().parents[1]

FEATURE_ROOT = (
    PROJECT_ROOT
    / "data"
    / "gold"
    / "ml_features"
)

MODEL_ROOT = (
    PROJECT_ROOT
    / "data"
    / "models"
    / "phase26"
)

RF_MODEL_FILE = (
    MODEL_ROOT
    / "random_forest.joblib"
)

ENCODER_FILE = (
    MODEL_ROOT
    / "categorical_encoder.joblib"
)

REPORT_ROOT = (
    PROJECT_ROOT
    / "reports"
    / "feature_importance"
)

TEST_START = pd.Timestamp(
    "2025-11-01 00:00:00"
)

TEST_END = pd.Timestamp(
    "2025-12-31 23:00:00"
)

EXPECTED_TEST_ROWS = 385_032

RANDOM_STATE = 42
PERMUTATION_REPEATS = 3


NUMERIC_FEATURES = [
    "lag_1h",
    "lag_24h",
    "lag_168h",
    "hour",
    "day_of_week",
    "month",
    "is_weekend",
    "taxi_zone_id",
    "temperature_c",
    "rain_mm",
    "snowfall_cm",
    "complaints_lag_1h",
    "complaints_lag_24h",
]

CATEGORICAL_FEATURES = [
    "borough",
    "weather_condition",
]

FEATURE_NAMES = (
    NUMERIC_FEATURES
    + CATEGORICAL_FEATURES
)

TARGET = "taxi_trips"


FEATURE_GROUPS = {
    "historical_demand": [
        "lag_1h",
        "lag_24h",
        "lag_168h",
    ],
    "time_calendar": [
        "hour",
        "day_of_week",
        "month",
        "is_weekend",
    ],
    "location": [
        "taxi_zone_id",
        "borough",
    ],
    "weather": [
        "temperature_c",
        "rain_mm",
        "snowfall_cm",
        "weather_condition",
    ],
    "311_activity": [
        "complaints_lag_1h",
        "complaints_lag_24h",
    ],
}


def load_test_data() -> pd.DataFrame:

    dataset = ds.dataset(
        FEATURE_ROOT,
        format="parquet",
        partitioning="hive",
    )

    table = dataset.to_table(
        columns=[
            "timestamp",
            TARGET,
            *FEATURE_NAMES,
        ]
    )

    df = table.to_pandas()

    df["timestamp"] = pd.to_datetime(
        df["timestamp"]
    )

    df = df.loc[
        (
            df["timestamp"]
            >= TEST_START
        )
        & (
            df["timestamp"]
            <= TEST_END
        )
    ].copy()

    if len(df) != EXPECTED_TEST_ROWS:
        raise ValueError(
            f"Unexpected test rows: "
            f"{len(df):,}. "
            f"Expected "
            f"{EXPECTED_TEST_ROWS:,}."
        )

    return df


def prepare_test_matrix(
    df: pd.DataFrame,
    encoder,
) -> tuple[
    np.ndarray,
    np.ndarray,
]:

    numeric = df[
        NUMERIC_FEATURES
    ].to_numpy(
        dtype=np.float32,
        copy=True,
    )

    categorical = encoder.transform(
        df[CATEGORICAL_FEATURES]
    )

    x_test = np.concatenate(
        [
            numeric,
            categorical,
        ],
        axis=1,
    )

    y_test = df[TARGET].to_numpy(
        dtype=np.float32
    )

    return x_test, y_test


def calculate_impurity_importance(
    model,
) -> pd.DataFrame:

    values = model.feature_importances_

    if len(values) != len(FEATURE_NAMES):
        raise ValueError(
            "Model feature count does not "
            "match Phase 26 feature names."
        )

    result = pd.DataFrame(
        {
            "feature": FEATURE_NAMES,
            "impurity_importance": values,
        }
    )

    result = result.sort_values(
        "impurity_importance",
        ascending=False,
    ).reset_index(drop=True)

    result["rank"] = (
        np.arange(
            1,
            len(result) + 1,
        )
    )

    return result[
        [
            "rank",
            "feature",
            "impurity_importance",
        ]
    ]


def calculate_permutation_importance(
    model,
    x_test: np.ndarray,
    y_test: np.ndarray,
) -> pd.DataFrame:

    result = permutation_importance(
        model,
        x_test,
        y_test,
        scoring="neg_mean_absolute_error",
        n_repeats=PERMUTATION_REPEATS,
        random_state=RANDOM_STATE,
        n_jobs=1,
    )

    output = pd.DataFrame(
        {
            "feature": FEATURE_NAMES,
            "mae_increase_mean":
                result.importances_mean,
            "mae_increase_std":
                result.importances_std,
        }
    )

    output = output.sort_values(
        "mae_increase_mean",
        ascending=False,
    ).reset_index(drop=True)

    output["rank"] = np.arange(
        1,
        len(output) + 1,
    )

    return output[
        [
            "rank",
            "feature",
            "mae_increase_mean",
            "mae_increase_std",
        ]
    ]


def calculate_group_permutation(
    model,
    x_test: np.ndarray,
    y_test: np.ndarray,
) -> pd.DataFrame:

    baseline_prediction = model.predict(
        x_test
    )

    baseline_mae = mean_absolute_error(
        y_test,
        baseline_prediction,
    )

    rng = np.random.default_rng(
        RANDOM_STATE
    )

    feature_index = {
        feature: index
        for index, feature
        in enumerate(FEATURE_NAMES)
    }

    rows = []

    for group_name, features in (
        FEATURE_GROUPS.items()
    ):

        deltas = []

        indices = [
            feature_index[feature]
            for feature in features
        ]

        for _ in range(
            PERMUTATION_REPEATS
        ):

            permutation = rng.permutation(
                len(x_test)
            )

            permuted = x_test.copy()

            permuted[
                :,
                indices,
            ] = x_test[
                permutation
            ][:, indices]

            prediction = model.predict(
                permuted
            )

            permuted_mae = (
                mean_absolute_error(
                    y_test,
                    prediction,
                )
            )

            deltas.append(
                permuted_mae
                - baseline_mae
            )

        rows.append(
            {
                "feature_group":
                    group_name,
                "features":
                    ", ".join(features),
                "baseline_mae":
                    baseline_mae,
                "mae_increase_mean":
                    float(
                        np.mean(deltas)
                    ),
                "mae_increase_std":
                    float(
                        np.std(
                            deltas,
                            ddof=0,
                        )
                    ),
            }
        )

    output = pd.DataFrame(rows)

    output = output.sort_values(
        "mae_increase_mean",
        ascending=False,
    ).reset_index(drop=True)

    output["rank"] = np.arange(
        1,
        len(output) + 1,
    )

    return output[
        [
            "rank",
            "feature_group",
            "features",
            "baseline_mae",
            "mae_increase_mean",
            "mae_increase_std",
        ]
    ]


def main() -> None:

    if not RF_MODEL_FILE.exists():
        raise FileNotFoundError(
            f"Random Forest model missing: "
            f"{RF_MODEL_FILE}"
        )

    if not ENCODER_FILE.exists():
        raise FileNotFoundError(
            f"Encoder missing: "
            f"{ENCODER_FILE}"
        )

    print(
        "Loading selected Random Forest..."
    )

    model = joblib.load(
        RF_MODEL_FILE
    )

    encoder = joblib.load(
        ENCODER_FILE
    )

    print(
        "Loading chronological "
        "Nov-Dec test data..."
    )

    df = load_test_data()

    x_test, y_test = (
        prepare_test_matrix(
            df,
            encoder,
        )
    )

    print(
        f"Test rows: "
        f"{len(df):,}"
    )

    print(
        f"Features: "
        f"{x_test.shape[1]}"
    )

    baseline_prediction = (
        model.predict(x_test)
    )

    baseline_mae = (
        mean_absolute_error(
            y_test,
            baseline_prediction,
        )
    )

    print(
        f"Baseline Random Forest MAE: "
        f"{baseline_mae:.4f}"
    )

    print()
    print(
        "Calculating tree impurity "
        "importance..."
    )

    impurity = (
        calculate_impurity_importance(
            model
        )
    )

    print(
        "Calculating test-set "
        "permutation importance..."
    )

    permutation = (
        calculate_permutation_importance(
            model,
            x_test,
            y_test,
        )
    )

    print(
        "Calculating grouped "
        "permutation importance..."
    )

    grouped = (
        calculate_group_permutation(
            model,
            x_test,
            y_test,
        )
    )

    REPORT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    impurity.to_csv(
        REPORT_ROOT
        / "random_forest_impurity.csv",
        index=False,
    )

    permutation.to_csv(
        REPORT_ROOT
        / "random_forest_permutation.csv",
        index=False,
    )

    grouped.to_csv(
        REPORT_ROOT
        / "grouped_permutation.csv",
        index=False,
    )

    print()
    print(
        "Top features by permutation "
        "MAE impact:"
    )

    print(
        permutation.head(15)
        .to_string(
            index=False
        )
    )

    print()
    print(
        "Tree impurity ranking:"
    )

    print(
        impurity.head(15)
        .to_string(
            index=False
        )
    )

    print()
    print(
        "Grouped permutation ranking:"
    )

    print(
        grouped.to_string(
            index=False
        )
    )

    print()
    print(
        "Interpretation rule:"
    )

    print(
        "Higher permutation MAE increase "
        "= greater measured out-of-sample "
        "influence."
    )

    print()
    print(
        "PHASE29_FEATURE_IMPORTANCE_SUCCESS"
    )


if __name__ == "__main__":
    main()
