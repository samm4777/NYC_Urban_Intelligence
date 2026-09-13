from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

PREDICTION_FILE = (
    PROJECT_ROOT
    / "data"
    / "gold"
    / "baseline_predictions"
    / "weekly_naive_baseline.parquet"
)

METRICS_FILE = (
    PROJECT_ROOT
    / "reports"
    / "baseline_model_metrics.csv"
)

EXPECTED_ROWS = 385_032
EXPECTED_ZONES = 263
EXPECTED_TEST_DAYS = 61

EXPECTED_MAE = 6.7707
EXPECTED_RMSE = 22.9201
EXPECTED_R2 = 0.8626

TOLERANCE = 0.0001


def main() -> None:
    if not PREDICTION_FILE.exists():
        raise FileNotFoundError(
            f"Missing prediction file: {PREDICTION_FILE}"
        )

    if not METRICS_FILE.exists():
        raise FileNotFoundError(
            f"Missing metrics file: {METRICS_FILE}"
        )

    df = pd.read_parquet(PREDICTION_FILE)

    df["timestamp"] = pd.to_datetime(
        df["timestamp"]
    )

    if len(df) != EXPECTED_ROWS:
        raise ValueError(
            f"Unexpected prediction rows: {len(df):,}. "
            f"Expected {EXPECTED_ROWS:,}."
        )

    zone_count = df["taxi_zone_id"].nunique()

    if zone_count != EXPECTED_ZONES:
        raise ValueError(
            f"Unexpected zone count: {zone_count}. "
            f"Expected {EXPECTED_ZONES}."
        )

    duplicate_count = int(
        df.duplicated(
            subset=[
                "timestamp",
                "taxi_zone_id",
            ]
        ).sum()
    )

    if duplicate_count != 0:
        raise ValueError(
            f"Duplicate prediction rows: {duplicate_count:,}"
        )

    null_count = int(
        df[
            [
                "actual_demand",
                "predicted_demand",
            ]
        ].isna().sum().sum()
    )

    if null_count != 0:
        raise ValueError(
            f"Null actual/predicted values: {null_count:,}"
        )

    first_timestamp = df["timestamp"].min()
    last_timestamp = df["timestamp"].max()

    if first_timestamp != pd.Timestamp(
        "2025-11-01 00:00:00"
    ):
        raise ValueError(
            f"Unexpected first timestamp: {first_timestamp}"
        )

    if last_timestamp != pd.Timestamp(
        "2025-12-31 23:00:00"
    ):
        raise ValueError(
            f"Unexpected last timestamp: {last_timestamp}"
        )

    day_count = df["timestamp"].dt.date.nunique()

    if day_count != EXPECTED_TEST_DAYS:
        raise ValueError(
            f"Unexpected test-day count: {day_count}"
        )

    error = (
        df["actual_demand"]
        - df["predicted_demand"]
    )

    mae = float(
        np.mean(
            np.abs(error)
        )
    )

    rmse = float(
        np.sqrt(
            np.mean(
                np.square(error)
            )
        )
    )

    ss_res = float(
        np.sum(
            np.square(error)
        )
    )

    actual_mean = float(
        df["actual_demand"].mean()
    )

    ss_tot = float(
        np.sum(
            np.square(
                df["actual_demand"]
                - actual_mean
            )
        )
    )

    r2 = 1.0 - (ss_res / ss_tot)

    expected_metrics = {
        "MAE": (mae, EXPECTED_MAE),
        "RMSE": (rmse, EXPECTED_RMSE),
        "R2": (r2, EXPECTED_R2),
    }

    for name, (
        actual,
        expected,
    ) in expected_metrics.items():

        if abs(
            actual - expected
        ) > TOLERANCE:

            raise ValueError(
                f"{name} mismatch: "
                f"{actual:.4f} vs "
                f"{expected:.4f}"
            )

    metrics_df = pd.read_csv(
        METRICS_FILE
    )

    if len(metrics_df) != 1:
        raise ValueError(
            "Expected exactly one baseline metrics row."
        )

    if (
        metrics_df.iloc[0]["model"]
        != "weekly_naive_baseline"
    ):
        raise ValueError(
            "Unexpected baseline model name."
        )

    print(f"Prediction rows: {len(df):,}")
    print(f"Zones: {zone_count}")
    print(f"Test days: {day_count}")
    print(f"Duplicate predictions: {duplicate_count:,}")
    print(f"Null predictions: {null_count:,}")
    print(f"First timestamp: {first_timestamp}")
    print(f"Last timestamp: {last_timestamp}")

    print()
    print(f"Validated MAE:  {mae:.4f}")
    print(f"Validated RMSE: {rmse:.4f}")
    print(f"Validated R2:   {r2:.4f}")

    print()
    print(
        "PHASE25_BASELINE_VALIDATION_SUCCESS"
    )


if __name__ == "__main__":
    main()
