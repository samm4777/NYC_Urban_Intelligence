from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SOURCE_ROOT = PROJECT_ROOT / "data" / "gold" / "zone_hourly"
OUTPUT_ROOT = PROJECT_ROOT / "data" / "gold" / "ml_features"

EXPECTED_SOURCE_ROWS = 2_303_880
EXPECTED_ZONES = 263
EXPECTED_DATES = 365
EXPECTED_HOURS_PER_ZONE = 8_760
EXPECTED_WARMUP_ROWS = 44_184
EXPECTED_MODEL_READY_ROWS = 2_259_696


SOURCE_COLUMNS = [
    "date",
    "hour",
    "taxi_zone_id",
    "taxi_zone_name",
    "borough",
    "taxi_trips",
    "complaints_311",
    "temperature_c",
    "rain_mm",
    "snowfall_cm",
    "weather_condition",
]


def load_gold() -> pd.DataFrame:
    dataset = ds.dataset(
        SOURCE_ROOT,
        format="parquet",
        partitioning="hive",
    )

    table = dataset.to_table(columns=SOURCE_COLUMNS)
    return table.to_pandas()


def validate_source(df: pd.DataFrame) -> None:
    if len(df) != EXPECTED_SOURCE_ROWS:
        raise ValueError(
            f"Unexpected Gold row count: {len(df):,}. "
            f"Expected {EXPECTED_SOURCE_ROWS:,}."
        )

    zone_count = df["taxi_zone_id"].nunique()
    if zone_count != EXPECTED_ZONES:
        raise ValueError(
            f"Unexpected zone count: {zone_count}. "
            f"Expected {EXPECTED_ZONES}."
        )

    date_count = df["date"].nunique()
    if date_count != EXPECTED_DATES:
        raise ValueError(
            f"Unexpected date count: {date_count}. "
            f"Expected {EXPECTED_DATES}."
        )

    rows_per_zone = df.groupby("taxi_zone_id", observed=True).size()

    if not (rows_per_zone == EXPECTED_HOURS_PER_ZONE).all():
        bad = rows_per_zone[
            rows_per_zone != EXPECTED_HOURS_PER_ZONE
        ]

        raise ValueError(
            "Gold is not a complete hourly grid for every zone. "
            f"Unexpected zones:\n{bad}"
        )


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["timestamp"] = (
        pd.to_datetime(df["date"])
        + pd.to_timedelta(df["hour"], unit="h")
    )

    df = df.sort_values(
        ["taxi_zone_id", "timestamp"],
        kind="mergesort",
    ).reset_index(drop=True)

    zone_groups = df.groupby(
        "taxi_zone_id",
        sort=False,
        observed=True,
    )

    df["lag_1h"] = zone_groups["taxi_trips"].shift(1)
    df["lag_24h"] = zone_groups["taxi_trips"].shift(24)
    df["lag_168h"] = zone_groups["taxi_trips"].shift(168)

    df["complaints_lag_1h"] = (
        zone_groups["complaints_311"].shift(1)
    )

    df["complaints_lag_24h"] = (
        zone_groups["complaints_311"].shift(24)
    )

    df["day_of_week"] = df["timestamp"].dt.dayofweek.astype("int8")
    df["month"] = df["timestamp"].dt.month.astype("int32")
    df["year"] = df["timestamp"].dt.year.astype("int32")

    df["is_weekend"] = (
        df["day_of_week"] >= 5
    ).astype("int8")

    complete_columns = [
        "lag_1h",
        "lag_24h",
        "lag_168h",
        "complaints_lag_1h",
        "complaints_lag_24h",
    ]

    df["is_feature_complete"] = (
        df[complete_columns]
        .notna()
        .all(axis=1)
    )

    return df


def validate_features(df: pd.DataFrame) -> None:
    incomplete_rows = int((~df["is_feature_complete"]).sum())

    if incomplete_rows != EXPECTED_WARMUP_ROWS:
        raise ValueError(
            f"Unexpected lag warm-up rows: {incomplete_rows:,}. "
            f"Expected {EXPECTED_WARMUP_ROWS:,}."
        )

    ready_rows = int(df["is_feature_complete"].sum())

    if ready_rows != EXPECTED_MODEL_READY_ROWS:
        raise ValueError(
            f"Unexpected model-ready row count: {ready_rows:,}. "
            f"Expected {EXPECTED_MODEL_READY_ROWS:,}."
        )

    leakage_columns = {
        "taxi_revenue",
        "average_fare",
        "average_trip_distance",
    }

    present = leakage_columns.intersection(df.columns)

    if present:
        raise ValueError(
            f"Leakage-prone outcome columns found: {sorted(present)}"
        )


def write_features(df: pd.DataFrame) -> None:
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    model_ready = df.loc[
        df["is_feature_complete"]
    ].copy()

    output_columns = [
        "timestamp",
        "date",
        "hour",
        "day_of_week",
        "month",
        "year",
        "is_weekend",
        "taxi_zone_id",
        "taxi_zone_name",
        "borough",
        "temperature_c",
        "rain_mm",
        "snowfall_cm",
        "weather_condition",
        "complaints_lag_1h",
        "complaints_lag_24h",
        "lag_1h",
        "lag_24h",
        "lag_168h",
        "taxi_trips",
    ]

    model_ready = model_ready[output_columns]

    for month in range(1, 13):
        month_df = model_ready[
            model_ready["month"] == month
        ].copy()

        month_dir = (
            OUTPUT_ROOT
            / "year=2025"
            / f"month={month:02d}"
        )

        month_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        table = pa.Table.from_pandas(
            month_df,
            preserve_index=False,
        )

        pq.write_table(
            table,
            month_dir / "features.parquet",
            compression="snappy",
        )


def main() -> None:
    print("Loading full-year Gold dataset...")
    df = load_gold()

    print(f"Source rows: {len(df):,}")

    validate_source(df)

    print("Building leakage-safe temporal features...")
    features = build_features(df)

    validate_features(features)

    ready_rows = int(
        features["is_feature_complete"].sum()
    )

    warmup_rows = len(features) - ready_rows

    print(f"Lag warm-up rows: {warmup_rows:,}")
    print(f"Model-ready rows: {ready_rows:,}")

    print("Writing monthly ML feature partitions...")
    write_features(features)

    print("PHASE24_FEATURE_BUILD_SUCCESS")


if __name__ == "__main__":
    main()


