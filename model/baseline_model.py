from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

FEATURE_ROOT = (
    PROJECT_ROOT
    / "data"
    / "gold"
    / "ml_features"
)

OUTPUT_ROOT = (
    PROJECT_ROOT
    / "data"
    / "gold"
    / "baseline_predictions"
)

TEST_START = pd.Timestamp("2025-11-01 00:00:00")
TEST_END = pd.Timestamp("2025-12-31 23:00:00")


def load_test_data() -> pd.DataFrame:
    dataset = ds.dataset(
        FEATURE_ROOT,
        format="parquet",
        partitioning="hive",
    )

    table = dataset.to_table(
        columns=[
            "timestamp",
            "taxi_zone_id",
            "taxi_zone_name",
            "borough",
            "taxi_trips",
            "lag_168h",
        ]
    )

    df = table.to_pandas()

    df["timestamp"] = pd.to_datetime(
        df["timestamp"]
    )

    df = df.loc[
        (df["timestamp"] >= TEST_START)
        & (df["timestamp"] <= TEST_END)
    ].copy()

    return df


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


def main() -> None:
    print("Loading Phase 24 feature dataset...")

    df = load_test_data()

    if df.empty:
        raise ValueError(
            "Baseline test dataset is empty."
        )

    expected_test_rows = (
        61
        * 24
        * 263
    )

    if len(df) != expected_test_rows:
        raise ValueError(
            f"Unexpected test rows: {len(df):,}. "
            f"Expected {expected_test_rows:,}."
        )

    if df["lag_168h"].isna().any():
        raise ValueError(
            "Null baseline predictions detected."
        )

    df["actual_demand"] = (
        df["taxi_trips"]
        .astype("float64")
    )

    df["predicted_demand"] = (
        df["lag_168h"]
        .astype("float64")
    )

    metrics = calculate_metrics(
        df["actual_demand"].to_numpy(),
        df["predicted_demand"].to_numpy(),
    )

    print()
    print("Baseline model:")
    print(
        "Predicted demand = "
        "same zone/hour demand 168 hours earlier"
    )

    print()
    print(f"Test start: {TEST_START}")
    print(f"Test end:   {TEST_END}")
    print(f"Test rows:  {len(df):,}")

    print()
    print(f"MAE:  {metrics['mae']:.4f}")
    print(f"RMSE: {metrics['rmse']:.4f}")
    print(f"R2:   {metrics['r2']:.4f}")

    OUTPUT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        OUTPUT_ROOT
        / "weekly_naive_baseline.parquet"
    )

    df[
        [
            "timestamp",
            "taxi_zone_id",
            "taxi_zone_name",
            "borough",
            "actual_demand",
            "predicted_demand",
        ]
    ].to_parquet(
        output_file,
        index=False,
    )

    metrics_file = (
        PROJECT_ROOT
        / "reports"
        / "baseline_model_metrics.csv"
    )

    metrics_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    pd.DataFrame(
        [
            {
                "model": "weekly_naive_baseline",
                "prediction_rule": "lag_168h",
                "test_start": TEST_START,
                "test_end": TEST_END,
                "test_rows": len(df),
                **metrics,
            }
        ]
    ).to_csv(
        metrics_file,
        index=False,
    )

    print()
    print(
        "PHASE25_BASELINE_SUCCESS"
    )


if __name__ == "__main__":
    main()
