import csv
import json
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_WEATHER_ROOT = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "weather"
    / "year=2025"
)

REPORT_DIR = (
    PROJECT_ROOT
    / "reports"
    / "profiling"
)

EXPECTED_ROWS = 8760

EXPECTED_HOURLY_KEYS = [
    "time",
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "precipitation",
    "rain",
    "snowfall",
    "weather_code",
    "wind_speed_10m",
    "wind_gusts_10m",
]


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    print("=" * 78)
    print("PHASE 6 - WEATHER DATA PROFILING")
    print("=" * 78)
    print(f"Run ID: {run_id}")

    files = sorted(RAW_WEATHER_ROOT.rglob("*.json"))

    if len(files) != 12:
        raise RuntimeError(
            f"Expected 12 weather JSON files, found {len(files)}"
        )

    frames = []
    monthly_schema_rows = []

    for path in files:
        month = path.parent.name.split("=")[-1]

        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        hourly = payload.get("hourly", {})
        keys = list(hourly.keys())

        lengths = {
            key: len(value)
            for key, value in hourly.items()
            if isinstance(value, list)
        }

        unique_lengths = sorted(set(lengths.values()))

        monthly_schema_rows.append(
            {
                "month": f"2025-{month}",
                "file_name": path.name,
                "hourly_key_count": len(keys),
                "hourly_keys": "|".join(keys),
                "matches_expected_hourly_keys": set(keys)
                == set(EXPECTED_HOURLY_KEYS),
                "array_length_count": len(unique_lengths),
                "array_lengths": "|".join(
                    str(v) for v in unique_lengths
                ),
                "row_count": len(hourly.get("time", [])),
            }
        )

        frame = pd.DataFrame(hourly)
        frame["_processing_month"] = int(month)
        frames.append(frame)

    df = pd.concat(frames, ignore_index=True)

    print()
    print("1. ROW COUNT / SCHEMA")
    print("-" * 78)
    print(f"Files: {len(files)}")
    print(f"Rows: {len(df):,}")
    print(f"Expected rows: {EXPECTED_ROWS:,}")
    print(f"Row-count match: {len(df) == EXPECTED_ROWS}")
    print(f"Columns: {len(df.columns) - 1}")
    print("Columns:")
    for column in [c for c in df.columns if c != "_processing_month"]:
        print(f"  - {column}: {df[column].dtype}")

    write_csv(
        REPORT_DIR / "weather_schema_by_month.csv",
        monthly_schema_rows,
        [
            "month",
            "file_name",
            "hourly_key_count",
            "hourly_keys",
            "matches_expected_hourly_keys",
            "array_length_count",
            "array_lengths",
            "row_count",
        ],
    )

    if len(df) != EXPECTED_ROWS:
        raise RuntimeError(
            f"Weather row-count mismatch: {len(df):,} != {EXPECTED_ROWS:,}"
        )

    print()
    print("2. MISSING VALUES")
    print("-" * 78)

    missing_rows = []

    for column in [c for c in df.columns if c != "_processing_month"]:
        count = int(df[column].isna().sum())
        missing_rows.append(
            {
                "column_name": column,
                "missing_count": count,
                "missing_percent": round(count / len(df) * 100, 6),
            }
        )
        print(
            f"{column}: {count:,} "
            f"({count / len(df) * 100:.4f}%)"
        )

    write_csv(
        REPORT_DIR / "weather_missing_values.csv",
        missing_rows,
        ["column_name", "missing_count", "missing_percent"],
    )

    print()
    print("3. TIME RANGE / DUPLICATES / GAPS")
    print("-" * 78)

    timestamps = pd.to_datetime(df["time"], errors="coerce")

    timestamp_min = timestamps.min()
    timestamp_max = timestamps.max()
    invalid_timestamp_count = int(timestamps.isna().sum())
    duplicate_timestamp_count = int(timestamps.duplicated().sum())

    valid_times = timestamps.dropna().sort_values()
    hour_diffs = valid_times.diff().dropna()
    non_hourly_gap_count = int(
        (hour_diffs != pd.Timedelta(hours=1)).sum()
    )

    expected_index = pd.date_range(
        "2025-01-01 00:00:00",
        "2025-12-31 23:00:00",
        freq="h",
    )

    actual_index = pd.DatetimeIndex(valid_times.unique())

    missing_expected_hours = expected_index.difference(actual_index)
    unexpected_hours = actual_index.difference(expected_index)

    print(f"Minimum timestamp: {timestamp_min}")
    print(f"Maximum timestamp: {timestamp_max}")
    print(f"Unparseable timestamps: {invalid_timestamp_count:,}")
    print(f"Duplicate timestamps: {duplicate_timestamp_count:,}")
    print(f"Non-hourly adjacent gaps: {non_hourly_gap_count:,}")
    print(f"Missing expected 2025 hours: {len(missing_expected_hours):,}")
    print(f"Unexpected timestamps outside expected grid: {len(unexpected_hours):,}")

    definitely_invalid = [
        {
            "classification": "DEFINITELY_INVALID",
            "check_name": "MISSING_OR_UNPARSEABLE_TIMESTAMP",
            "description": "Hourly timestamp is missing or unparseable.",
            "record_count": invalid_timestamp_count,
        },
        {
            "classification": "DEFINITELY_INVALID",
            "check_name": "DUPLICATE_TIMESTAMP",
            "description": "Duplicate hourly timestamp.",
            "record_count": duplicate_timestamp_count,
        },
        {
            "classification": "DEFINITELY_INVALID",
            "check_name": "MISSING_EXPECTED_HOUR",
            "description": "Expected 2025 hourly timestamp is absent.",
            "record_count": len(missing_expected_hours),
        },
        {
            "classification": "DEFINITELY_INVALID",
            "check_name": "UNEXPECTED_TIMESTAMP",
            "description": "Timestamp lies outside the expected 2025 hourly grid.",
            "record_count": len(unexpected_hours),
        },
    ]

    write_csv(
        REPORT_DIR / "weather_definitely_invalid.csv",
        definitely_invalid,
        [
            "classification",
            "check_name",
            "description",
            "record_count",
        ],
    )

    print()
    print("4. OUTLIERS / CANDIDATE ANOMALIES")
    print("-" * 78)

    numeric_columns = [
        "temperature_2m",
        "relative_humidity_2m",
        "apparent_temperature",
        "precipitation",
        "rain",
        "snowfall",
        "weather_code",
        "wind_speed_10m",
        "wind_gusts_10m",
    ]

    outlier_rows = []

    for column in numeric_columns:
        series = pd.to_numeric(df[column], errors="coerce")

        outlier_rows.append(
            {
                "column_name": column,
                "min": series.min(),
                "p01": series.quantile(0.01),
                "p50": series.quantile(0.50),
                "p95": series.quantile(0.95),
                "p99": series.quantile(0.99),
                "max": series.max(),
            }
        )

        print(
            f"{column}: min={series.min()}, "
            f"p50={series.quantile(0.50)}, "
            f"p99={series.quantile(0.99)}, "
            f"max={series.max()}"
        )

    write_csv(
        REPORT_DIR / "weather_outlier_quantiles.csv",
        outlier_rows,
        [
            "column_name",
            "min",
            "p01",
            "p50",
            "p95",
            "p99",
            "max",
        ],
    )

    humidity = pd.to_numeric(
        df["relative_humidity_2m"],
        errors="coerce",
    )
    precipitation = pd.to_numeric(
        df["precipitation"],
        errors="coerce",
    )
    rain = pd.to_numeric(
        df["rain"],
        errors="coerce",
    )
    snowfall = pd.to_numeric(
        df["snowfall"],
        errors="coerce",
    )
    wind = pd.to_numeric(
        df["wind_speed_10m"],
        errors="coerce",
    )
    gust = pd.to_numeric(
        df["wind_gusts_10m"],
        errors="coerce",
    )
    temperature = pd.to_numeric(
        df["temperature_2m"],
        errors="coerce",
    )

    candidate_rows = [
        {
            "classification": "CANDIDATE_ANOMALY",
            "check_name": "TEMPERATURE_OUTSIDE_PLAUSIBLE_NYC_RANGE",
            "description": (
                "Temperature is below -30 C or above 50 C; investigate before rule definition."
            ),
            "record_count": int(
                ((temperature < -30) | (temperature > 50)).sum()
            ),
        },
        {
            "classification": "CANDIDATE_ANOMALY",
            "check_name": "HUMIDITY_OUTSIDE_0_100",
            "description": "Relative humidity is outside 0-100 percent.",
            "record_count": int(
                ((humidity < 0) | (humidity > 100)).sum()
            ),
        },
        {
            "classification": "CANDIDATE_ANOMALY",
            "check_name": "NEGATIVE_PRECIPITATION",
            "description": "Precipitation is negative.",
            "record_count": int((precipitation < 0).sum()),
        },
        {
            "classification": "CANDIDATE_ANOMALY",
            "check_name": "NEGATIVE_RAIN",
            "description": "Rain is negative.",
            "record_count": int((rain < 0).sum()),
        },
        {
            "classification": "CANDIDATE_ANOMALY",
            "check_name": "NEGATIVE_SNOWFALL",
            "description": "Snowfall is negative.",
            "record_count": int((snowfall < 0).sum()),
        },
        {
            "classification": "CANDIDATE_ANOMALY",
            "check_name": "NEGATIVE_WIND_SPEED",
            "description": "Wind speed is negative.",
            "record_count": int((wind < 0).sum()),
        },
        {
            "classification": "CANDIDATE_ANOMALY",
            "check_name": "NEGATIVE_WIND_GUST",
            "description": "Wind gust is negative.",
            "record_count": int((gust < 0).sum()),
        },
    ]

    for row in candidate_rows:
        print(f"{row['check_name']}: {row['record_count']:,}")

    write_csv(
        REPORT_DIR / "weather_candidate_anomalies.csv",
        candidate_rows,
        [
            "classification",
            "check_name",
            "description",
            "record_count",
        ],
    )

    print()
    print("5. FINAL SUMMARY")
    print("-" * 78)

    summary = {
        "run_id": run_id,
        "source": "open_meteo_weather",
        "profile_year": 2025,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "raw_file_count": len(files),
        "row_count": len(df),
        "expected_row_count": EXPECTED_ROWS,
        "row_count_match": len(df) == EXPECTED_ROWS,
        "column_count": len(EXPECTED_HOURLY_KEYS),
        "hourly_columns": EXPECTED_HOURLY_KEYS,
        "timestamp_min": str(timestamp_min),
        "timestamp_max": str(timestamp_max),
        "duplicate_timestamp_count": duplicate_timestamp_count,
        "missing_expected_hours": len(missing_expected_hours),
        "unexpected_timestamps": len(unexpected_hours),
        "monthly_schema_problems": [
            row["month"]
            for row in monthly_schema_rows
            if (
                not row["matches_expected_hourly_keys"]
                or row["array_length_count"] != 1
            )
        ],
        "definitely_invalid": {
            row["check_name"]: row["record_count"]
            for row in definitely_invalid
        },
        "candidate_anomalies": {
            row["check_name"]: row["record_count"]
            for row in candidate_rows
        },
        "status": "SUCCESS",
    }

    with open(
        REPORT_DIR / "weather_profile_summary.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(summary, f, indent=2)

    print(f"Rows profiled: {len(df):,}")
    print(f"Duplicate timestamps: {duplicate_timestamp_count:,}")
    print(f"Missing expected hours: {len(missing_expected_hours):,}")
    print(f"Reports: {REPORT_DIR}")
    print()
    print("WEATHER DATA PROFILING SUCCESS")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print()
        print("WEATHER DATA PROFILING FAILED")
        print(f"Error: {exc}")
        sys.exit(1)
