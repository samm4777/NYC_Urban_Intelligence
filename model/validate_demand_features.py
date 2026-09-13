from pathlib import Path

import pandas as pd
import pyarrow.dataset as ds


PROJECT_ROOT = Path(__file__).resolve().parents[1]

FEATURE_ROOT = PROJECT_ROOT / "data" / "gold" / "ml_features"

EXPECTED_ROWS = 2_259_696
EXPECTED_ZONES = 263
EXPECTED_MONTHS = 12
EXPECTED_ROWS_PER_ZONE = 8_592

EXPECTED_COLUMNS = {
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
}

FORBIDDEN_COLUMNS = {
    "taxi_revenue",
    "average_fare",
    "average_trip_distance",
    "complaints_311",
}


def main() -> None:
    dataset = ds.dataset(
        FEATURE_ROOT,
        format="parquet",
        partitioning="hive",
    )

    print("Feature schema:")
    print(dataset.schema)

    columns = set(dataset.schema.names)

    missing = EXPECTED_COLUMNS - columns
    if missing:
        raise ValueError(
            f"Missing expected feature columns: {sorted(missing)}"
        )

    leakage = FORBIDDEN_COLUMNS.intersection(columns)
    if leakage:
        raise ValueError(
            f"Leakage-prone columns found: {sorted(leakage)}"
        )

    table = dataset.to_table(
        columns=[
            "timestamp",
            "taxi_zone_id",
            "month",
            "lag_1h",
            "lag_24h",
            "lag_168h",
            "complaints_lag_1h",
            "complaints_lag_24h",
            "taxi_trips",
        ]
    )

    df = table.to_pandas()

    if len(df) != EXPECTED_ROWS:
        raise ValueError(
            f"Unexpected feature row count: {len(df):,}. "
            f"Expected {EXPECTED_ROWS:,}."
        )

    zone_count = df["taxi_zone_id"].nunique()
    if zone_count != EXPECTED_ZONES:
        raise ValueError(
            f"Unexpected zone count: {zone_count}. "
            f"Expected {EXPECTED_ZONES}."
        )

    month_count = df["month"].nunique()
    if month_count != EXPECTED_MONTHS:
        raise ValueError(
            f"Unexpected month count: {month_count}. "
            f"Expected {EXPECTED_MONTHS}."
        )

    duplicate_count = int(
        df.duplicated(
            subset=["taxi_zone_id", "timestamp"]
        ).sum()
    )

    if duplicate_count != 0:
        raise ValueError(
            f"Duplicate Zone x Hour rows found: {duplicate_count:,}"
        )

    rows_per_zone = (
        df.groupby("taxi_zone_id", observed=True)
        .size()
    )

    if not (rows_per_zone == EXPECTED_ROWS_PER_ZONE).all():
        raise ValueError(
            "Unexpected model-ready row count for one or more zones."
        )

    lag_columns = [
        "lag_1h",
        "lag_24h",
        "lag_168h",
        "complaints_lag_1h",
        "complaints_lag_24h",
    ]

    null_lags = df[lag_columns].isna().sum()

    if int(null_lags.sum()) != 0:
        raise ValueError(
            f"Null lag values found:\n{null_lags}"
        )

    first_timestamp = pd.to_datetime(
        df["timestamp"]
    ).min()

    last_timestamp = pd.to_datetime(
        df["timestamp"]
    ).max()

    if first_timestamp != pd.Timestamp("2025-01-08 00:00:00"):
        raise ValueError(
            f"Unexpected first timestamp: {first_timestamp}"
        )

    if last_timestamp != pd.Timestamp("2025-12-31 23:00:00"):
        raise ValueError(
            f"Unexpected last timestamp: {last_timestamp}"
        )

    monthly_counts = (
        df.groupby("month", observed=True)
        .size()
        .sort_index()
    )

    print()
    print("Monthly model-ready rows:")
    print(monthly_counts.to_string())

    print()
    print(f"Total rows: {len(df):,}")
    print(f"Zones: {zone_count}")
    print(f"Months: {month_count}")
    print(f"Duplicate zone-hours: {duplicate_count:,}")
    print(f"First timestamp: {first_timestamp}")
    print(f"Last timestamp: {last_timestamp}")
    print(f"Rows per zone: {EXPECTED_ROWS_PER_ZONE:,}")
    print("Leakage-prone outcome columns: NONE")
    print("Null lag values: NONE")

    print()
    print("PHASE24_FEATURE_VALIDATION_SUCCESS")


if __name__ == "__main__":
    main()
