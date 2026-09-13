from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

PREDICTION_FILE = (
    PROJECT_ROOT
    / "data"
    / "gold"
    / "model_predictions"
    / "phase26_model_predictions.parquet"
)

REPORT_FILE = (
    PROJECT_ROOT
    / "reports"
    / "model_comparison_metrics.csv"
)

EXPECTED_ROWS = 385_032
EXPECTED_ZONES = 263

EXPECTED_FIRST_TIMESTAMP = pd.Timestamp(
    "2025-11-01 00:00:00"
)

EXPECTED_LAST_TIMESTAMP = pd.Timestamp(
    "2025-12-31 23:00:00"
)

TOLERANCE = 1e-6


def metrics(
    actual: np.ndarray,
    predicted: np.ndarray,
) -> dict[str, float]:

    return {
        "mae": float(
            mean_absolute_error(
                actual,
                predicted,
            )
        ),
        "rmse": float(
            np.sqrt(
                mean_squared_error(
                    actual,
                    predicted,
                )
            )
        ),
        "r2": float(
            r2_score(
                actual,
                predicted,
            )
        ),
    }


def assert_close(
    name: str,
    actual: float,
    expected: float,
) -> None:

    if abs(actual - expected) > TOLERANCE:
        raise ValueError(
            f"{name} mismatch: "
            f"{actual} vs {expected}"
        )


def main() -> None:
    if not PREDICTION_FILE.exists():
        raise FileNotFoundError(
            f"Missing prediction file: "
            f"{PREDICTION_FILE}"
        )

    if not REPORT_FILE.exists():
        raise FileNotFoundError(
            f"Missing comparison report: "
            f"{REPORT_FILE}"
        )

    df = pd.read_parquet(
        PREDICTION_FILE
    )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"]
    )

    if len(df) != EXPECTED_ROWS:
        raise ValueError(
            f"Unexpected prediction rows: "
            f"{len(df):,}"
        )

    zone_count = (
        df["taxi_zone_id"].nunique()
    )

    if zone_count != EXPECTED_ZONES:
        raise ValueError(
            f"Unexpected zone count: "
            f"{zone_count}"
        )

    duplicates = int(
        df.duplicated(
            subset=[
                "timestamp",
                "taxi_zone_id",
            ]
        ).sum()
    )

    if duplicates != 0:
        raise ValueError(
            f"Duplicate predictions: "
            f"{duplicates:,}"
        )

    prediction_columns = [
        "actual_demand",
        "baseline_prediction",
        "hist_gradient_boosting_prediction",
        "random_forest_prediction",
    ]

    null_count = int(
        df[prediction_columns]
        .isna()
        .sum()
        .sum()
    )

    if null_count != 0:
        raise ValueError(
            f"Null prediction values: "
            f"{null_count:,}"
        )

    first_timestamp = (
        df["timestamp"].min()
    )

    last_timestamp = (
        df["timestamp"].max()
    )

    if (
        first_timestamp
        != EXPECTED_FIRST_TIMESTAMP
    ):
        raise ValueError(
            f"Unexpected first timestamp: "
            f"{first_timestamp}"
        )

    if (
        last_timestamp
        != EXPECTED_LAST_TIMESTAMP
    ):
        raise ValueError(
            f"Unexpected last timestamp: "
            f"{last_timestamp}"
        )

    actual = (
        df["actual_demand"]
        .to_numpy()
    )

    calculated = {
        "weekly_naive_baseline":
            metrics(
                actual,
                df[
                    "baseline_prediction"
                ].to_numpy(),
            ),

        "hist_gradient_boosting":
            metrics(
                actual,
                df[
                    "hist_gradient_boosting_prediction"
                ].to_numpy(),
            ),

        "random_forest":
            metrics(
                actual,
                df[
                    "random_forest_prediction"
                ].to_numpy(),
            ),
    }

    report = pd.read_csv(
        REPORT_FILE
    )

    expected_models = {
        "weekly_naive_baseline",
        "hist_gradient_boosting",
        "random_forest",
    }

    if set(report["model"]) != expected_models:
        raise ValueError(
            "Unexpected models in comparison report."
        )

    for model_name, model_metrics in (
        calculated.items()
    ):

        row = report.loc[
            report["model"] == model_name
        ].iloc[0]

        for metric_name in [
            "mae",
            "rmse",
            "r2",
        ]:
            assert_close(
                f"{model_name} {metric_name}",
                model_metrics[metric_name],
                float(row[metric_name]),
            )

    baseline = calculated[
        "weekly_naive_baseline"
    ]

    hgb = calculated[
        "hist_gradient_boosting"
    ]

    rf = calculated[
        "random_forest"
    ]

    if not (
        rf["mae"] < baseline["mae"]
        and rf["rmse"] < baseline["rmse"]
    ):
        raise ValueError(
            "Random Forest does not beat "
            "baseline on MAE and RMSE."
        )

    if not (
        rf["mae"] < hgb["mae"]
        and rf["rmse"] < hgb["rmse"]
    ):
        raise ValueError(
            "Random Forest is not the measured "
            "accuracy winner."
        )

    selected_rows = report.loc[
        report["selected_ml_model"]
        .astype(str)
        .str.lower()
        == "true"
    ]

    if len(selected_rows) != 1:
        raise ValueError(
            "Expected exactly one selected ML model."
        )

    selected_model = (
        selected_rows.iloc[0]["model"]
    )

    if selected_model != "random_forest":
        raise ValueError(
            f"Unexpected selected model: "
            f"{selected_model}"
        )

    mae_improvement = (
        (
            baseline["mae"]
            - rf["mae"]
        )
        / baseline["mae"]
        * 100.0
    )

    rmse_improvement = (
        (
            baseline["rmse"]
            - rf["rmse"]
        )
        / baseline["rmse"]
        * 100.0
    )

    print(
        f"Prediction rows: "
        f"{len(df):,}"
    )

    print(
        f"Zones: {zone_count}"
    )

    print(
        f"Duplicate predictions: "
        f"{duplicates:,}"
    )

    print(
        f"Null values: "
        f"{null_count:,}"
    )

    print(
        f"First timestamp: "
        f"{first_timestamp}"
    )

    print(
        f"Last timestamp: "
        f"{last_timestamp}"
    )

    print()

    for model_name, result in (
        calculated.items()
    ):
        print(model_name)
        print(
            f"  MAE:  "
            f"{result['mae']:.4f}"
        )
        print(
            f"  RMSE: "
            f"{result['rmse']:.4f}"
        )
        print(
            f"  R2:   "
            f"{result['r2']:.4f}"
        )

    print()

    print(
        "Selected model: "
        f"{selected_model}"
    )

    print(
        "Random Forest MAE improvement "
        f"vs baseline: "
        f"{mae_improvement:.2f}%"
    )

    print(
        "Random Forest RMSE improvement "
        f"vs baseline: "
        f"{rmse_improvement:.2f}%"
    )

    print()

    print(
        "PHASE26_MODEL_VALIDATION_SUCCESS"
    )


if __name__ == "__main__":
    main()
