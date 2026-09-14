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

PREDICTION_FILE = (
    PROJECT_ROOT
    / "data"
    / "gold"
    / "model_predictions"
    / "phase26_model_predictions.parquet"
)

FEATURE_ROOT = (
    PROJECT_ROOT
    / "data"
    / "gold"
    / "ml_features"
)

REPORT_ROOT = (
    PROJECT_ROOT
    / "reports"
    / "model_evaluation"
)

EXPECTED_ROWS = 385_032
EXPECTED_ZONES = 263

SELECTED_MODEL = "random_forest"

ACTUAL_COLUMN = "actual_demand"
PREDICTION_COLUMN = "random_forest_prediction"


def regression_metrics(
    actual: pd.Series,
    predicted: pd.Series,
) -> dict[str, float]:

    actual_np = actual.to_numpy(
        dtype=np.float64
    )

    predicted_np = predicted.to_numpy(
        dtype=np.float64
    )

    mae = mean_absolute_error(
        actual_np,
        predicted_np,
    )

    rmse = np.sqrt(
        mean_squared_error(
            actual_np,
            predicted_np,
        )
    )

    if len(actual_np) >= 2:
        r2 = r2_score(
            actual_np,
            predicted_np,
        )
    else:
        r2 = np.nan

    positive_mask = actual_np > 0

    if positive_mask.any():
        mape_positive = np.mean(
            np.abs(
                (
                    actual_np[positive_mask]
                    - predicted_np[positive_mask]
                )
                / actual_np[positive_mask]
            )
        ) * 100.0
    else:
        mape_positive = np.nan

    denominator = (
        np.abs(actual_np)
        + np.abs(predicted_np)
    )

    smape_mask = denominator > 0

    if smape_mask.any():
        smape = np.mean(
            200.0
            * np.abs(
                actual_np[smape_mask]
                - predicted_np[smape_mask]
            )
            / denominator[smape_mask]
        )
    else:
        smape = 0.0

    bias = np.mean(
        predicted_np - actual_np
    )

    return {
        "observations": int(len(actual_np)),
        "actual_mean": float(
            np.mean(actual_np)
        ),
        "predicted_mean": float(
            np.mean(predicted_np)
        ),
        "mae": float(mae),
        "rmse": float(rmse),
        "r2": float(r2),
        "mape_positive_pct": float(
            mape_positive
        ),
        "smape_pct": float(smape),
        "mean_error_bias": float(bias),
    }


def load_predictions() -> pd.DataFrame:

    if not PREDICTION_FILE.exists():
        raise FileNotFoundError(
            f"Missing prediction file: "
            f"{PREDICTION_FILE}"
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

    if (
        df["taxi_zone_id"].nunique()
        != EXPECTED_ZONES
    ):
        raise ValueError(
            "Unexpected taxi-zone count."
        )

    duplicates = df.duplicated(
        subset=[
            "timestamp",
            "taxi_zone_id",
        ]
    ).sum()

    if duplicates != 0:
        raise ValueError(
            f"Duplicate predictions: "
            f"{duplicates:,}"
        )

    required = [
        ACTUAL_COLUMN,
        PREDICTION_COLUMN,
    ]

    if df[required].isna().any().any():
        raise ValueError(
            "Null actual or Random Forest "
            "prediction values detected."
        )

    return df


def load_zone_metadata() -> pd.DataFrame:

    dataset = ds.dataset(
        FEATURE_ROOT,
        format="parquet",
        partitioning="hive",
    )

    table = dataset.to_table(
        columns=[
            "taxi_zone_id",
            "taxi_zone_name",
            "borough",
        ]
    )

    zones = (
        table.to_pandas()
        .drop_duplicates(
            subset=["taxi_zone_id"]
        )
        .sort_values("taxi_zone_id")
        .reset_index(drop=True)
    )

    if len(zones) != EXPECTED_ZONES:
        raise ValueError(
            f"Unexpected metadata zones: "
            f"{len(zones)}"
        )

    return zones


def evaluate_grouped(
    df: pd.DataFrame,
    group_column: str,
) -> pd.DataFrame:

    rows = []

    for group_value, group in df.groupby(
        group_column,
        observed=True,
        sort=True,
    ):

        result = regression_metrics(
            group[ACTUAL_COLUMN],
            group[PREDICTION_COLUMN],
        )

        result[group_column] = group_value

        rows.append(result)

    output = pd.DataFrame(rows)

    metric_columns = [
        group_column,
        "observations",
        "actual_mean",
        "predicted_mean",
        "mae",
        "rmse",
        "r2",
        "mape_positive_pct",
        "smape_pct",
        "mean_error_bias",
    ]

    return output[metric_columns]


def add_temporal_dimensions(
    df: pd.DataFrame,
) -> pd.DataFrame:

    df = df.copy()

    df["hour"] = (
        df["timestamp"]
        .dt.hour
        .astype("int8")
    )

    df["day_of_week_number"] = (
        df["timestamp"]
        .dt.dayofweek
        .astype("int8")
    )

    df["day_of_week"] = (
        df["timestamp"]
        .dt.day_name()
    )

    return df


def add_demand_level(
    df: pd.DataFrame,
) -> pd.DataFrame:

    df = df.copy()

    bins = [
        -0.1,
        0,
        5,
        20,
        50,
        100,
        np.inf,
    ]

    labels = [
        "Zero (0)",
        "Very Low (1-5)",
        "Low (6-20)",
        "Moderate (21-50)",
        "High (51-100)",
        "Very High (101+)",
    ]

    df["demand_level"] = pd.cut(
        df[ACTUAL_COLUMN],
        bins=bins,
        labels=labels,
        include_lowest=True,
        ordered=True,
    )

    if df["demand_level"].isna().any():
        raise ValueError(
            "Some demand observations were "
            "not assigned to a demand level."
        )

    return df


def main() -> None:

    print(
        "Loading selected-model predictions..."
    )

    df = load_predictions()

    zones = load_zone_metadata()

    df = df.merge(
        zones,
        on="taxi_zone_id",
        how="left",
        validate="many_to_one",
    )

    if (
        df["taxi_zone_name"]
        .isna()
        .any()
    ):
        raise ValueError(
            "Missing taxi-zone metadata."
        )

    df = add_temporal_dimensions(df)
    df = add_demand_level(df)

    REPORT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print(
        "Calculating overall metrics..."
    )

    overall = regression_metrics(
        df[ACTUAL_COLUMN],
        df[PREDICTION_COLUMN],
    )

    overall_df = pd.DataFrame(
        [
            {
                "model": SELECTED_MODEL,
                **overall,
            }
        ]
    )

    overall_df.to_csv(
        REPORT_ROOT
        / "overall_metrics.csv",
        index=False,
    )

    print()
    print(
        "Calculating evaluation by zone..."
    )

    by_zone = evaluate_grouped(
        df,
        "taxi_zone_id",
    )

    by_zone = by_zone.merge(
        zones,
        on="taxi_zone_id",
        how="left",
        validate="one_to_one",
    )

    by_zone = by_zone[
        [
            "taxi_zone_id",
            "taxi_zone_name",
            "borough",
            "observations",
            "actual_mean",
            "predicted_mean",
            "mae",
            "rmse",
            "r2",
            "mape_positive_pct",
            "smape_pct",
            "mean_error_bias",
        ]
    ]

    by_zone.to_csv(
        REPORT_ROOT
        / "by_zone.csv",
        index=False,
    )

    print(
        "Calculating evaluation by hour..."
    )

    by_hour = evaluate_grouped(
        df,
        "hour",
    )

    by_hour.to_csv(
        REPORT_ROOT
        / "by_hour.csv",
        index=False,
    )

    print(
        "Calculating evaluation by day..."
    )

    by_day = evaluate_grouped(
        df,
        "day_of_week_number",
    )

    day_names = (
        df[
            [
                "day_of_week_number",
                "day_of_week",
            ]
        ]
        .drop_duplicates()
    )

    by_day = by_day.merge(
        day_names,
        on="day_of_week_number",
        how="left",
        validate="one_to_one",
    )

    by_day = by_day[
        [
            "day_of_week_number",
            "day_of_week",
            "observations",
            "actual_mean",
            "predicted_mean",
            "mae",
            "rmse",
            "r2",
            "mape_positive_pct",
            "smape_pct",
            "mean_error_bias",
        ]
    ]

    by_day.to_csv(
        REPORT_ROOT
        / "by_day_of_week.csv",
        index=False,
    )

    print(
        "Calculating evaluation by "
        "actual demand level..."
    )

    by_demand = evaluate_grouped(
        df,
        "demand_level",
    )

    by_demand.to_csv(
        REPORT_ROOT
        / "by_demand_level.csv",
        index=False,
    )

    print()
    print("Overall Random Forest metrics:")
    print(
        f"  Observations: "
        f"{overall['observations']:,}"
    )
    print(
        f"  MAE:  "
        f"{overall['mae']:.4f}"
    )
    print(
        f"  RMSE: "
        f"{overall['rmse']:.4f}"
    )
    print(
        f"  R2:   "
        f"{overall['r2']:.4f}"
    )
    print(
        f"  MAPE (actual > 0): "
        f"{overall['mape_positive_pct']:.2f}%"
    )
    print(
        f"  sMAPE: "
        f"{overall['smape_pct']:.2f}%"
    )
    print(
        f"  Mean error bias: "
        f"{overall['mean_error_bias']:.4f}"
    )

    best_zones = (
        by_zone.sort_values(
            ["mae", "rmse"],
            ascending=True,
        )
        .head(5)
    )

    worst_zones = (
        by_zone.sort_values(
            ["mae", "rmse"],
            ascending=False,
        )
        .head(5)
    )

    best_hours = (
        by_hour.sort_values(
            ["mae", "rmse"],
            ascending=True,
        )
        .head(3)
    )

    worst_hours = (
        by_hour.sort_values(
            ["mae", "rmse"],
            ascending=False,
        )
        .head(3)
    )

    print()
    print("Lowest-MAE zones:")
    print(
        best_zones[
            [
                "taxi_zone_id",
                "taxi_zone_name",
                "mae",
                "rmse",
            ]
        ].to_string(
            index=False
        )
    )

    print()
    print("Highest-MAE zones:")
    print(
        worst_zones[
            [
                "taxi_zone_id",
                "taxi_zone_name",
                "mae",
                "rmse",
            ]
        ].to_string(
            index=False
        )
    )

    print()
    print("Lowest-MAE hours:")
    print(
        best_hours[
            [
                "hour",
                "mae",
                "rmse",
            ]
        ].to_string(
            index=False
        )
    )

    print()
    print("Highest-MAE hours:")
    print(
        worst_hours[
            [
                "hour",
                "mae",
                "rmse",
            ]
        ].to_string(
            index=False
        )
    )

    print()
    print("Performance by demand level:")
    print(
        by_demand[
            [
                "demand_level",
                "observations",
                "actual_mean",
                "mae",
                "rmse",
                "mape_positive_pct",
                "smape_pct",
                "mean_error_bias",
            ]
        ].to_string(
            index=False
        )
    )

    print()
    print(
        "PHASE28_MODEL_EVALUATION_SUCCESS"
    )


if __name__ == "__main__":
    main()
