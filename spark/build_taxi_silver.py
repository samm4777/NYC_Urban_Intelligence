#!/usr/bin/env python
"""
Phase 9 - Yellow Taxi Silver preparation.

Design:
- Read existing 2025 Bronze Taxi Parquet files with Spark using explicit file URIs.
- Reproduce Phase 8 reject logic without modifying Bronze/Raw/Quarantine.
- Keep candidate anomalies and expose boolean flags.
- Enrich pickup/drop-off LocationIDs with TLC Taxi Zone labels.
- Derive date/hour/duration/payment_method/revenue.
- Persist Silver by year/month using the same Windows-safe Spark->PyArrow pattern
  proven in Phase 5.
- Reconcile Bronze rows = Silver rows + rejected rows.

Revenue definition:
    revenue = total_amount
This is gross reported passenger amount charged from the TLC source field.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pyspark import StorageLevel
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType,
    ByteType,
    DateType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    LongType,
    ShortType,
    StringType,
    TimestampNTZType,
    TimestampType,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

BRONZE_ROOT = PROJECT_ROOT / "data" / "bronze" / "taxi" / "year=2025"
SILVER_ROOT = PROJECT_ROOT / "data" / "silver" / "taxi" / "year=2025"
ZONE_LOOKUP = PROJECT_ROOT / "data" / "raw" / "taxi_zones" / "taxi_zone_lookup.csv"

RUN_LOG = PROJECT_ROOT / "logs" / "pipeline_runs.jsonl"
RECON_REPORT = (
    PROJECT_ROOT / "reports" / "reconciliation" / "taxi_silver_reconciliation.csv"
)

EXPECTED_FULL_YEAR_BRONZE_ROWS = 48_722_602
EXPECTED_FULL_YEAR_REJECTED_ROWS = 2_265
EXPECTED_FULL_YEAR_SILVER_ROWS = 48_720_337

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

REQUIRED_BRONZE_COLUMNS = TAXI_SOURCE_COLUMNS + [
    "_source",
    "_source_file",
    "_ingested_at",
    "_run_id",
    "_processing_year",
    "_processing_month",
]

PAYMENT_METHODS = {
    0: "Flex Fare",
    1: "Credit Card",
    2: "Cash",
    3: "No Charge",
    4: "Dispute",
    5: "Unknown",
    6: "Voided Trip",
}


def spark_uri(path: Path) -> str:
    return "file:///" + path.resolve().as_posix()


def create_spark() -> SparkSession:
    return (
        SparkSession.builder
        .appName("NYC-Taxi-Silver-Phase9")
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.driver.memory", "4g")
        .getOrCreate()
    )


def append_run_log(metric: dict) -> None:
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RUN_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(metric, default=str) + "\n")


def collect_month_files(month: int) -> list[Path]:
    month_dir = BRONZE_ROOT / f"month={month:02d}"
    files = sorted(month_dir.glob("part-*.parquet"))
    if not files:
        raise FileNotFoundError(f"No Bronze Taxi Parquet files found: {month_dir}")
    return files


def collect_all_files() -> list[Path]:
    files: list[Path] = []
    for month in range(1, 13):
        files.extend(collect_month_files(month))
    return files


def parquet_row_count(files: list[Path]) -> int:
    return sum(pq.ParquetFile(str(p)).metadata.num_rows for p in files)


def read_explicit_parquet_files(spark: SparkSession, files: list[Path]):
    # Explicit file paths avoid Windows directory-listing NativeIO failures.
    return spark.read.parquet(*[spark_uri(p) for p in files])


def validate_bronze_schema(df) -> None:
    missing = sorted(set(REQUIRED_BRONZE_COLUMNS) - set(df.columns))
    if missing:
        raise RuntimeError(
            "TAXI_SCHEMA_MISMATCH: missing Bronze columns: " + ", ".join(missing)
        )


def add_source_record_hash(df):
    source_json = F.to_json(
        F.struct(*[F.col(column) for column in TAXI_SOURCE_COLUMNS])
    )
    return df.withColumn(
        "_record_hash",
        F.sha2(source_json, 256),
    )


def find_global_duplicate_metadata(spark: SparkSession):
    """
    Match Phase 8 duplicate identity:
      sha2(to_json(struct(TAXI_SOURCE_COLUMNS)), 256)

    For each duplicate hash, Phase 8 orders by _source_file, pickup, dropoff and
    rejects row_number > 1. Since rows sharing the same source hash also share
    pickup/dropoff values, the lexicographically first _source_file identifies
    the file containing the global keeper. A per-month row_number then keeps
    exactly one copy in that keeper file and rejects all other copies.
    """
    all_files = collect_all_files()

    print("\n===== GLOBAL EXACT-DUPLICATE PRE-SCAN =====")
    print(f"Bronze Parquet files: {len(all_files)}")

    df = read_explicit_parquet_files(spark, all_files)
    validate_bronze_schema(df)

    hashed = add_source_record_hash(
        df.select(*(TAXI_SOURCE_COLUMNS + ["_source_file"]))
    )

    duplicate_meta_df = (
        hashed
        .groupBy("_record_hash")
        .agg(
            F.count(F.lit(1)).alias("_duplicate_count"),
            F.min("_source_file").alias("_keeper_source_file"),
        )
        .where(F.col("_duplicate_count") > 1)
        .orderBy("_record_hash")
    )

    rows = duplicate_meta_df.collect()

    duplicate_hash_count = len(rows)
    duplicate_rejections_expected = sum(
        int(row["_duplicate_count"]) - 1 for row in rows
    )

    print(f"Duplicate hashes: {duplicate_hash_count:,}")
    print(f"Expected duplicate rows rejected: {duplicate_rejections_expected:,}")

    if not rows:
        schema = (
            "_record_hash string, "
            "_duplicate_count long, "
            "_keeper_source_file string"
        )
        return spark.createDataFrame([], schema=schema), 0

    local_rows = [
        (
            row["_record_hash"],
            int(row["_duplicate_count"]),
            row["_keeper_source_file"],
        )
        for row in rows
    ]

    return (
        spark.createDataFrame(
            local_rows,
            ["_record_hash", "_duplicate_count", "_keeper_source_file"],
        ),
        duplicate_rejections_expected,
    )


def load_zone_dimension(spark: SparkSession):
    if not ZONE_LOOKUP.exists():
        raise FileNotFoundError(f"Taxi Zone lookup not found: {ZONE_LOOKUP}")

    pdf = pd.read_csv(ZONE_LOOKUP)

    expected = ["LocationID", "Borough", "Zone", "service_zone"]
    if list(pdf.columns) != expected:
        raise RuntimeError(
            "ZONE_SCHEMA_MISMATCH: expected columns "
            f"{expected}, found {list(pdf.columns)}"
        )

    if pdf["LocationID"].isna().any():
        raise RuntimeError("ZONE_SCHEMA_MISMATCH: LocationID contains nulls")

    if pdf["LocationID"].duplicated().any():
        raise RuntimeError("ZONE_SCHEMA_MISMATCH: duplicate LocationID values")

    pdf["LocationID"] = pdf["LocationID"].astype("int32")

    return spark.createDataFrame(pdf)


def add_payment_method(df):
    expression = None
    for code, label in PAYMENT_METHODS.items():
        condition = F.col("payment_type") == F.lit(code)
        if expression is None:
            expression = F.when(condition, F.lit(label))
        else:
            expression = expression.when(condition, F.lit(label))

    return df.withColumn(
        "payment_method",
        expression.otherwise(F.lit("Unmapped")),
    )


def add_duplicate_reject_flag(df, duplicate_meta):
    hashed = add_source_record_hash(df)

    joined = hashed.join(
        F.broadcast(duplicate_meta),
        on="_record_hash",
        how="left",
    )

    duplicate_window = Window.partitionBy("_record_hash").orderBy(
        F.col("_source_file"),
        F.col("tpep_pickup_datetime"),
        F.col("tpep_dropoff_datetime"),
    )

    ranked = joined.withColumn(
        "_duplicate_number_in_month",
        F.when(
            F.col("_duplicate_count").isNotNull(),
            F.row_number().over(duplicate_window),
        ),
    )

    # For a duplicate hash:
    # - all rows in source files after the global keeper file are rejected;
    # - inside the keeper source file, only the first ranked row survives.
    reject_duplicate = (
        F.col("_duplicate_count").isNotNull()
        & (
            (F.col("_source_file") > F.col("_keeper_source_file"))
            | (
                (F.col("_source_file") == F.col("_keeper_source_file"))
                & (F.col("_duplicate_number_in_month") > 1)
            )
        )
    )

    return ranked.withColumn(
        "_reject_duplicate",
        F.coalesce(reject_duplicate, F.lit(False)),
    )


def add_rejection_flags(df):
    return (
        df
        .withColumn(
            "_reject_missing_pickup",
            F.col("tpep_pickup_datetime").isNull(),
        )
        .withColumn(
            "_reject_missing_dropoff",
            F.col("tpep_dropoff_datetime").isNull(),
        )
        .withColumn(
            "_reject_invalid_duration",
            F.col("tpep_dropoff_datetime") < F.col("tpep_pickup_datetime"),
        )
        .withColumn(
            "_reject_invalid_pickup_date",
            F.col("tpep_pickup_datetime").isNotNull()
            & (
                (F.col("tpep_pickup_datetime") < F.lit("2025-01-01"))
                | (F.col("tpep_pickup_datetime") >= F.lit("2026-01-01"))
            ),
        )
        .withColumn(
            "_reject_missing_location",
            F.col("PULocationID").isNull() | F.col("DOLocationID").isNull(),
        )
        .withColumn(
            "_reject_negative_distance",
            F.col("trip_distance") < F.lit(0.0),
        )
        .withColumn(
            "_reject_any",
            F.coalesce(F.col("_reject_missing_pickup"), F.lit(False))
            | F.coalesce(F.col("_reject_missing_dropoff"), F.lit(False))
            | F.coalesce(F.col("_reject_invalid_duration"), F.lit(False))
            | F.coalesce(F.col("_reject_invalid_pickup_date"), F.lit(False))
            | F.coalesce(F.col("_reject_missing_location"), F.lit(False))
            | F.coalesce(F.col("_reject_negative_distance"), F.lit(False))
            | F.coalesce(F.col("_reject_duplicate"), F.lit(False)),
        )
    )


def enrich_and_derive(df, zones):
    valid = df.where(~F.col("_reject_any"))

    # Spark 4 reads the TLC Parquet timestamps as TIMESTAMP_NTZ on this
    # Windows environment. TIMESTAMP_NTZ cannot be cast directly to DOUBLE,
    # so calculate elapsed time with Spark SQL TIMESTAMPDIFF instead.
    valid = valid.withColumn(
        "trip_duration_minutes",
        F.expr(
            "timestampdiff(MICROSECOND, "
            "tpep_pickup_datetime, tpep_dropoff_datetime) / 60000000.0"
        ),
    )

    valid = (
        valid
        .withColumn("pickup_date", F.to_date("tpep_pickup_datetime"))
        .withColumn("pickup_hour", F.hour("tpep_pickup_datetime"))
        .withColumn("revenue", F.col("total_amount").cast("double"))
    )

    valid = add_payment_method(valid)

    valid = (
        valid
        .withColumn(
            "is_negative_fare",
            F.coalesce(F.col("fare_amount") < 0, F.lit(False)),
        )
        .withColumn(
            "is_negative_total",
            F.coalesce(F.col("total_amount") < 0, F.lit(False)),
        )
        .withColumn(
            "is_extreme_fare",
            F.coalesce(F.col("fare_amount") >= 900, F.lit(False)),
        )
        .withColumn(
            "is_extreme_distance",
            F.coalesce(F.col("trip_distance") >= 150, F.lit(False)),
        )
        .withColumn(
            "is_extreme_duration",
            F.coalesce(F.col("trip_duration_minutes") >= 600, F.lit(False)),
        )
        .withColumn(
            "is_unusual_passenger_count",
            F.coalesce(
                (F.col("passenger_count") <= 0)
                | (F.col("passenger_count") > 6),
                F.lit(False),
            ),
        )
    )

    # Join-success markers are deliberately independent of descriptive text.
    # TLC LocationID 264/265 are valid reference rows even though some Zone,
    # Borough, and service_zone attributes are NULL in the official lookup.
    pickup_zones = F.broadcast(
        zones.select(
            F.col("LocationID").alias("PULocationID"),
            F.col("Zone").alias("pickup_zone"),
            F.col("Borough").alias("pickup_borough"),
            F.col("service_zone").alias("pickup_service_zone"),
            F.lit(True).alias("_pickup_zone_matched"),
        )
    )

    dropoff_zones = F.broadcast(
        zones.select(
            F.col("LocationID").alias("DOLocationID"),
            F.col("Zone").alias("dropoff_zone"),
            F.col("Borough").alias("dropoff_borough"),
            F.col("service_zone").alias("dropoff_service_zone"),
            F.lit(True).alias("_dropoff_zone_matched"),
        )
    )

    enriched = (
        valid
        .join(pickup_zones, on="PULocationID", how="left")
        .join(dropoff_zones, on="DOLocationID", how="left")
    )

    final_columns = [
        # Original source fields
        *TAXI_SOURCE_COLUMNS,
        # Phase 9 derived analytical fields
        "pickup_date",
        "pickup_hour",
        "trip_duration_minutes",
        "payment_method",
        "revenue",
        # Geography
        "pickup_zone",
        "pickup_borough",
        "pickup_service_zone",
        "dropoff_zone",
        "dropoff_borough",
        "dropoff_service_zone",
        # Internal join-success markers used only for validation
        "_pickup_zone_matched",
        "_dropoff_zone_matched",
        # Retained anomaly indicators
        "is_negative_fare",
        "is_negative_total",
        "is_extreme_fare",
        "is_extreme_distance",
        "is_extreme_duration",
        "is_unusual_passenger_count",
        # Bronze lineage / audit metadata
        "_source",
        "_source_file",
        "_ingested_at",
        "_run_id",
        "_processing_year",
        "_processing_month",
    ]

    return enriched.select(*final_columns)


def spark_type_to_arrow(data_type):
    if isinstance(data_type, ByteType):
        return pa.int8()
    if isinstance(data_type, ShortType):
        return pa.int16()
    if isinstance(data_type, IntegerType):
        return pa.int32()
    if isinstance(data_type, LongType):
        return pa.int64()
    if isinstance(data_type, FloatType):
        return pa.float32()
    if isinstance(data_type, DoubleType):
        return pa.float64()
    if isinstance(data_type, StringType):
        return pa.string()
    if isinstance(data_type, BooleanType):
        return pa.bool_()
    if isinstance(data_type, DateType):
        return pa.date32()
    if isinstance(data_type, (TimestampType, TimestampNTZType)):
        return pa.timestamp("us")
    if isinstance(data_type, DecimalType):
        return pa.decimal128(data_type.precision, data_type.scale)
    raise TypeError(f"Unsupported Spark type for portable Parquet writer: {data_type}")


def build_arrow_schema(spark_schema):
    return pa.schema(
        [
            pa.field(
                field.name,
                spark_type_to_arrow(field.dataType),
                nullable=field.nullable,
            )
            for field in spark_schema.fields
        ]
    )


def write_parquet_windows_fallback(
    dataframe,
    output_directory: Path,
    run_id: str,
    batch_size: int = 50_000,
):
    if output_directory.exists():
        shutil.rmtree(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)

    arrow_schema = build_arrow_schema(dataframe.schema)
    serialized_schema = arrow_schema.serialize().to_pybytes()
    output_dir_text = str(output_directory.resolve())
    run_tag = run_id.replace("-", "")

    def write_partition(partition_index, rows):
        import pyarrow as worker_pa
        import pyarrow.parquet as worker_pq
        from pathlib import Path as WorkerPath

        partition_schema = worker_pa.ipc.read_schema(
            worker_pa.BufferReader(serialized_schema)
        )
        file_path = (
            WorkerPath(output_dir_text)
            / f"part-{partition_index:05d}-{run_tag}.parquet"
        )

        writer = None
        buffer = []
        row_count = 0

        try:
            for row in rows:
                buffer.append(row.asDict(recursive=False))

                if len(buffer) >= batch_size:
                    table = worker_pa.Table.from_pylist(
                        buffer,
                        schema=partition_schema,
                    )
                    if writer is None:
                        writer = worker_pq.ParquetWriter(
                            str(file_path),
                            partition_schema,
                            compression="snappy",
                        )
                    writer.write_table(table)
                    row_count += len(buffer)
                    buffer.clear()

            if buffer:
                table = worker_pa.Table.from_pylist(
                    buffer,
                    schema=partition_schema,
                )
                if writer is None:
                    writer = worker_pq.ParquetWriter(
                        str(file_path),
                        partition_schema,
                        compression="snappy",
                    )
                writer.write_table(table)
                row_count += len(buffer)

        finally:
            if writer is not None:
                writer.close()

        yield row_count

    partition_counts = (
        dataframe.rdd
        .mapPartitionsWithIndex(write_partition)
        .collect()
    )

    worker_rows = sum(partition_counts)
    parquet_files = sorted(output_directory.glob("part-*.parquet"))
    verified_rows = sum(
        pq.ParquetFile(str(file)).metadata.num_rows
        for file in parquet_files
    )

    return worker_rows, verified_rows, len(parquet_files)


def write_silver(dataframe, output_directory: Path, run_id: str):
    if os.name == "nt":
        print(
            "Writer: Windows portable Parquet adapter "
            "(PySpark processing + PyArrow persistence)"
        )
        return write_parquet_windows_fallback(
            dataframe,
            output_directory,
            run_id,
        )

    if output_directory.exists():
        shutil.rmtree(output_directory)

    dataframe.write.mode("overwrite").parquet(spark_uri(output_directory))

    parquet_files = sorted(output_directory.glob("part-*.parquet"))
    verified_rows = sum(
        pq.ParquetFile(str(file)).metadata.num_rows
        for file in parquet_files
    )
    return verified_rows, verified_rows, len(parquet_files)


def write_reconciliation(rows: list[dict]) -> None:
    RECON_REPORT.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "run_id",
        "processing_month",
        "bronze_rows",
        "silver_rows",
        "rows_rejected",
        "unmatched_pickup_zone_rows",
        "unmatched_dropoff_zone_rows",
        "status",
    ]

    with RECON_REPORT.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def process_month(
    spark: SparkSession,
    month: int,
    zones,
    duplicate_meta,
):
    month_text = f"{month:02d}"
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    files = collect_month_files(month)
    bronze_rows = parquet_row_count(files)

    output_directory = SILVER_ROOT / f"month={month_text}"

    metric = {
        "run_id": run_id,
        "source": "yellow_taxi",
        "layer": "silver",
        "processing_year": 2025,
        "processing_month": month,
        "started_at": started_at.isoformat(),
        "finished_at": None,
        "rows_read": bronze_rows,
        "rows_valid": None,
        "rows_rejected": None,
        "status": "RUNNING",
        "error_message": None,
    }

    print("\n" + "=" * 78)
    print(f"PHASE 9 - TAXI SILVER - 2025-{month_text}")
    print("=" * 78)
    print(f"Bronze files: {len(files)}")
    print(f"Bronze rows (Parquet metadata): {bronze_rows:,}")
    print(f"Output: {output_directory}")
    print(f"Run ID: {run_id}")

    try:
        df = read_explicit_parquet_files(spark, files)
        validate_bronze_schema(df)

        prepared = add_duplicate_reject_flag(df, duplicate_meta)
        prepared = add_rejection_flags(prepared)

        silver_df = enrich_and_derive(prepared, zones)
        silver_df = silver_df.persist(StorageLevel.MEMORY_AND_DISK)

        validation = (
            silver_df
            .agg(
                F.count(F.lit(1)).alias("silver_rows"),
                F.sum(
                    F.when(F.col("_pickup_zone_matched").isNull(), 1).otherwise(0)
                ).alias("unmatched_pickup_zone_rows"),
                F.sum(
                    F.when(F.col("_dropoff_zone_matched").isNull(), 1).otherwise(0)
                ).alias("unmatched_dropoff_zone_rows"),
            )
            .collect()[0]
        )

        silver_rows = int(validation["silver_rows"])
        unmatched_pickup = int(
            validation["unmatched_pickup_zone_rows"] or 0
        )
        unmatched_dropoff = int(
            validation["unmatched_dropoff_zone_rows"] or 0
        )
        rows_rejected = bronze_rows - silver_rows

        print(f"Silver candidate rows: {silver_rows:,}")
        print(f"Rejected rows: {rows_rejected:,}")
        print(f"Unmatched pickup zones: {unmatched_pickup:,}")
        print(f"Unmatched dropoff zones: {unmatched_dropoff:,}")

        if rows_rejected < 0:
            raise RuntimeError(
                "Reconciliation failure: Silver rows exceed Bronze rows"
            )

        if unmatched_pickup != 0 or unmatched_dropoff != 0:
            raise RuntimeError(
                "ZONE_ENRICHMENT_FAILURE: "
                f"pickup_unmatched={unmatched_pickup:,}, "
                f"dropoff_unmatched={unmatched_dropoff:,}"
            )

        # Validation markers are internal controls, not Silver business columns.
        silver_output_df = silver_df.drop(
            "_pickup_zone_matched",
            "_dropoff_zone_matched",
        )

        worker_rows, verified_rows, file_count = write_silver(
            silver_output_df,
            output_directory,
            run_id,
        )

        silver_df.unpersist()

        print(f"Worker rows: {worker_rows:,}")
        print(f"Verified Silver rows: {verified_rows:,}")
        print(f"Silver Parquet files: {file_count}")

        if worker_rows != silver_rows:
            raise RuntimeError(
                "Worker reconciliation failed: "
                f"expected={silver_rows:,}, workers={worker_rows:,}"
            )

        if verified_rows != silver_rows:
            raise RuntimeError(
                "Silver file reconciliation failed: "
                f"expected={silver_rows:,}, files={verified_rows:,}"
            )

        metric.update(
            {
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "rows_valid": verified_rows,
                "rows_rejected": rows_rejected,
                "status": "SUCCESS",
                "error_message": None,
            }
        )
        append_run_log(metric)

        print("Reconciliation: SUCCESS")
        print(f"2025-{month_text}: SILVER SUCCESS")

        return {
            "run_id": run_id,
            "processing_month": f"2025-{month_text}",
            "bronze_rows": bronze_rows,
            "silver_rows": verified_rows,
            "rows_rejected": rows_rejected,
            "unmatched_pickup_zone_rows": unmatched_pickup,
            "unmatched_dropoff_zone_rows": unmatched_dropoff,
            "status": "SUCCESS",
        }

    except Exception as exc:
        metric.update(
            {
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "status": "FAILED",
                "error_message": str(exc),
            }
        )
        append_run_log(metric)
        print(f"2025-{month_text}: SILVER FAILED")
        print(f"Error: {exc}")
        raise


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Phase 9 - Build 2025 Yellow Taxi Silver datasets."
    )
    parser.add_argument(
        "--months",
        nargs="+",
        type=int,
        default=list(range(1, 13)),
        help="Months to process. Example: --months 1 or --months 1 2 3",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    invalid_months = [m for m in args.months if m < 1 or m > 12]
    if invalid_months:
        raise ValueError(f"Invalid months: {invalid_months}")

    months = sorted(set(args.months))

    spark = create_spark()
    spark.sparkContext.setLogLevel("WARN")

    try:
        print("=" * 78)
        print("PHASE 9 - YELLOW TAXI DATA PREPARATION")
        print("=" * 78)
        print("Revenue definition: revenue = total_amount")
        print("Candidate anomalies: FLAG AND RETAIN")
        print("Proven-invalid records: EXCLUDED FROM SILVER")

        full_year_metadata_rows = parquet_row_count(collect_all_files())
        print(f"Full-year Bronze rows: {full_year_metadata_rows:,}")

        if full_year_metadata_rows != EXPECTED_FULL_YEAR_BRONZE_ROWS:
            raise RuntimeError(
                "Full-year Bronze reconciliation failed: "
                f"expected={EXPECTED_FULL_YEAR_BRONZE_ROWS:,}, "
                f"actual={full_year_metadata_rows:,}"
            )

        duplicate_meta, duplicate_rejections = find_global_duplicate_metadata(
            spark
        )

        zones = load_zone_dimension(spark)

        results = []
        for month in months:
            result = process_month(
                spark,
                month,
                zones,
                duplicate_meta,
            )
            results.append(result)

        write_reconciliation(results)

        total_bronze = sum(r["bronze_rows"] for r in results)
        total_silver = sum(r["silver_rows"] for r in results)
        total_rejected = sum(r["rows_rejected"] for r in results)

        print("\n" + "=" * 78)
        print("PHASE 9 RUN SUMMARY")
        print("=" * 78)
        print(f"Months processed: {', '.join(f'{m:02d}' for m in months)}")
        print(f"Bronze rows: {total_bronze:,}")
        print(f"Silver rows: {total_silver:,}")
        print(f"Rejected rows: {total_rejected:,}")
        print(f"Global duplicate rejections expected: {duplicate_rejections:,}")
        print(f"Reconciliation report: {RECON_REPORT}")

        if months == list(range(1, 13)):
            if total_bronze != EXPECTED_FULL_YEAR_BRONZE_ROWS:
                raise RuntimeError(
                    "Full-year Bronze total mismatch after processing"
                )
            if total_rejected != EXPECTED_FULL_YEAR_REJECTED_ROWS:
                raise RuntimeError(
                    "Full-year rejected-row mismatch: "
                    f"expected={EXPECTED_FULL_YEAR_REJECTED_ROWS:,}, "
                    f"actual={total_rejected:,}"
                )
            if total_silver != EXPECTED_FULL_YEAR_SILVER_ROWS:
                raise RuntimeError(
                    "Full-year Silver-row mismatch: "
                    f"expected={EXPECTED_FULL_YEAR_SILVER_ROWS:,}, "
                    f"actual={total_silver:,}"
                )

            print("\nFULL-YEAR RECONCILIATION: SUCCESS")
            print(
                f"{EXPECTED_FULL_YEAR_BRONZE_ROWS:,} Bronze "
                f"- {EXPECTED_FULL_YEAR_REJECTED_ROWS:,} rejected "
                f"= {EXPECTED_FULL_YEAR_SILVER_ROWS:,} Silver"
            )

        print("\nPHASE 9 TAXI SILVER BUILD: SUCCESS")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
