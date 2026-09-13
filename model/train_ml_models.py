from __future__ import annotations

import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pyarrow.dataset as ds

from sklearn.ensemble import (
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.preprocessing import OrdinalEncoder


PROJECT_ROOT = Path(__file__).resolve().parents[1]

FEATURE_ROOT = (
    PROJECT_ROOT
    / "data"
    / "gold"
    / "ml_features"
)

PREDICTION_ROOT = (
    PROJECT_ROOT
    / "data"
    / "gold"
    / "model_predictions"
)

MODEL_ROOT = (
    PROJECT_ROOT
    / "data"
    / "models"
    / "phase26"
)

REPORT_FILE = (
    PROJECT_ROOT
    / "reports"
    / "model_comparison_metrics.csv"
)

TRAIN_END = pd.Timestamp("2025-10-31 23:00:00")
TEST_START = pd.Timestamp("2025-11-01 00:00:00")
TEST_END = pd.Timestamp("2025-12-31 23:00:00")

EXPECTED_TOTAL_ROWS = 2_259_696
EXPECTED_TRAIN_ROWS = 1_874_664
EXPECTED_TEST_ROWS = 385_032

RANDOM_STATE = 42


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

ALL_FEATURES = (
    NUMERIC_FEATURES
    + CATEGORICAL_FEATURES
)

TARGET = "taxi_trips"


def calculate_metrics(
    actual: np.ndarray,
    predicted: np.ndarray,
) -> dict[str, float]:

    mae = mean_absolute_error(
        actual,
        predicted,
    )

    rmse = np.sqrt(
        mean_squared_error(
            actual,
            predicted,
        )
    )

    r2 = r2_score(
        actual,
        predicted,
    )

    return {
        "mae": float(mae),
        "rmse": float(rmse),
        "r2": float(r2),
    }


def load_features() -> pd.DataFrame:
    dataset = ds.dataset(
        FEATURE_ROOT,
        format="parquet",
        partitioning="hive",
    )

    columns = [
        "timestamp",
        TARGET,
        *ALL_FEATURES,
    ]

    table = dataset.to_table(
        columns=columns
    )

    df = table.to_pandas()

    df["timestamp"] = pd.to_datetime(
        df["timestamp"]
    )

    if len(df) != EXPECTED_TOTAL_ROWS:
        raise ValueError(
            f"Unexpected feature rows: {len(df):,}. "
            f"Expected {EXPECTED_TOTAL_ROWS:,}."
        )

    return df


def split_data(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:

    train = df.loc[
        df["timestamp"] <= TRAIN_END
    ].copy()

    test = df.loc[
        (df["timestamp"] >= TEST_START)
        & (df["timestamp"] <= TEST_END)
    ].copy()

    if len(train) != EXPECTED_TRAIN_ROWS:
        raise ValueError(
            f"Unexpected training rows: {len(train):,}. "
            f"Expected {EXPECTED_TRAIN_ROWS:,}."
        )

    if len(test) != EXPECTED_TEST_ROWS:
        raise ValueError(
            f"Unexpected test rows: {len(test):,}. "
            f"Expected {EXPECTED_TEST_ROWS:,}."
        )

    if train["timestamp"].max() >= test["timestamp"].min():
        raise ValueError(
            "Temporal leakage detected between train and test periods."
        )

    return train, test


def prepare_matrices(
    train: pd.DataFrame,
    test: pd.DataFrame,
):
    encoder = OrdinalEncoder(
        handle_unknown="use_encoded_value",
        unknown_value=-1,
        dtype=np.float32,
    )

    train_numeric = train[
        NUMERIC_FEATURES
    ].to_numpy(
        dtype=np.float32,
        copy=True,
    )

    test_numeric = test[
        NUMERIC_FEATURES
    ].to_numpy(
        dtype=np.float32,
        copy=True,
    )

    train_categories = encoder.fit_transform(
        train[CATEGORICAL_FEATURES]
    )

    test_categories = encoder.transform(
        test[CATEGORICAL_FEATURES]
    )

    x_train = np.concatenate(
        [
            train_numeric,
            train_categories,
        ],
        axis=1,
    )

    x_test = np.concatenate(
        [
            test_numeric,
            test_categories,
        ],
        axis=1,
    )

    y_train = train[TARGET].to_numpy(
        dtype=np.float32
    )

    y_test = test[TARGET].to_numpy(
        dtype=np.float32
    )

    return (
        x_train,
        x_test,
        y_train,
        y_test,
        encoder,
    )


def train_hist_gradient_boosting(
    x_train: np.ndarray,
    y_train: np.ndarray,
):
    categorical_indices = [
        len(NUMERIC_FEATURES),
        len(NUMERIC_FEATURES) + 1,
    ]

    model = HistGradientBoostingRegressor(
        loss="squared_error",
        learning_rate=0.08,
        max_iter=200,
        max_leaf_nodes=31,
        min_samples_leaf=30,
        l2_regularization=1.0,
        categorical_features=categorical_indices,
        early_stopping=False,
        random_state=RANDOM_STATE,
    )

    start = time.perf_counter()

    model.fit(
        x_train,
        y_train,
    )

    seconds = time.perf_counter() - start

    return model, seconds


def train_random_forest(
    x_train: np.ndarray,
    y_train: np.ndarray,
):
    model = RandomForestRegressor(
        n_estimators=50,
        max_depth=18,
        min_samples_leaf=5,
        max_features=0.75,
        bootstrap=True,
        max_samples=0.70,
        n_jobs=5,
        random_state=RANDOM_STATE,
        verbose=1,
    )

    start = time.perf_counter()

    model.fit(
        x_train,
        y_train,
    )

    seconds = time.perf_counter() - start

    return model, seconds


def main() -> None:
    print("Loading Phase 24 ML features...")

    df = load_features()

    train, test = split_data(df)

    print()
    print(f"Total feature rows: {len(df):,}")
    print(f"Training rows:      {len(train):,}")
    print(f"Test rows:          {len(test):,}")

    print()
    print(
        "Training period: "
        f"{train['timestamp'].min()} "
        "through "
        f"{train['timestamp'].max()}"
    )

    print(
        "Test period:     "
        f"{test['timestamp'].min()} "
        "through "
        f"{test['timestamp'].max()}"
    )

    print()
    print("Preparing identical feature matrices...")

    (
        x_train,
        x_test,
        y_train,
        y_test,
        encoder,
    ) = prepare_matrices(
        train,
        test,
    )

    print(
        f"Feature matrix: {x_train.shape[1]} columns"
    )

    print()
    print("Evaluating weekly naive baseline...")

    baseline_prediction = test[
        "lag_168h"
    ].to_numpy(
        dtype=np.float32
    )

    baseline_metrics = calculate_metrics(
        y_test,
        baseline_prediction,
    )

    print(
        f"Baseline MAE:  "
        f"{baseline_metrics['mae']:.4f}"
    )
    print(
        f"Baseline RMSE: "
        f"{baseline_metrics['rmse']:.4f}"
    )
    print(
        f"Baseline R2:   "
        f"{baseline_metrics['r2']:.4f}"
    )

    print()
    print(
        "Training Model 1: "
        "HistGradientBoostingRegressor..."
    )

    hgb_model, hgb_seconds = (
        train_hist_gradient_boosting(
            x_train,
            y_train,
        )
    )

    hgb_prediction = hgb_model.predict(
        x_test
    )

    hgb_metrics = calculate_metrics(
        y_test,
        hgb_prediction,
    )

    print(
        f"HGB training seconds: "
        f"{hgb_seconds:.1f}"
    )
    print(
        f"HGB MAE:  "
        f"{hgb_metrics['mae']:.4f}"
    )
    print(
        f"HGB RMSE: "
        f"{hgb_metrics['rmse']:.4f}"
    )
    print(
        f"HGB R2:   "
        f"{hgb_metrics['r2']:.4f}"
    )

    print()
    print(
        "Training Model 2: "
        "RandomForestRegressor..."
    )

    rf_model, rf_seconds = (
        train_random_forest(
            x_train,
            y_train,
        )
    )

    rf_prediction = rf_model.predict(
        x_test
    )

    rf_metrics = calculate_metrics(
        y_test,
        rf_prediction,
    )

    print()
    print(
        f"RF training seconds: "
        f"{rf_seconds:.1f}"
    )
    print(
        f"RF MAE:  "
        f"{rf_metrics['mae']:.4f}"
    )
    print(
        f"RF RMSE: "
        f"{rf_metrics['rmse']:.4f}"
    )
    print(
        f"RF R2:   "
        f"{rf_metrics['r2']:.4f}"
    )

    results = pd.DataFrame(
        [
            {
                "model": "weekly_naive_baseline",
                "mae": baseline_metrics["mae"],
                "rmse": baseline_metrics["rmse"],
                "r2": baseline_metrics["r2"],
                "training_seconds": 0.0,
            },
            {
                "model": "hist_gradient_boosting",
                "mae": hgb_metrics["mae"],
                "rmse": hgb_metrics["rmse"],
                "r2": hgb_metrics["r2"],
                "training_seconds": hgb_seconds,
            },
            {
                "model": "random_forest",
                "mae": rf_metrics["mae"],
                "rmse": rf_metrics["rmse"],
                "r2": rf_metrics["r2"],
                "training_seconds": rf_seconds,
            },
        ]
    )

    results["mae_rank"] = (
        results["mae"]
        .rank(
            method="min"
        )
        .astype(int)
    )

    ml_results = results.loc[
        results["model"]
        != "weekly_naive_baseline"
    ].copy()

    ml_results = ml_results.sort_values(
        ["mae", "rmse"],
        ascending=True,
    )

    selected_ml_model = (
        ml_results.iloc[0]["model"]
    )

    selected_metrics = (
        ml_results.iloc[0]
    )

    beats_baseline_mae = (
        selected_metrics["mae"]
        < baseline_metrics["mae"]
    )

    beats_baseline_rmse = (
        selected_metrics["rmse"]
        < baseline_metrics["rmse"]
    )

    results["selected_ml_model"] = (
        results["model"]
        == selected_ml_model
    )

    results["train_start"] = (
        train["timestamp"].min()
    )

    results["train_end"] = (
        train["timestamp"].max()
    )

    results["test_start"] = (
        test["timestamp"].min()
    )

    results["test_end"] = (
        test["timestamp"].max()
    )

    results["train_rows"] = len(train)
    results["test_rows"] = len(test)

    REPORT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    results.to_csv(
        REPORT_FILE,
        index=False,
    )

    PREDICTION_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    prediction_output = pd.DataFrame(
        {
            "timestamp": test["timestamp"],
            "taxi_zone_id": test["taxi_zone_id"],
            "actual_demand": y_test,
            "baseline_prediction": baseline_prediction,
            "hist_gradient_boosting_prediction": hgb_prediction,
            "random_forest_prediction": rf_prediction,
        }
    )

    prediction_output.to_parquet(
        PREDICTION_ROOT
        / "phase26_model_predictions.parquet",
        index=False,
    )

    MODEL_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    joblib.dump(
        encoder,
        MODEL_ROOT
        / "categorical_encoder.joblib",
    )

    joblib.dump(
        hgb_model,
        MODEL_ROOT
        / "hist_gradient_boosting.joblib",
    )

    joblib.dump(
        rf_model,
        MODEL_ROOT
        / "random_forest.joblib",
        compress=3,
    )

    print()
    print("Model comparison:")
    print(
        results[
            [
                "model",
                "mae",
                "rmse",
                "r2",
                "training_seconds",
            ]
        ].to_string(
            index=False
        )
    )

    print()
    print(
        f"Selected ML model: "
        f"{selected_ml_model}"
    )

    print(
        "Selected model beats baseline MAE: "
        f"{beats_baseline_mae}"
    )

    print(
        "Selected model beats baseline RMSE: "
        f"{beats_baseline_rmse}"
    )

    print()
    print(
        "PHASE26_MODEL_COMPARISON_SUCCESS"
    )


if __name__ == "__main__":
    main()
