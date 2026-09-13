from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SOURCE_ROOT = PROJECT_ROOT / "data" / "gold" / "zone_hourly"
FEATURE_ROOT = PROJECT_ROOT / "data" / "gold" / "ml_features"

TEST_ZONES = [1, 132, 263]


def main() -> None:
    source_ds = ds.dataset(
        SOURCE_ROOT,
        format="parquet",
        partitioning="hive",
    )

    feature_ds = ds.dataset(
        FEATURE_ROOT,
        format="parquet",
        partitioning="hive",
    )

    zone_filter = ds.field("taxi_zone_id").isin(TEST_ZONES)

    source = source_ds.to_table(
        columns=[
            "date",
            "hour",
            "taxi_zone_id",
            "taxi_trips",
            "complaints_311",
        ],
        filter=zone_filter,
    ).to_pandas()

    source["timestamp"] = (
        pd.to_datetime(source["date"])
        + pd.to_timedelta(source["hour"], unit="h")
    )

    source = source.sort_values(
        ["taxi_zone_id", "timestamp"]
    ).reset_index(drop=True)

    groups = source.groupby(
        "taxi_zone_id",
        sort=False,
        observed=True,
    )

    source["expected_lag_1h"] = groups["taxi_trips"].shift(1)
    source["expected_lag_24h"] = groups["taxi_trips"].shift(24)
    source["expected_lag_168h"] = groups["taxi_trips"].shift(168)

    source["expected_complaints_lag_1h"] = (
        groups["complaints_311"].shift(1)
    )

    source["expected_complaints_lag_24h"] = (
        groups["complaints_311"].shift(24)
    )

    source = source.loc[
        source["expected_lag_168h"].notna()
    ].copy()

    features = feature_ds.to_table(
        columns=[
            "timestamp",
            "taxi_zone_id",
            "lag_1h",
            "lag_24h",
            "lag_168h",
            "complaints_lag_1h",
            "complaints_lag_24h",
        ],
        filter=zone_filter,
    ).to_pandas()

    merged = features.merge(
        source[
            [
                "timestamp",
                "taxi_zone_id",
                "expected_lag_1h",
                "expected_lag_24h",
                "expected_lag_168h",
                "expected_complaints_lag_1h",
                "expected_complaints_lag_24h",
            ]
        ],
        on=["timestamp", "taxi_zone_id"],
        how="inner",
        validate="one_to_one",
    )

    expected_rows = 3 * 8_592

    if len(merged) != expected_rows:
        raise ValueError(
            f"Unexpected validation rows: {len(merged):,}. "
            f"Expected {expected_rows:,}."
        )

    checks = {
        "lag_1h": "expected_lag_1h",
        "lag_24h": "expected_lag_24h",
        "lag_168h": "expected_lag_168h",
        "complaints_lag_1h": "expected_complaints_lag_1h",
        "complaints_lag_24h": "expected_complaints_lag_24h",
    }

    for actual, expected in checks.items():
        matches = np.allclose(
            merged[actual].to_numpy(),
            merged[expected].to_numpy(),
            equal_nan=False,
        )

        if not matches:
            raise ValueError(
                f"Lag alignment failed for {actual}"
            )

        print(f"{actual}: PASS")

    print()
    print(f"Zones validated: {TEST_ZONES}")
    print(f"Rows compared: {len(merged):,}")
    print("All historical lag values match source Gold data.")
    print()
    print("PHASE24_LAG_ALIGNMENT_SUCCESS")


if __name__ == "__main__":
    main()
