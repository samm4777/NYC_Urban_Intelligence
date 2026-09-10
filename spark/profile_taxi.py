import csv
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq
from pyspark.sql import SparkSession
from pyspark.sql import functions as F


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_TAXI_ROOT = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "taxi"
    / "year=2025"
)

REPORT_DIR = (
    PROJECT_ROOT
    / "reports"
    / "profiling"
)

EXPECTED_FULL_YEAR_ROWS = 48_722_602


def spark_uri(path: Path) -> str:
    """Windows-safe local URI without encoding '=' as %3D."""
    return "file:///" + path.resolve().as_posix()


def create_spark() -> SparkSession:
    return (
        SparkSession.builder
        .appName("NYC-Taxi-Data-Profiling")
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.driver.memory", "4g")
        .config("spark.sql.parquet.mergeSchema", "true")
        .getOrCreate()
    )


def csv_write(path: Path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def collect_raw_files():
    files = []

    for month in range(1, 13):
        month_text = f"{month:02d}"
        path = (
            RAW_TAXI_ROOT
            / f"month={month_text}"
            / f"yellow_tripdata_2025-{month_text}.parquet"
        )

        if not path.exists():
            raise FileNotFoundError(f"Missing Taxi Raw file: {path}")

        files.append((month, path))

    return files


def profile_parquet_metadata(raw_files):
    monthly_rows = []
    schema_rows = []
    schema_signatures = {}

    for month, path in raw_files:
        parquet_file = pq.ParquetFile(str(path))
        row_count = parquet_file.metadata.num_rows
        schema = parquet_file.schema_arrow

        monthly_rows.append(
            {
                "month": f"2025-{month:02d}",
                "file_name": path.name,
                "row_count": row_count,
                "column_count": len(schema.names),
            }
        )

        signature_parts = []

        for field in schema:
            type_text = str(field.type)
            signature_parts.append(f"{field.name}:{type_text}")

            schema_rows.append(
                {
                    "month": f"2025-{month:02d}",
                    "column_name": field.name,
                    "data_type": type_text,
                    "nullable": field.nullable,
                }
            )

        schema_signatures[month] = tuple(signature_parts)

    baseline = schema_signatures[1]

    schema_difference_rows = []

    for month in range(1, 13):
        matches_january = schema_signatures[month] == baseline

        schema_difference_rows.append(
            {
                "month": f"2025-{month:02d}",
                "matches_january_schema": matches_january,
                "schema_signature": " | ".join(schema_signatures[month]),
            }
        )

    return monthly_rows, schema_rows, schema_difference_rows


def agg_single_row(df, expressions):
    return df.agg(*expressions).collect()[0].asDict()


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    print("=" * 78)
    print("PHASE 6 - FULL-YEAR YELLOW TAXI DATA PROFILING")
    print("=" * 78)
    print(f"Run ID: {run_id}")

    raw_files = collect_raw_files()

    print()
    print("1. PARQUET METADATA / MONTHLY SCHEMA CHECK")
    print("-" * 78)

    monthly_rows, schema_rows, schema_diff_rows = profile_parquet_metadata(
        raw_files
    )

    metadata_total = sum(row["row_count"] for row in monthly_rows)
    differing_months = [
        row["month"]
        for row in schema_diff_rows
        if not row["matches_january_schema"]
    ]

    print(f"Raw files: {len(raw_files)}")
    print(f"Metadata row count: {metadata_total:,}")
    print(f"Expected row count: {EXPECTED_FULL_YEAR_ROWS:,}")
    print(f"Row-count match: {metadata_total == EXPECTED_FULL_YEAR_ROWS}")
    print(
        "Schema differences vs January: "
        + (", ".join(differing_months) if differing_months else "NONE")
    )

    csv_write(
        REPORT_DIR / "taxi_monthly_rows.csv",
        monthly_rows,
        ["month", "file_name", "row_count", "column_count"],
    )

    csv_write(
        REPORT_DIR / "taxi_schema_by_month.csv",
        schema_rows,
        ["month", "column_name", "data_type", "nullable"],
    )

    csv_write(
        REPORT_DIR / "taxi_schema_differences.csv",
        schema_diff_rows,
        ["month", "matches_january_schema", "schema_signature"],
    )

    spark = create_spark()
    spark.sparkContext.setLogLevel("WARN")

    try:
        paths = [spark_uri(path) for _, path in raw_files]

        print()
        print("2. FULL-YEAR PYSPARK INGESTION FOR PROFILING")
        print("-" * 78)

        df = (
            spark.read
            .option("mergeSchema", "true")
            .parquet(*paths)
        )

        source_columns = df.columns

        print(f"Columns: {len(source_columns)}")
        print("Column list:")
        for name in source_columns:
            print(f"  - {name}")

        print()
        print("Spark schema:")
        df.printSchema()

        full_year_count = df.count()

        print(f"Full-year Spark row count: {full_year_count:,}")
        print(
            f"Matches metadata total: {full_year_count == metadata_total}"
        )

        print()
        print("3. MISSING VALUES")
        print("-" * 78)

        missing_exprs = [
            F.sum(F.when(F.col(c).isNull(), 1).otherwise(0)).alias(c)
            for c in source_columns
        ]

        missing_map = agg_single_row(df, missing_exprs)

        missing_rows = []

        for column in source_columns:
            null_count = int(missing_map[column] or 0)
            missing_rows.append(
                {
                    "column_name": column,
                    "null_count": null_count,
                    "null_percent": round(
                        (null_count / full_year_count) * 100, 6
                    ),
                }
            )
            print(
                f"{column}: {null_count:,} "
                f"({(null_count / full_year_count) * 100:.4f}%)"
            )

        csv_write(
            REPORT_DIR / "taxi_missing_values.csv",
            missing_rows,
            ["column_name", "null_count", "null_percent"],
        )

        print()
        print("4. DATE RANGE / DEFINITELY INVALID RECORDS")
        print("-" * 78)

        pickup = F.col("tpep_pickup_datetime")
        dropoff = F.col("tpep_dropoff_datetime")

        date_metrics = agg_single_row(
            df,
            [
                F.min(pickup).alias("pickup_min"),
                F.max(pickup).alias("pickup_max"),
                F.min(dropoff).alias("dropoff_min"),
                F.max(dropoff).alias("dropoff_max"),
                F.sum(
                    F.when(pickup.isNull(), 1).otherwise(0)
                ).alias("missing_pickup_timestamp"),
                F.sum(
                    F.when(dropoff.isNull(), 1).otherwise(0)
                ).alias("missing_dropoff_timestamp"),
                F.sum(
                    F.when(
                        pickup.isNotNull()
                        & dropoff.isNotNull()
                        & (dropoff < pickup),
                        1,
                    ).otherwise(0)
                ).alias("dropoff_before_pickup"),
                F.sum(
                    F.when(
                        pickup.isNotNull()
                        & (
                            (pickup < F.lit("2025-01-01 00:00:00"))
                            | (pickup >= F.lit("2026-01-01 00:00:00"))
                        ),
                        1,
                    ).otherwise(0)
                ).alias("pickup_outside_2025"),
            ],
        )

        for key, value in date_metrics.items():
            print(f"{key}: {value}")

        definitely_invalid_rows = [
            {
                "classification": "DEFINITELY_INVALID",
                "check_name": "MISSING_PICKUP_TIMESTAMP",
                "description": "Pickup timestamp is null.",
                "record_count": int(
                    date_metrics["missing_pickup_timestamp"] or 0
                ),
            },
            {
                "classification": "DEFINITELY_INVALID",
                "check_name": "MISSING_DROPOFF_TIMESTAMP",
                "description": "Drop-off timestamp is null.",
                "record_count": int(
                    date_metrics["missing_dropoff_timestamp"] or 0
                ),
            },
            {
                "classification": "DEFINITELY_INVALID",
                "check_name": "DROPOFF_BEFORE_PICKUP",
                "description": "Drop-off timestamp occurs before pickup.",
                "record_count": int(
                    date_metrics["dropoff_before_pickup"] or 0
                ),
            },
            {
                "classification": "DEFINITELY_INVALID",
                "check_name": "PICKUP_OUTSIDE_2025",
                "description": "Pickup timestamp is outside intended 2025 period.",
                "record_count": int(
                    date_metrics["pickup_outside_2025"] or 0
                ),
            },
        ]

        csv_write(
            REPORT_DIR / "taxi_definitely_invalid.csv",
            definitely_invalid_rows,
            [
                "classification",
                "check_name",
                "description",
                "record_count",
            ],
        )

        print()
        print("5. CANDIDATE ANOMALIES / SUSPICIOUS VALUES")
        print("-" * 78)

        duration_seconds = (
            F.unix_timestamp(dropoff)
            - F.unix_timestamp(pickup)
        )

        anomaly_metrics = agg_single_row(
            df,
            [
                F.sum(
                    F.when(F.col("fare_amount") >= 900, 1).otherwise(0)
                ).alias("fare_ge_900"),
                F.sum(
                    F.when(F.col("fare_amount") < 0, 1).otherwise(0)
                ).alias("negative_fare"),
                F.sum(
                    F.when(F.col("total_amount") < 0, 1).otherwise(0)
                ).alias("negative_total_amount"),
                F.sum(
                    F.when(F.col("trip_distance") >= 150, 1).otherwise(0)
                ).alias("distance_ge_150"),
                F.sum(
                    F.when(F.col("trip_distance") < 0, 1).otherwise(0)
                ).alias("negative_trip_distance"),
                F.sum(
                    F.when(duration_seconds >= 10 * 60 * 60, 1).otherwise(0)
                ).alias("duration_ge_10_hours"),
                F.sum(
                    F.when(
                        F.col("PULocationID").isNull(),
                        1,
                    ).otherwise(0)
                ).alias("missing_pickup_location"),
                F.sum(
                    F.when(
                        F.col("DOLocationID").isNull(),
                        1,
                    ).otherwise(0)
                ).alias("missing_dropoff_location"),
                F.sum(
                    F.when(
                        F.col("passenger_count") <= 0,
                        1,
                    ).otherwise(0)
                ).alias("passenger_count_le_0"),
                F.sum(
                    F.when(
                        F.col("passenger_count") > 6,
                        1,
                    ).otherwise(0)
                ).alias("passenger_count_gt_6"),
            ],
        )

        anomaly_definitions = [
            (
                "FARE_GE_900",
                "Fare amount is at least 900; investigate before defining a rule.",
                "fare_ge_900",
            ),
            (
                "NEGATIVE_FARE",
                "Fare amount is negative; may include adjustments/refunds and requires investigation.",
                "negative_fare",
            ),
            (
                "NEGATIVE_TOTAL_AMOUNT",
                "Total amount is negative; requires investigation.",
                "negative_total_amount",
            ),
            (
                "DISTANCE_GE_150",
                "Trip distance is at least 150 miles; investigate before defining a rule.",
                "distance_ge_150",
            ),
            (
                "NEGATIVE_TRIP_DISTANCE",
                "Trip distance is negative; requires investigation.",
                "negative_trip_distance",
            ),
            (
                "DURATION_GE_10_HOURS",
                "Trip duration is at least 10 hours; investigate before defining a rule.",
                "duration_ge_10_hours",
            ),
            (
                "MISSING_PICKUP_LOCATION",
                "Pickup location ID is missing.",
                "missing_pickup_location",
            ),
            (
                "MISSING_DROPOFF_LOCATION",
                "Drop-off location ID is missing.",
                "missing_dropoff_location",
            ),
            (
                "PASSENGER_COUNT_LE_0",
                "Passenger count is zero/negative; may represent unknown values and requires investigation.",
                "passenger_count_le_0",
            ),
            (
                "PASSENGER_COUNT_GT_6",
                "Passenger count exceeds 6; requires investigation.",
                "passenger_count_gt_6",
            ),
        ]

        candidate_rows = []

        for check_name, description, metric_key in anomaly_definitions:
            value = int(anomaly_metrics[metric_key] or 0)

            candidate_rows.append(
                {
                    "classification": "CANDIDATE_ANOMALY",
                    "check_name": check_name,
                    "description": description,
                    "record_count": value,
                }
            )

            print(f"{check_name}: {value:,}")

        csv_write(
            REPORT_DIR / "taxi_candidate_anomalies.csv",
            candidate_rows,
            [
                "classification",
                "check_name",
                "description",
                "record_count",
            ],
        )

        print()
        print("6. OUTLIER DISTRIBUTION")
        print("-" * 78)

        profiled = df.withColumn(
            "_profile_duration_seconds",
            duration_seconds.cast("double"),
        )

        quantile_columns = [
            "fare_amount",
            "total_amount",
            "trip_distance",
            "passenger_count",
            "_profile_duration_seconds",
        ]

        probabilities = [
            0.0,
            0.01,
            0.50,
            0.95,
            0.99,
            0.999,
            1.0,
        ]

        quantile_results = profiled.approxQuantile(
            quantile_columns,
            probabilities,
            0.001,
        )

        outlier_rows = []

        for column, values in zip(
            quantile_columns,
            quantile_results,
        ):
            row = {
                "column_name": column,
                "min": values[0] if len(values) > 0 else None,
                "p01": values[1] if len(values) > 1 else None,
                "p50": values[2] if len(values) > 2 else None,
                "p95": values[3] if len(values) > 3 else None,
                "p99": values[4] if len(values) > 4 else None,
                "p999": values[5] if len(values) > 5 else None,
                "max": values[6] if len(values) > 6 else None,
            }

            outlier_rows.append(row)
            print(row)

        csv_write(
            REPORT_DIR / "taxi_outlier_quantiles.csv",
            outlier_rows,
            [
                "column_name",
                "min",
                "p01",
                "p50",
                "p95",
                "p99",
                "p999",
                "max",
            ],
        )

        print()
        print("7. DUPLICATE COUNT")
        print("-" * 78)
        print(
            "Computing duplicate candidates using SHA-256 of the complete "
            "source record. This can take several minutes."
        )

        record_hash_df = df.select(
            F.sha2(
                F.to_json(
                    F.struct(
                        *[F.col(c) for c in source_columns]
                    )
                ),
                256,
            ).alias("_record_hash")
        )

        distinct_records = (
            record_hash_df
            .select("_record_hash")
            .distinct()
            .count()
        )

        duplicate_count = full_year_count - distinct_records

        print(f"Total records: {full_year_count:,}")
        print(f"Distinct record hashes: {distinct_records:,}")
        print(f"Duplicate record count: {duplicate_count:,}")

        duplicate_rows = [
            {
                "method": "SHA256_OF_COMPLETE_SOURCE_RECORD",
                "total_rows": full_year_count,
                "distinct_record_hashes": distinct_records,
                "duplicate_record_count": duplicate_count,
            }
        ]

        csv_write(
            REPORT_DIR / "taxi_duplicate_count.csv",
            duplicate_rows,
            [
                "method",
                "total_rows",
                "distinct_record_hashes",
                "duplicate_record_count",
            ],
        )

        print()
        print("8. FINAL SUMMARY")
        print("-" * 78)

        summary = {
            "run_id": run_id,
            "source": "yellow_taxi",
            "profile_year": 2025,
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "raw_file_count": len(raw_files),
            "row_count": full_year_count,
            "expected_row_count": EXPECTED_FULL_YEAR_ROWS,
            "row_count_match": (
                full_year_count == EXPECTED_FULL_YEAR_ROWS
            ),
            "column_count": len(source_columns),
            "columns": source_columns,
            "pickup_min": str(date_metrics["pickup_min"]),
            "pickup_max": str(date_metrics["pickup_max"]),
            "dropoff_min": str(date_metrics["dropoff_min"]),
            "dropoff_max": str(date_metrics["dropoff_max"]),
            "schema_difference_months_vs_january": differing_months,
            "duplicate_record_count": duplicate_count,
            "definitely_invalid": {
                row["check_name"]: row["record_count"]
                for row in definitely_invalid_rows
            },
            "candidate_anomalies": {
                row["check_name"]: row["record_count"]
                for row in candidate_rows
            },
            "status": "SUCCESS",
        }

        with open(
            REPORT_DIR / "taxi_profile_summary.json",
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(summary, f, indent=2)

        print(f"Rows profiled: {full_year_count:,}")
        print(f"Columns profiled: {len(source_columns)}")
        print(f"Duplicate records: {duplicate_count:,}")
        print(
            "Definitely-invalid checks: "
            f"{len(definitely_invalid_rows)}"
        )
        print(
            "Candidate-anomaly checks: "
            f"{len(candidate_rows)}"
        )
        print(f"Reports: {REPORT_DIR}")
        print()
        print("TAXI DATA PROFILING SUCCESS")

    finally:
        spark.stop()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print()
        print("TAXI DATA PROFILING FAILED")
        print(f"Error: {exc}")
        sys.exit(1)
