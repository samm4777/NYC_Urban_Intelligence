#!/usr/bin/env python
"""
Phase 11 - Open-Meteo Weather Silver preparation.

Reads 2025 monthly Open-Meteo Raw JSON files and writes an analysis-ready,
hourly Silver weather dataset.

Key contracts:
- Grain: one row per NYC local wall-clock hour.
- 2025 must contain exactly 8,760 unique expected hourly labels.
- Missing hours are documented and FAIL publication; they are never imputed.
- Duplicate timestamps, out-of-period timestamps, schema mismatches, or
  physically invalid measurements FAIL publication.
- Raw weather values are never silently filled or altered.
"""

from __future__ import annotations

import argparse
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_WEATHER_ROOT = PROJECT_ROOT / "data" / "raw" / "weather" / "year=2025"
SILVER_WEATHER_ROOT = PROJECT_ROOT / "data" / "silver" / "weather" / "year=2025"

PROFILE_SUMMARY = PROJECT_ROOT / "reports" / "profiling" / "weather_profile_summary.json"
RECONCILIATION_REPORT = (
    PROJECT_ROOT / "reports" / "reconciliation" / "weather_silver_reconciliation.csv"
)
GAP_REPORT = PROJECT_ROOT / "reports" / "reconciliation" / "weather_gap_report.csv"
RUN_LOG = PROJECT_ROOT / "logs" / "pipeline_runs.jsonl"

EXPECTED_FULL_YEAR_ROWS = 8_760
EXPECTED_TIMEZONE = "America/New_York"

HOURLY_KEYS = [
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

# Open-Meteo WMO weather interpretation codes.
WEATHER_CODE_MAP = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

SILVER_SCHEMA = pa.schema(
    [
        pa.field("weather_timestamp", pa.timestamp("us"), nullable=False),
        pa.field("weather_date", pa.date32(), nullable=False),
        pa.field("weather_hour", pa.int32(), nullable=False),
        pa.field("weather_timezone", pa.string(), nullable=False),
        pa.field("temperature_c", pa.float64(), nullable=False),
        pa.field("relative_humidity_pct", pa.float64(), nullable=False),
        pa.field("apparent_temperature_c", pa.float64(), nullable=False),
        pa.field("precipitation_mm", pa.float64(), nullable=False),
        pa.field("rain_mm", pa.float64(), nullable=False),
        pa.field("snowfall_cm", pa.float64(), nullable=False),
        pa.field("weather_code", pa.int32(), nullable=False),
        pa.field("weather_condition", pa.string(), nullable=False),
        pa.field("wind_speed_kmh", pa.float64(), nullable=False),
        pa.field("wind_gust_kmh", pa.float64(), nullable=False),
        pa.field("is_weather_gap", pa.bool_(), nullable=False),
        pa.field("source_latitude", pa.float64()),
        pa.field("source_longitude", pa.float64()),
        pa.field("source_elevation_m", pa.float64()),
        pa.field("_source", pa.string(), nullable=False),
        pa.field("_source_file", pa.string(), nullable=False),
        pa.field("_run_id", pa.string(), nullable=False),
        pa.field("_processed_at", pa.timestamp("us"), nullable=False),
        pa.field("_processing_year", pa.int32(), nullable=False),
        pa.field("_processing_month", pa.int32(), nullable=False),
    ]
)


def write_run_log(record: dict) -> None:
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RUN_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


def load_profile_contract() -> dict:
    if not PROFILE_SUMMARY.exists():
        raise FileNotFoundError(f"Weather profile summary not found: {PROFILE_SUMMARY}")

    with PROFILE_SUMMARY.open("r", encoding="utf-8") as f:
        profile = json.load(f)

    checks = {
        "row_count": EXPECTED_FULL_YEAR_ROWS,
        "expected_row_count": EXPECTED_FULL_YEAR_ROWS,
        "row_count_match": True,
        "duplicate_timestamp_count": 0,
        "missing_expected_hours": 0,
        "unexpected_timestamps": 0,
        "status": "SUCCESS",
    }

    for key, expected in checks.items():
        actual = profile.get(key)
        if actual != expected:
            raise RuntimeError(
                f"PROFILE_CONTRACT_FAILURE: {key} expected {expected!r}, found {actual!r}"
            )

    if profile.get("monthly_schema_problems") != []:
        raise RuntimeError(
            "PROFILE_CONTRACT_FAILURE: Phase 6 reported monthly schema problems"
        )

    return profile


def expected_month_grid(month: int) -> pd.DatetimeIndex:
    start = pd.Timestamp(year=2025, month=month, day=1, hour=0)
    if month == 12:
        end = pd.Timestamp("2026-01-01 00:00:00")
    else:
        end = pd.Timestamp(year=2025, month=month + 1, day=1, hour=0)

    # Deliberately a naive NYC local wall-clock grid, matching the Open-Meteo
    # response labels and the Yellow Taxi local timestamp semantics used by Gold.
    return pd.date_range(start=start, end=end, inclusive="left", freq="h")


def load_month_payload(month: int) -> tuple[Path, dict]:
    mt = f"{month:02d}"
    path = (
        RAW_WEATHER_ROOT
        / f"month={mt}"
        / f"weather_nyc_2025_{mt}.json"
    )

    if not path.exists():
        raise FileNotFoundError(f"Weather Raw file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    return path, payload


def validate_payload_structure(payload: dict, source_file: Path) -> dict:
    if payload.get("timezone") != EXPECTED_TIMEZONE:
        raise RuntimeError(
            "WEATHER_TIMEZONE_MISMATCH: "
            f"{source_file.name} returned timezone={payload.get('timezone')!r}, "
            f"expected {EXPECTED_TIMEZONE!r}"
        )

    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        raise RuntimeError(f"WEATHER_SCHEMA_MISMATCH: no hourly object in {source_file}")

    actual_keys = list(hourly.keys())
    if actual_keys != HOURLY_KEYS:
        raise RuntimeError(
            "WEATHER_SCHEMA_MISMATCH: expected hourly keys "
            f"{HOURLY_KEYS}, found {actual_keys}"
        )

    lengths = {key: len(hourly[key]) for key in HOURLY_KEYS if isinstance(hourly.get(key), list)}
    if len(lengths) != len(HOURLY_KEYS):
        raise RuntimeError(
            f"WEATHER_SCHEMA_MISMATCH: one or more hourly values are not arrays in {source_file}"
        )

    if len(set(lengths.values())) != 1:
        raise RuntimeError(
            f"WEATHER_SCHEMA_MISMATCH: unequal hourly array lengths in {source_file}: {lengths}"
        )

    return hourly


def document_gap_rows(rows: list[dict]) -> None:
    GAP_REPORT.parent.mkdir(parents=True, exist_ok=True)

    columns = [
        "processing_month",
        "gap_type",
        "weather_timestamp",
        "description",
    ]

    if rows:
        pd.DataFrame(rows, columns=columns).to_csv(GAP_REPORT, index=False)
    else:
        pd.DataFrame(columns=columns).to_csv(GAP_REPORT, index=False)


def weather_condition(code) -> str:
    if pd.isna(code):
        return "Unmapped"
    try:
        return WEATHER_CODE_MAP.get(int(code), "Unmapped")
    except (TypeError, ValueError):
        return "Unmapped"


def prepare_month(month: int, run_id: str, processed_at: datetime):
    source_file, payload = load_month_payload(month)
    hourly = validate_payload_structure(payload, source_file)

    raw_rows = len(hourly["time"])
    df = pd.DataFrame({key: hourly[key] for key in HOURLY_KEYS})

    timestamps = pd.to_datetime(df["time"], errors="coerce")
    expected = expected_month_grid(month)

    invalid_timestamp_count = int(timestamps.isna().sum())
    if invalid_timestamp_count:
        raise RuntimeError(
            f"DQ_WEATHER_TIMESTAMP_FAILURE: {invalid_timestamp_count} "
            f"missing/unparseable timestamps in 2025-{month:02d}"
        )

    duplicate_count = int(timestamps.duplicated(keep=False).sum())
    if duplicate_count:
        raise RuntimeError(
            f"DQ_WEATHER_002: {duplicate_count} rows participate in duplicate "
            f"weather timestamps in 2025-{month:02d}"
        )

    actual_set = set(timestamps.tolist())
    expected_set = set(expected.tolist())

    missing_hours = sorted(expected_set - actual_set)
    unexpected_hours = sorted(actual_set - expected_set)

    gap_rows = [
        {
            "processing_month": f"2025-{month:02d}",
            "gap_type": "MISSING_EXPECTED_HOUR",
            "weather_timestamp": ts.isoformat(sep=" "),
            "description": "Expected 2025 hourly weather timestamp is absent. No value was imputed.",
        }
        for ts in missing_hours
    ]

    if gap_rows:
        document_gap_rows(gap_rows)

    if missing_hours:
        raise RuntimeError(
            f"DQ_WEATHER_001: {len(missing_hours)} expected weather hours are missing "
            f"in 2025-{month:02d}. Gap report: {GAP_REPORT}"
        )

    if unexpected_hours:
        raise RuntimeError(
            f"DQ_WEATHER_004: {len(unexpected_hours)} unexpected weather timestamps "
            f"in 2025-{month:02d}"
        )

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

    numeric = {}
    for col in numeric_columns:
        numeric[col] = pd.to_numeric(df[col], errors="coerce")
        null_count = int(numeric[col].isna().sum())
        if null_count:
            raise RuntimeError(
                f"DQ_WEATHER_003: {null_count} null/unparseable values in {col} "
                f"for 2025-{month:02d}"
            )

    humidity_invalid = ~numeric["relative_humidity_2m"].between(0, 100)
    precipitation_invalid = numeric["precipitation"] < 0
    rain_invalid = numeric["rain"] < 0
    snowfall_invalid = numeric["snowfall"] < 0
    wind_invalid = numeric["wind_speed_10m"] < 0
    gust_invalid = numeric["wind_gusts_10m"] < 0

    invalid_measurement_mask = (
        humidity_invalid
        | precipitation_invalid
        | rain_invalid
        | snowfall_invalid
        | wind_invalid
        | gust_invalid
    )

    invalid_measurement_count = int(invalid_measurement_mask.sum())
    if invalid_measurement_count:
        raise RuntimeError(
            f"DQ_WEATHER_003: {invalid_measurement_count} physically invalid "
            f"weather rows in 2025-{month:02d}"
        )

    mapped_conditions = numeric["weather_code"].map(weather_condition)
    unmapped_code_count = int((mapped_conditions == "Unmapped").sum())
    if unmapped_code_count:
        unmapped = sorted(
            set(
                numeric["weather_code"]
                .loc[mapped_conditions == "Unmapped"]
                .astype(int)
                .tolist()
            )
        )
        raise RuntimeError(
            f"WEATHER_CODE_MAPPING_FAILURE: unmapped WMO codes {unmapped} "
            f"in 2025-{month:02d}"
        )

    source_lat = pd.to_numeric(
        pd.Series([payload.get("latitude")]), errors="coerce"
    ).iloc[0]
    source_lon = pd.to_numeric(
        pd.Series([payload.get("longitude")]), errors="coerce"
    ).iloc[0]
    elevation = pd.to_numeric(
        pd.Series([payload.get("elevation")]), errors="coerce"
    ).iloc[0]

    output = pd.DataFrame(
        {
            "weather_timestamp": timestamps,
            "weather_date": timestamps.dt.date,
            "weather_hour": timestamps.dt.hour.astype("int32"),
            "weather_timezone": EXPECTED_TIMEZONE,
            "temperature_c": numeric["temperature_2m"].astype("float64"),
            "relative_humidity_pct": numeric["relative_humidity_2m"].astype("float64"),
            "apparent_temperature_c": numeric["apparent_temperature"].astype("float64"),
            "precipitation_mm": numeric["precipitation"].astype("float64"),
            "rain_mm": numeric["rain"].astype("float64"),
            "snowfall_cm": numeric["snowfall"].astype("float64"),
            "weather_code": numeric["weather_code"].astype("int32"),
            "weather_condition": mapped_conditions,
            "wind_speed_kmh": numeric["wind_speed_10m"].astype("float64"),
            "wind_gust_kmh": numeric["wind_gusts_10m"].astype("float64"),
            "is_weather_gap": False,
            "source_latitude": None if pd.isna(source_lat) else float(source_lat),
            "source_longitude": None if pd.isna(source_lon) else float(source_lon),
            "source_elevation_m": None if pd.isna(elevation) else float(elevation),
            "_source": "open_meteo_weather",
            "_source_file": source_file.resolve().as_uri(),
            "_run_id": run_id,
            "_processed_at": processed_at,
            "_processing_year": 2025,
            "_processing_month": month,
        }
    )

    table = pa.Table.from_pandas(
        output,
        schema=SILVER_SCHEMA,
        preserve_index=False,
        safe=False,
    )

    return {
        "source_file": source_file,
        "table": table,
        "raw_rows": raw_rows,
        "silver_rows": table.num_rows,
        "missing_hours": len(missing_hours),
        "duplicate_timestamp_rows": duplicate_count,
        "unexpected_timestamps": len(unexpected_hours),
        "invalid_measurement_rows": invalid_measurement_count,
        "unmapped_weather_code_rows": unmapped_code_count,
    }


def update_reconciliation_report(rows: list[dict]) -> None:
    RECONCILIATION_REPORT.parent.mkdir(parents=True, exist_ok=True)

    new_df = pd.DataFrame(rows)

    if RECONCILIATION_REPORT.exists():
        existing = pd.read_csv(
            RECONCILIATION_REPORT,
            dtype={"processing_month": str},
        )
        incoming_months = set(new_df["processing_month"].astype(str))
        existing = existing[
            ~existing["processing_month"].astype(str).isin(incoming_months)
        ]
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df

    combined = combined.sort_values("processing_month").reset_index(drop=True)
    combined.to_csv(RECONCILIATION_REPORT, index=False)


def process_month(month: int) -> dict:
    mt = f"{month:02d}"
    output_dir = SILVER_WEATHER_ROOT / f"month={mt}"
    run_id = str(uuid.uuid4())
    processed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    started_at = datetime.now(timezone.utc)

    print("\n" + "=" * 78)
    print(f"PHASE 11 - WEATHER SILVER - 2025-{mt}")
    print("=" * 78)
    print(f"Run ID: {run_id}")
    print(f"Output: {output_dir}")

    try:
        prepared = prepare_month(month, run_id, processed_at)

        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = (
            output_dir
            / f"part-00000-{run_id.replace('-', '')}.parquet"
        )

        pq.write_table(
            prepared["table"],
            output_file,
            compression="snappy",
        )

        verified_rows = pq.ParquetFile(output_file).metadata.num_rows

        if prepared["raw_rows"] != prepared["silver_rows"]:
            raise RuntimeError(
                "ROW_RECONCILIATION_FAILURE: "
                f"Raw={prepared['raw_rows']:,}, Silver={prepared['silver_rows']:,}"
            )

        if verified_rows != prepared["silver_rows"]:
            raise RuntimeError(
                "PARQUET_RECONCILIATION_FAILURE: "
                f"expected {prepared['silver_rows']:,}, verified {verified_rows:,}"
            )

        result = {
            "run_id": run_id,
            "processing_month": f"2025-{mt}",
            "raw_rows": prepared["raw_rows"],
            "silver_rows": prepared["silver_rows"],
            "missing_hours": prepared["missing_hours"],
            "duplicate_timestamp_rows": prepared["duplicate_timestamp_rows"],
            "unexpected_timestamps": prepared["unexpected_timestamps"],
            "invalid_measurement_rows": prepared["invalid_measurement_rows"],
            "unmapped_weather_code_rows": prepared["unmapped_weather_code_rows"],
            "status": "SUCCESS",
        }

        write_run_log(
            {
                "phase": 11,
                "pipeline": "weather_silver",
                **result,
                "started_at": started_at.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "output_file_count": 1,
            }
        )

        print(f"Raw rows: {prepared['raw_rows']:,}")
        print(f"Silver rows: {prepared['silver_rows']:,}")
        print(f"Missing expected hours: {prepared['missing_hours']}")
        print(f"Duplicate timestamps: {prepared['duplicate_timestamp_rows']}")
        print(f"Unexpected timestamps: {prepared['unexpected_timestamps']}")
        print(f"Invalid measurements: {prepared['invalid_measurement_rows']}")
        print(f"Unmapped weather codes: {prepared['unmapped_weather_code_rows']}")
        print(f"Verified Silver rows: {verified_rows:,}")
        print("Reconciliation: SUCCESS")
        print(f"2025-{mt}: SILVER SUCCESS")

        return result

    except Exception as exc:
        write_run_log(
            {
                "phase": 11,
                "pipeline": "weather_silver",
                "run_id": run_id,
                "processing_month": f"2025-{mt}",
                "started_at": started_at.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "status": "FAILED",
                "error_message": str(exc),
            }
        )
        print(f"2025-{mt}: SILVER FAILED")
        print(f"Error: {exc}")
        raise


def parse_args():
    parser = argparse.ArgumentParser(
        description="Prepare hourly Open-Meteo Weather Silver data for Phase 11."
    )
    parser.add_argument(
        "--months",
        nargs="+",
        type=int,
        default=list(range(1, 13)),
        help="Months to process, e.g. --months 1 or --months 2 3 4",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if any(month < 1 or month > 12 for month in args.months):
        raise ValueError(f"Invalid months: {args.months}")

    profile = load_profile_contract()

    print("=" * 78)
    print("PHASE 11 - WEATHER DATA PREPARATION")
    print("=" * 78)
    print(f"Phase 6 Raw rows: {profile['row_count']:,}")
    print(f"Target grain: hourly")
    print(f"Timestamp semantics: NYC local wall-clock ({EXPECTED_TIMEZONE})")
    print("Gap policy: DOCUMENT + FAIL; NEVER IMPUTE")
    print("Weather condition: WMO weather_code mapping")

    # If the current run starts from a source already known to have zero gaps,
    # keep an explicit empty gap artifact. If any later monthly run detects a
    # gap, prepare_month replaces it with the actual missing timestamps.
    if not GAP_REPORT.exists():
        document_gap_rows([])

    results = [process_month(month) for month in args.months]
    update_reconciliation_report(results)

    total_raw = sum(row["raw_rows"] for row in results)
    total_silver = sum(row["silver_rows"] for row in results)
    total_missing = sum(row["missing_hours"] for row in results)
    total_duplicates = sum(row["duplicate_timestamp_rows"] for row in results)
    total_unexpected = sum(row["unexpected_timestamps"] for row in results)
    total_invalid = sum(row["invalid_measurement_rows"] for row in results)

    print("\n" + "=" * 78)
    print("PHASE 11 RUN SUMMARY")
    print("=" * 78)
    print("Months processed:", ", ".join(f"{m:02d}" for m in args.months))
    print(f"Raw rows: {total_raw:,}")
    print(f"Silver rows: {total_silver:,}")
    print(f"Missing hours: {total_missing}")
    print(f"Duplicate timestamps: {total_duplicates}")
    print(f"Unexpected timestamps: {total_unexpected}")
    print(f"Invalid measurements: {total_invalid}")
    print(f"Reconciliation report: {RECONCILIATION_REPORT}")
    print(f"Gap report: {GAP_REPORT}")

    if sorted(set(args.months)) == list(range(1, 13)):
        if total_raw != EXPECTED_FULL_YEAR_ROWS:
            raise RuntimeError(
                f"FULL_YEAR_RAW_FAILURE: expected {EXPECTED_FULL_YEAR_ROWS:,}, "
                f"found {total_raw:,}"
            )
        if total_silver != EXPECTED_FULL_YEAR_ROWS:
            raise RuntimeError(
                f"FULL_YEAR_SILVER_FAILURE: expected {EXPECTED_FULL_YEAR_ROWS:,}, "
                f"found {total_silver:,}"
            )
        if any([total_missing, total_duplicates, total_unexpected, total_invalid]):
            raise RuntimeError(
                "FULL_YEAR_WEATHER_QUALITY_FAILURE: one or more gap/duplicate/"
                "timestamp/measurement controls failed"
            )
        print("Full-year hourly grid reconciliation: PASS")

    print("\nPHASE 11 WEATHER SILVER BUILD: SUCCESS")


if __name__ == "__main__":
    main()
