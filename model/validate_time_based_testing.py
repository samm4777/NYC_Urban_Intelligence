from __future__ import annotations

from pathlib import Path
from datetime import timedelta

import numpy as np
import pandas as pd
import pyarrow.dataset as ds


PROJECT_ROOT = Path(__file__).resolve().parents[1]

GOLD_ROOT = (
    PROJECT_ROOT
    / "data"
    / "gold"
    / "zone_hourly"
)

FEATURE_ROOT = (
    PROJECT_ROOT
    / "data"
    / "gold"
    / "ml_features"
)

TRAIN_START = pd.Timestamp("2025-01-08 00:00:00")
TRAIN_END = pd.Timestamp("2025-10-31 23:00:00")

TEST_START = pd.Timestamp("2025-11-01 00:00:00")
TEST_END = pd.Timestamp("2025-12-31 23:00:00")

EXPECTED_GOLD_ROWS = 2_303_880
EXPECTED_FEATURE_ROWS = 2_259_696
EXPECTED_TRAIN_ROWS = 1_874_664
EXPECTED_TEST_ROWS = 385_032
EXPECTED_ZONES = 263

FORBIDDEN_FEATURE_COLUMNS = {
    "taxi_revenue",
    "average_fare",
    "average_trip_distance",
    "complaints_311",
}


def load_gold() -> pd.DataFrame:
    dataset = ds.dataset(
        GOLD_ROOT,
        format="parquet",
        partitioning="hive",
    )

    table = dataset.to_table(
        columns=[
            "date",
            "hour",
            "taxi_zone_id",
            "taxi_trips",
            "complaints_311",
        ]
    )

    df = table.to_pandas()

    df["timestamp"] = (
        pd.to_datetime(df["date"])
        + pd.to_timedelta(
            df["hour"],
            unit="h",
        )
    )

    return df


def load_features() -> pd.DataFrame:
    dataset = ds.dataset(
        FEATURE_ROOT,
        format="parquet",
        partitioning="hive",
    )

    columns = set(
        dataset.schema.names
    )

    leakage_columns = (
        FORBIDDEN_FEATURE_COLUMNS
        .intersection(columns)
    )

    if leakage_columns:
        raise ValueError(
            "Leakage-prone same-hour columns "
            f"found in ML dataset: "
            f"{sorted(leakage_columns)}"
        )

    table = dataset.to_table(
        columns=[
            "timestamp",
            "taxi_zone_id",
            "taxi_trips",
            "lag_1h",
            "lag_24h",
            "lag_168h",
            "complaints_lag_1h",
            "complaints_lag_24h",
        ]
    )

    df = table.to_pandas()

    df["timestamp"] = pd.to_datetime(
        df["timestamp"]
    )

    return df


def validate_gold_grid(
    gold: pd.DataFrame,
) -> None:

    if len(gold) != EXPECTED_GOLD_ROWS:
        raise ValueError(
            f"Unexpected Gold rows: "
            f"{len(gold):,}"
        )

    if (
        gold["taxi_zone_id"].nunique()
        != EXPECTED_ZONES
    ):
        raise ValueError(
            "Unexpected Gold zone count."
        )

    duplicates = gold.duplicated(
        subset=[
            "taxi_zone_id",
            "timestamp",
        ]
    ).sum()

    if duplicates != 0:
        raise ValueError(
            f"Duplicate Gold zone-hours: "
            f"{duplicates:,}"
        )

    gold.sort_values(
        [
            "taxi_zone_id",
            "timestamp",
        ],
        inplace=True,
        kind="mergesort",
    )

    gold.reset_index(
        drop=True,
        inplace=True,
    )

    gaps = (
        gold.groupby(
            "taxi_zone_id",
            sort=False,
            observed=True,
        )["timestamp"]
        .diff()
    )

    invalid_gaps = (
        gaps.notna()
        & (
            gaps
            != timedelta(hours=1)
        )
    )

    if invalid_gaps.any():
        raise ValueError(
            "Non-hourly gaps detected in "
            "the source Gold grid."
        )


def build_expected_lags(
    gold: pd.DataFrame,
) -> pd.DataFrame:

    groups = gold.groupby(
        "taxi_zone_id",
        sort=False,
        observed=True,
    )

    gold["expected_lag_1h"] = (
        groups["taxi_trips"]
        .shift(1)
    )

    gold["expected_lag_24h"] = (
        groups["taxi_trips"]
        .shift(24)
    )

    gold["expected_lag_168h"] = (
        groups["taxi_trips"]
        .shift(168)
    )

    gold[
        "expected_complaints_lag_1h"
    ] = (
        groups["complaints_311"]
        .shift(1)
    )

    gold[
        "expected_complaints_lag_24h"
    ] = (
        groups["complaints_311"]
        .shift(24)
    )

    expected = gold.loc[
        gold["expected_lag_168h"]
        .notna(),
        [
            "timestamp",
            "taxi_zone_id",
            "taxi_trips",
            "expected_lag_1h",
            "expected_lag_24h",
            "expected_lag_168h",
            "expected_complaints_lag_1h",
            "expected_complaints_lag_24h",
        ],
    ].copy()

    return expected


def validate_temporal_split(
    features: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:

    if len(features) != EXPECTED_FEATURE_ROWS:
        raise ValueError(
            f"Unexpected feature rows: "
            f"{len(features):,}"
        )

    train = features.loc[
        (
            features["timestamp"]
            >= TRAIN_START
        )
        & (
            features["timestamp"]
            <= TRAIN_END
        )
    ]

    test = features.loc[
        (
            features["timestamp"]
            >= TEST_START
        )
        & (
            features["timestamp"]
            <= TEST_END
        )
    ]

    if len(train) != EXPECTED_TRAIN_ROWS:
        raise ValueError(
            f"Unexpected training rows: "
            f"{len(train):,}"
        )

    if len(test) != EXPECTED_TEST_ROWS:
        raise ValueError(
            f"Unexpected test rows: "
            f"{len(test):,}"
        )

    if (
        train["timestamp"].max()
        >= test["timestamp"].min()
    ):
        raise ValueError(
            "Training/test temporal overlap "
            "detected."
        )

    return train, test


def validate_all_lags(
    features: pd.DataFrame,
    expected: pd.DataFrame,
) -> None:

    features = features.sort_values(
        [
            "taxi_zone_id",
            "timestamp",
        ],
        kind="mergesort",
    ).reset_index(drop=True)

    expected = expected.sort_values(
        [
            "taxi_zone_id",
            "timestamp",
        ],
        kind="mergesort",
    ).reset_index(drop=True)

    if len(features) != len(expected):
        raise ValueError(
            "Feature/source lag row counts "
            "do not match."
        )

    if not np.array_equal(
        features[
            "taxi_zone_id"
        ].to_numpy(),
        expected[
            "taxi_zone_id"
        ].to_numpy(),
    ):
        raise ValueError(
            "Taxi-zone alignment mismatch."
        )

    if not np.array_equal(
        features[
            "timestamp"
        ].to_numpy(),
        expected[
            "timestamp"
        ].to_numpy(),
    ):
        raise ValueError(
            "Timestamp alignment mismatch."
        )

    comparisons = {
        "lag_1h":
            "expected_lag_1h",

        "lag_24h":
            "expected_lag_24h",

        "lag_168h":
            "expected_lag_168h",

        "complaints_lag_1h":
            "expected_complaints_lag_1h",

        "complaints_lag_24h":
            "expected_complaints_lag_24h",
    }

    for actual, reference in (
        comparisons.items()
    ):

        if not np.array_equal(
            features[actual].to_numpy(),
            expected[reference].to_numpy(),
        ):
            raise ValueError(
                f"Historical alignment failed: "
                f"{actual}"
            )

        print(
            f"{actual}: "
            "FULL-DATA PASS"
        )


def print_first_test_boundary(
    features: pd.DataFrame,
) -> None:

    first = features.loc[
        features["timestamp"]
        == TEST_START
    ].iloc[0]

    print()
    print(
        "First test prediction timestamp:"
    )
    print(
        f"  target:   {TEST_START}"
    )
    print(
        "  lag_1h source time:   "
        f"{TEST_START - timedelta(hours=1)}"
    )
    print(
        "  lag_24h source time:  "
        f"{TEST_START - timedelta(hours=24)}"
    )
    print(
        "  lag_168h source time: "
        f"{TEST_START - timedelta(hours=168)}"
    )

    if pd.isna(first["lag_168h"]):
        raise ValueError(
            "First test observation has "
            "missing historical lag."
        )


def main() -> None:
    print(
        "Loading full-year Gold source..."
    )

    gold = load_gold()

    print(
        f"Gold rows: "
        f"{len(gold):,}"
    )

    print()
    print(
        "Validating complete hourly "
        "zone grid..."
    )

    validate_gold_grid(gold)

    print(
        "Hourly Gold continuity: PASS"
    )

    print()
    print(
        "Reconstructing lag values "
        "independently from Gold..."
    )

    expected = build_expected_lags(
        gold
    )

    print()
    print(
        "Loading model-ready features..."
    )

    features = load_features()

    train, test = (
        validate_temporal_split(
            features
        )
    )

    print()
    print("Temporal split:")
    print(
        f"  Train start: "
        f"{train['timestamp'].min()}"
    )
    print(
        f"  Train end:   "
        f"{train['timestamp'].max()}"
    )
    print(
        f"  Train rows:  "
        f"{len(train):,}"
    )

    print(
        f"  Test start:  "
        f"{test['timestamp'].min()}"
    )
    print(
        f"  Test end:    "
        f"{test['timestamp'].max()}"
    )
    print(
        f"  Test rows:   "
        f"{len(test):,}"
    )

    print()
    print(
        "Train/test temporal overlap: NONE"
    )

    print(
        "Random historical/future mixing: NONE"
    )

    print(
        "Same-hour outcome leakage "
        "columns: NONE"
    )

    print()
    print(
        "Auditing historical lag values "
        f"across all "
        f"{len(features):,} model rows..."
    )

    validate_all_lags(
        features,
        expected,
    )

    print_first_test_boundary(
        features
    )

    print()
    print(
        "Forecast protocol: "
        "rolling hourly prediction"
    )

    print(
        "All lag predictors reference "
        "observations strictly earlier "
        "than the target hour."
    )

    print()
    print(
        "Weather note: target-hour "
        "historical observed weather is "
        "treated as a proxy for weather "
        "forecast information that would "
        "need to be available operationally."
    )

    print()
    print(
        "PHASE27_TIME_BASED_TESTING_SUCCESS"
    )


if __name__ == "__main__":
    main()

