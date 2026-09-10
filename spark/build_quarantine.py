import argparse
import csv
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F


PROJECT_ROOT = Path(__file__).resolve().parents[1]

TAXI_BRONZE_ROOT = PROJECT_ROOT / "data" / "bronze" / "taxi" / "year=2025"
RAW_311_ROOT = PROJECT_ROOT / "data" / "raw" / "complaints_311" / "year=2025"
RAW_WEATHER_ROOT = PROJECT_ROOT / "data" / "raw" / "weather" / "year=2025"
ZONE_LOOKUP = PROJECT_ROOT / "data" / "raw" / "taxi_zones" / "taxi_zone_lookup.csv"

QUARANTINE_ROOT = PROJECT_ROOT / "data" / "quarantine"
REASON_CODES_FILE = PROJECT_ROOT / "data_quality" / "reason_codes.csv"
REPORT_DIR = PROJECT_ROOT / "reports" / "quarantine"

TAXI_SOURCE_COLUMNS = [
    "VendorID",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "passenger_count",
    "trip_distance",
    "RatecodeID",
    "store_and_fwd_flag",
    "PULocationID",
    "DOLocationID",
    "payment_type",
    "fare_amount",
    "extra",
    "mta_tax",
    "tip_amount",
    "tolls_amount",
    "improvement_surcharge",
    "total_amount",
    "congestion_surcharge",
    "Airport_fee",
    "cbd_congestion_fee",
]

REQUIRED_311_COLUMNS = {
    "unique_key",
    "created_date",
    "closed_date",
    "latitude",
    "longitude",
}

EXPECTED_WEATHER_COLUMNS = [
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

EXPECTED_ZONE_COLUMNS = [
    "LocationID",
    "Borough",
    "Zone",
    "service_zone",
]

QUARANTINE_SCHEMA = pa.schema(
    [
        ("source", pa.string()),
        ("reason_code", pa.string()),
        ("reason_description", pa.string()),
        ("run_id", pa.string()),
        ("rejected_at", pa.string()),
        ("original_record", pa.string()),
        ("rule_id", pa.string()),
        ("severity", pa.string()),
    ]
)


def as_uri(path: Path) -> str:
    return "file:///" + path.resolve().as_posix()


def create_spark():
    return (
        SparkSession.builder
        .appName("NYC-Urban-Intelligence-Quarantine")
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "12")
        .config("spark.driver.memory", "4g")
        .getOrCreate()
    )


def load_reason_codes():
    with REASON_CODES_FILE.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    by_rule = {row["rule_id"]: row for row in rows}

    if len(by_rule) != len(rows):
        raise RuntimeError("reason_codes.csv contains duplicate rule_id values")

    return by_rule


def reason_struct(reason_codes, rule_id):
    meta = reason_codes[rule_id]

    return F.struct(
        F.lit(rule_id).alias("rule_id"),
        F.lit(meta["reason_code"]).alias("reason_code"),
        F.lit(meta["reason_description"]).alias("reason_description"),
        F.lit(meta["severity"]).alias("severity"),
    )


def write_rows_to_parquet(rows, output_file: Path, batch_size=5000):
    output_file.parent.mkdir(parents=True, exist_ok=True)

    writer = pq.ParquetWriter(
        output_file,
        QUARANTINE_SCHEMA,
        compression="snappy",
    )

    count = 0
    buffer = []

    try:
        for row in rows:
            if hasattr(row, "asDict"):
                row = row.asDict(recursive=True)

            buffer.append(
                {
                    field.name: (
                        None
                        if row.get(field.name) is None
                        else str(row.get(field.name))
                    )
                    for field in QUARANTINE_SCHEMA
                }
            )

            if len(buffer) >= batch_size:
                table = pa.Table.from_pylist(
                    buffer,
                    schema=QUARANTINE_SCHEMA,
                )
                writer.write_table(table)
                count += len(buffer)
                buffer.clear()

        if buffer:
            table = pa.Table.from_pylist(
                buffer,
                schema=QUARANTINE_SCHEMA,
            )
            writer.write_table(table)
            count += len(buffer)

        if count == 0:
            writer.write_table(
                pa.Table.from_pylist(
                    [],
                    schema=QUARANTINE_SCHEMA,
                )
            )
    finally:
        writer.close()

    return count


def spark_rejection_rows(
    df,
    source,
    run_id,
    rejected_at,
    rules,
    reason_codes,
    original_columns=None,
):
    if original_columns is None:
        original_columns = df.columns

    original_json = F.to_json(
        F.struct(
            *[F.col(column) for column in original_columns]
        )
    )

    reason_array = F.array(
        *[
            F.when(
                condition,
                reason_struct(reason_codes, rule_id),
            )
            for rule_id, condition in rules
        ]
    )

    return (
        df
        .withColumn("_original_record", original_json)
        .withColumn("_reasons_raw", reason_array)
        .withColumn(
            "_reasons",
            F.expr(
                "filter(_reasons_raw, x -> x is not null)"
            ),
        )
        .withColumn("_reason", F.explode("_reasons"))
        .select(
            F.lit(source).alias("source"),
            F.col("_reason.reason_code").alias("reason_code"),
            F.col("_reason.reason_description").alias(
                "reason_description"
            ),
            F.lit(run_id).alias("run_id"),
            F.lit(rejected_at).alias("rejected_at"),
            F.col("_original_record").alias("original_record"),
            F.col("_reason.rule_id").alias("rule_id"),
            F.col("_reason.severity").alias("severity"),
        )
    )


def taxi_duplicate_rows(
    df,
    reason_codes,
    run_id,
    rejected_at,
):
    missing = set(TAXI_SOURCE_COLUMNS) - set(df.columns)

    if missing:
        raise RuntimeError(
            "TAXI_SCHEMA_MISMATCH: missing columns "
            + ", ".join(sorted(missing))
        )

    source_json = F.to_json(
        F.struct(
            *[F.col(column) for column in TAXI_SOURCE_COLUMNS]
        )
    )

    with_hash = (
        df
        .withColumn("_source_record_json", source_json)
        .withColumn(
            "_record_hash",
            F.sha2(F.col("_source_record_json"), 256),
        )
    )

    duplicate_hashes = (
        with_hash
        .groupBy("_record_hash")
        .count()
        .where(F.col("count") > 1)
        .select("_record_hash")
    )

    duplicate_candidates = with_hash.join(
        duplicate_hashes,
        on="_record_hash",
        how="inner",
    )

    order_columns = []

    if "_source_file" in duplicate_candidates.columns:
        order_columns.append(F.col("_source_file"))

    order_columns.extend(
        [
            F.col("tpep_pickup_datetime"),
            F.col("tpep_dropoff_datetime"),
        ]
    )

    window = Window.partitionBy("_record_hash").orderBy(
        *order_columns
    )

    meta = reason_codes["DQ_TAXI_006"]

    return (
        duplicate_candidates
        .withColumn("_duplicate_number", F.row_number().over(window))
        .where(F.col("_duplicate_number") > 1)
        .select(
            F.lit("yellow_taxi").alias("source"),
            F.lit(meta["reason_code"]).alias("reason_code"),
            F.lit(meta["reason_description"]).alias(
                "reason_description"
            ),
            F.lit(run_id).alias("run_id"),
            F.lit(rejected_at).alias("rejected_at"),
            F.to_json(
                F.struct(
                    *[
                        F.col(column)
                        for column in df.columns
                    ]
                )
            ).alias("original_record"),
            F.lit("DQ_TAXI_006").alias("rule_id"),
            F.lit(meta["severity"]).alias("severity"),
        )
    )


def quarantine_taxi(
    spark,
    reason_codes,
    run_id,
    rejected_at,
    run_root,
):
    files = sorted(TAXI_BRONZE_ROOT.rglob("*.parquet"))

    if not files:
        raise FileNotFoundError(
            f"No Taxi Bronze parquet files found under {TAXI_BRONZE_ROOT}"
        )

    print()
    print("TAXI QUARANTINE")
    print("-" * 78)
    print(f"Bronze parquet files: {len(files)}")

    df = spark.read.parquet(
        *[as_uri(path) for path in files]
    )

    missing = set(TAXI_SOURCE_COLUMNS) - set(df.columns)

    if missing:
        raise RuntimeError(
            "TAXI_SCHEMA_MISMATCH: missing required columns "
            + ", ".join(sorted(missing))
        )

    rules = [
        (
            "DQ_TAXI_001",
            F.col("tpep_pickup_datetime").isNull(),
        ),
        (
            "DQ_TAXI_002",
            F.col("tpep_dropoff_datetime").isNull(),
        ),
        (
            "DQ_TAXI_003",
            F.col("tpep_dropoff_datetime")
            < F.col("tpep_pickup_datetime"),
        ),
        (
            "DQ_TAXI_004",
            F.col("tpep_pickup_datetime").isNotNull()
            & (
                (F.col("tpep_pickup_datetime") < F.lit("2025-01-01"))
                | (
                    F.col("tpep_pickup_datetime")
                    >= F.lit("2026-01-01")
                )
            ),
        ),
        (
            "DQ_TAXI_005",
            F.col("PULocationID").isNull()
            | F.col("DOLocationID").isNull(),
        ),
        (
            "DQ_TAXI_007",
            F.col("trip_distance") < 0,
        ),
    ]

    structural = spark_rejection_rows(
        df,
        "yellow_taxi",
        run_id,
        rejected_at,
        rules,
        reason_codes,
    )

    duplicate = taxi_duplicate_rows(
        df,
        reason_codes,
        run_id,
        rejected_at,
    )

    combined = structural.unionByName(duplicate)

    output = (
        run_root
        / "source=yellow_taxi"
        / "part-00000.parquet"
    )

    count = write_rows_to_parquet(
        combined.toLocalIterator(),
        output,
    )

    print(f"Taxi quarantine events written: {count:,}")
    print(f"Output: {output}")

    return count


def quarantine_311(
    spark,
    reason_codes,
    run_id,
    rejected_at,
    run_root,
):
    files = sorted(RAW_311_ROOT.rglob("*.json"))

    if not files:
        raise FileNotFoundError(
            f"No 311 JSON files found under {RAW_311_ROOT}"
        )

    print()
    print("311 QUARANTINE")
    print("-" * 78)
    print(f"Raw JSON pages: {len(files)}")

    df = (
        spark.read
        .option("multiLine", "true")
        .json([as_uri(path) for path in files])
    )

    missing = REQUIRED_311_COLUMNS - set(df.columns)

    if missing:
        raise RuntimeError(
            "311_SCHEMA_MISMATCH: missing required columns "
            + ", ".join(sorted(missing))
        )

    created_ts = F.try_to_timestamp(F.col("created_date"))
    closed_ts = F.try_to_timestamp(F.col("closed_date"))
    latitude = F.expr("try_cast(latitude as double)")
    longitude = F.expr("try_cast(longitude as double)")

    typed = (
        df
        .withColumn("_created_ts", created_ts)
        .withColumn("_closed_ts", closed_ts)
        .withColumn("_latitude_num", latitude)
        .withColumn("_longitude_num", longitude)
    )

    rules = [
        (
            "DQ_311_001",
            F.col("_created_ts").isNull(),
        ),
        (
            "DQ_311_002",
            F.col("_created_ts").isNotNull()
            & (
                (F.col("_created_ts") < F.lit("2025-01-01"))
                | (F.col("_created_ts") >= F.lit("2026-01-01"))
            ),
        ),
        (
            "DQ_311_003",
            F.col("_created_ts").isNotNull()
            & F.col("_closed_ts").isNotNull()
            & (F.col("_closed_ts") < F.col("_created_ts")),
        ),
        (
            "DQ_311_005",
            F.col("latitude").isNull()
            | F.col("longitude").isNull(),
        ),
        (
            "DQ_311_006",
            (
                F.col("latitude").isNotNull()
                & (
                    F.col("_latitude_num").isNull()
                    | (F.col("_latitude_num") < -90)
                    | (F.col("_latitude_num") > 90)
                )
            )
            | (
                F.col("longitude").isNotNull()
                & (
                    F.col("_longitude_num").isNull()
                    | (F.col("_longitude_num") < -180)
                    | (F.col("_longitude_num") > 180)
                )
            ),
        ),
    ]

    base_columns = df.columns

    structural_input = typed.select(
        *base_columns,
        "_created_ts",
        "_closed_ts",
        "_latitude_num",
        "_longitude_num",
    )

    structural = spark_rejection_rows(
        structural_input,
        "nyc_311",
        run_id,
        rejected_at,
        rules,
        reason_codes,
        original_columns=base_columns,
    )

    meta = reason_codes["DQ_311_004"]

    duplicate_window = Window.partitionBy("unique_key").orderBy(
        F.col("created_date"),
        F.col("closed_date"),
    )

    duplicates = (
        df
        .where(F.col("unique_key").isNotNull())
        .withColumn(
            "_duplicate_number",
            F.row_number().over(duplicate_window),
        )
        .where(F.col("_duplicate_number") > 1)
        .select(
            F.lit("nyc_311").alias("source"),
            F.lit(meta["reason_code"]).alias("reason_code"),
            F.lit(meta["reason_description"]).alias(
                "reason_description"
            ),
            F.lit(run_id).alias("run_id"),
            F.lit(rejected_at).alias("rejected_at"),
            F.to_json(
                F.struct(
                    *[
                        F.col(column)
                        for column in df.columns
                    ]
                )
            ).alias("original_record"),
            F.lit("DQ_311_004").alias("rule_id"),
            F.lit(meta["severity"]).alias("severity"),
        )
    )

    combined = structural.unionByName(duplicates)

    output = (
        run_root
        / "source=nyc_311"
        / "part-00000.parquet"
    )

    count = write_rows_to_parquet(
        combined.toLocalIterator(),
        output,
    )

    print(f"311 quarantine events written: {count:,}")
    print(f"Output: {output}")

    return count


def weather_original_record(row):
    record = {}

    for key, value in row.items():
        if key == "_source_file":
            record[key] = value
        elif pd.isna(value):
            record[key] = None
        else:
            record[key] = value.item() if hasattr(value, "item") else value

    return json.dumps(
        record,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )


def quarantine_weather(
    reason_codes,
    run_id,
    rejected_at,
    run_root,
):
    files = sorted(RAW_WEATHER_ROOT.rglob("*.json"))

    if not files:
        raise FileNotFoundError(
            f"No Weather JSON files found under {RAW_WEATHER_ROOT}"
        )

    print()
    print("WEATHER QUARANTINE / CONTROL CHECK")
    print("-" * 78)
    print(f"Raw JSON files: {len(files)}")

    frames = []

    for path in files:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        hourly = payload.get("hourly", {})

        if set(hourly.keys()) != set(EXPECTED_WEATHER_COLUMNS):
            raise RuntimeError(
                f"WEATHER_SCHEMA_MISMATCH: {path.name}"
            )

        lengths = {
            len(value)
            for value in hourly.values()
            if isinstance(value, list)
        }

        if len(lengths) != 1:
            raise RuntimeError(
                f"WEATHER_SCHEMA_MISMATCH: unequal arrays in {path.name}"
            )

        frame = pd.DataFrame(hourly)
        frame["_source_file"] = str(path.relative_to(PROJECT_ROOT))
        frames.append(frame)

    df = pd.concat(frames, ignore_index=True)
    timestamps = pd.to_datetime(df["time"], errors="coerce")

    expected = pd.date_range(
        "2025-01-01 00:00:00",
        "2025-12-31 23:00:00",
        freq="h",
    )

    actual_valid = pd.DatetimeIndex(
        timestamps.dropna().unique()
    )

    missing_hours = expected.difference(actual_valid)

    if len(missing_hours) > 0:
        raise RuntimeError(
            f"WEATHER_GAP: {len(missing_hours)} expected hours missing"
        )

    duplicate_mask = timestamps.duplicated(keep="first")

    humidity = pd.to_numeric(
        df["relative_humidity_2m"],
        errors="coerce",
    )
    precipitation = pd.to_numeric(
        df["precipitation"],
        errors="coerce",
    )
    rain = pd.to_numeric(df["rain"], errors="coerce")
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

    invalid_measurement = (
        humidity.isna()
        | (humidity < 0)
        | (humidity > 100)
        | precipitation.isna()
        | (precipitation < 0)
        | rain.isna()
        | (rain < 0)
        | snowfall.isna()
        | (snowfall < 0)
        | wind.isna()
        | (wind < 0)
        | gust.isna()
        | (gust < 0)
    )

    invalid_date = (
        timestamps.isna()
        | (timestamps < pd.Timestamp("2025-01-01 00:00:00"))
        | (timestamps > pd.Timestamp("2025-12-31 23:00:00"))
    )

    output_rows = []

    checks = [
        (
            duplicate_mask,
            "DQ_WEATHER_002",
        ),
        (
            invalid_measurement,
            "DQ_WEATHER_003",
        ),
        (
            invalid_date,
            "DQ_WEATHER_004",
        ),
    ]

    for mask, rule_id in checks:
        meta = reason_codes[rule_id]

        for _, row in df.loc[mask].iterrows():
            output_rows.append(
                {
                    "source": "open_meteo_weather",
                    "reason_code": meta["reason_code"],
                    "reason_description": meta["reason_description"],
                    "run_id": run_id,
                    "rejected_at": rejected_at,
                    "original_record": weather_original_record(
                        row.to_dict()
                    ),
                    "rule_id": rule_id,
                    "severity": meta["severity"],
                }
            )

    output = (
        run_root
        / "source=open_meteo_weather"
        / "part-00000.parquet"
    )

    count = write_rows_to_parquet(
        output_rows,
        output,
    )

    print(f"Weather quarantine events written: {count:,}")
    print(f"Output: {output}")

    return count


def validate_taxi_zones():
    print()
    print("TAXI ZONE CONTROL CHECK")
    print("-" * 78)

    if not ZONE_LOOKUP.exists():
        raise FileNotFoundError(
            f"Taxi Zone lookup not found: {ZONE_LOOKUP}"
        )

    df = pd.read_csv(
        ZONE_LOOKUP,
        keep_default_na=False,
    )

    if list(df.columns) != EXPECTED_ZONE_COLUMNS:
        raise RuntimeError(
            "ZONE_SCHEMA_MISMATCH: unexpected Taxi Zone columns"
        )

    if (df["LocationID"].astype(str).str.strip() == "").any():
        raise RuntimeError("MISSING_ZONE_ID")

    if df["LocationID"].duplicated().any():
        raise RuntimeError("DUPLICATE_ZONE_ID")

    if (df["Zone"].astype(str).str.strip() == "").any():
        raise RuntimeError("MISSING_ZONE_NAME")

    print(f"Rows: {len(df):,}")
    print("Schema: PASS")
    print("LocationID uniqueness: PASS")
    print("Zone name completeness: PASS")


def write_summary(
    run_id,
    started_at,
    finished_at,
    counts,
    status,
    error=None,
):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    summary = {
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "status": status,
        "quarantine_event_counts": counts,
        "total_quarantine_events": sum(counts.values()),
        "error": error,
    }

    path = REPORT_DIR / "quarantine_latest_summary.json"

    with path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return path


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--sources",
        nargs="+",
        choices=["taxi", "311", "weather", "zones"],
        default=["taxi", "311", "weather", "zones"],
        help="Sources to validate/quarantine.",
    )

    args = parser.parse_args()

    reason_codes = load_reason_codes()

    run_id = str(uuid.uuid4())
    rejected_at = datetime.now(timezone.utc).isoformat()
    started_at = rejected_at

    run_root = QUARANTINE_ROOT / f"run_id={run_id}"
    run_root.mkdir(parents=True, exist_ok=True)

    counts = {}
    spark = None

    print("=" * 78)
    print("PHASE 8 - QUARANTINE INVALID DATA")
    print("=" * 78)
    print(f"Run ID: {run_id}")
    print(f"Run output: {run_root}")
    print(f"Sources: {', '.join(args.sources)}")

    try:
        if "taxi" in args.sources or "311" in args.sources:
            spark = create_spark()
            spark.sparkContext.setLogLevel("WARN")

        if "taxi" in args.sources:
            counts["yellow_taxi"] = quarantine_taxi(
                spark,
                reason_codes,
                run_id,
                rejected_at,
                run_root,
            )

        if "311" in args.sources:
            counts["nyc_311"] = quarantine_311(
                spark,
                reason_codes,
                run_id,
                rejected_at,
                run_root,
            )

        if "weather" in args.sources:
            counts["open_meteo_weather"] = quarantine_weather(
                reason_codes,
                run_id,
                rejected_at,
                run_root,
            )

        if "zones" in args.sources:
            validate_taxi_zones()
            counts["tlc_taxi_zones"] = 0

        finished_at = datetime.now(timezone.utc).isoformat()

        summary_path = write_summary(
            run_id,
            started_at,
            finished_at,
            counts,
            "SUCCESS",
        )

        print()
        print("=" * 78)
        print("QUARANTINE BUILD SUCCESS")
        print("=" * 78)

        for source, count in counts.items():
            print(f"{source}: {count:,}")

        print(f"Total quarantine events: {sum(counts.values()):,}")
        print(f"Summary: {summary_path}")

    except Exception as exc:
        finished_at = datetime.now(timezone.utc).isoformat()

        write_summary(
            run_id,
            started_at,
            finished_at,
            counts,
            "FAILED",
            str(exc),
        )

        print()
        print("QUARANTINE BUILD FAILED")
        print(f"Error: {exc}")
        raise

    finally:
        if spark is not None:
            spark.stop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(1)
