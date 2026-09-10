import csv
import json
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_311_ROOT = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "complaints_311"
    / "year=2025"
)

REPORT_DIR = (
    PROJECT_ROOT
    / "reports"
    / "profiling"
)

EXPECTED_ROWS = 3_655_040


def spark_uri(path: Path) -> str:
    return "file:///" + path.resolve().as_posix()


def create_spark():
    return (
        SparkSession.builder
        .appName("NYC-311-Data-Profiling")
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.driver.memory", "4g")
        .getOrCreate()
    )


def write_csv(path: Path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def collect_files():
    files = sorted(RAW_311_ROOT.rglob("*.json"))

    if len(files) != 80:
        raise RuntimeError(
            f"Expected 80 NYC 311 JSON pages, found {len(files)}"
        )

    return files


def inspect_file_schemas(files):
    """
    Build a source-level field-presence profile without changing records.
    Each page is loaded sequentially, so memory stays bounded to one page.
    """
    monthly_keys = defaultdict(set)
    monthly_rows = defaultdict(int)

    for path in files:
        month = path.parent.name.split("=")[-1]

        with open(path, "r", encoding="utf-8") as file:
            records = json.load(file)

        monthly_rows[month] += len(records)

        for record in records:
            monthly_keys[month].update(record.keys())

    baseline = monthly_keys["01"]

    schema_rows = []

    for month in sorted(monthly_keys):
        added = sorted(monthly_keys[month] - baseline)
        missing = sorted(baseline - monthly_keys[month])

        schema_rows.append(
            {
                "month": f"2025-{month}",
                "field_count": len(monthly_keys[month]),
                "matches_january_field_set": not added and not missing,
                "fields_added_vs_january": "|".join(added),
                "fields_missing_vs_january": "|".join(missing),
                "rows": monthly_rows[month],
            }
        )

    return schema_rows


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    print("=" * 78)
    print("PHASE 6 - NYC 311 DATA PROFILING")
    print("=" * 78)
    print(f"Run ID: {run_id}")

    files = collect_files()

    print()
    print("1. SOURCE FILE / SCHEMA PRESENCE CHECK")
    print("-" * 78)
    print(f"JSON pages: {len(files)}")

    schema_rows = inspect_file_schemas(files)

    schema_differences = [
        row["month"]
        for row in schema_rows
        if not row["matches_january_field_set"]
    ]

    for row in schema_rows:
        print(
            f"{row['month']}: rows={row['rows']:,}, "
            f"fields={row['field_count']}, "
            f"matches_january={row['matches_january_field_set']}"
        )

    write_csv(
        REPORT_DIR / "311_schema_differences.csv",
        schema_rows,
        [
            "month",
            "field_count",
            "matches_january_field_set",
            "fields_added_vs_january",
            "fields_missing_vs_january",
            "rows",
        ],
    )

    spark = create_spark()
    spark.sparkContext.setLogLevel("WARN")

    try:
        paths = [spark_uri(path) for path in files]

        print()
        print("2. FULL-YEAR PYSPARK INGESTION")
        print("-" * 78)

        df = (
            spark.read
            .option("multiLine", "true")
            .json(paths)
        )

        row_count = df.count()
        columns = sorted(df.columns)

        print(f"Rows: {row_count:,}")
        print(f"Expected rows: {EXPECTED_ROWS:,}")
        print(f"Row-count match: {row_count == EXPECTED_ROWS}")
        print(f"Columns: {len(columns)}")

        print()
        print("Column list:")
        for column in columns:
            print(f"  - {column}")

        print()
        print("Spark schema:")
        df.printSchema()

        if row_count != EXPECTED_ROWS:
            raise RuntimeError(
                f"311 row-count mismatch: {row_count:,} != {EXPECTED_ROWS:,}"
            )

        schema_output = [
            {
                "column_name": field.name,
                "data_type": field.dataType.simpleString(),
                "nullable": field.nullable,
            }
            for field in df.schema.fields
        ]

        write_csv(
            REPORT_DIR / "311_column_types.csv",
            schema_output,
            ["column_name", "data_type", "nullable"],
        )

        print()
        print("3. MISSING VALUES")
        print("-" * 78)

        important_columns = [
            "unique_key",
            "created_date",
            "closed_date",
            "agency",
            "complaint_type",
            "descriptor",
            "status",
            "borough",
            "incident_zip",
            "latitude",
            "longitude",
        ]

        missing_exprs = [
            F.sum(
                F.when(
                    F.col(column).isNull()
                    | (F.trim(F.col(column).cast("string")) == ""),
                    1,
                ).otherwise(0)
            ).alias(column)
            for column in important_columns
        ]

        missing_map = df.agg(*missing_exprs).collect()[0].asDict()

        missing_rows = []

        for column in important_columns:
            value = int(missing_map[column] or 0)

            missing_rows.append(
                {
                    "column_name": column,
                    "missing_count": value,
                    "missing_percent": round(
                        value / row_count * 100,
                        6,
                    ),
                }
            )

            print(
                f"{column}: {value:,} "
                f"({value / row_count * 100:.4f}%)"
            )

        write_csv(
            REPORT_DIR / "311_missing_values.csv",
            missing_rows,
            [
                "column_name",
                "missing_count",
                "missing_percent",
            ],
        )

        print()
        print("4. DATE RANGE / DEFINITELY INVALID")
        print("-" * 78)

        created_ts = F.to_timestamp("created_date")
        closed_ts = F.to_timestamp("closed_date")

        date_metrics = (
            df
            .withColumn("_created_ts", created_ts)
            .withColumn("_closed_ts", closed_ts)
            .agg(
                F.min("_created_ts").alias("created_min"),
                F.max("_created_ts").alias("created_max"),
                F.min("_closed_ts").alias("closed_min"),
                F.max("_closed_ts").alias("closed_max"),
                F.sum(
                    F.when(
                        F.col("_created_ts").isNull(),
                        1,
                    ).otherwise(0)
                ).alias("missing_or_unparseable_created"),
                F.sum(
                    F.when(
                        F.col("_created_ts").isNotNull()
                        & (
                            (F.col("_created_ts") < F.lit("2025-01-01 00:00:00"))
                            | (F.col("_created_ts") >= F.lit("2026-01-01 00:00:00"))
                        ),
                        1,
                    ).otherwise(0)
                ).alias("created_outside_2025"),
                F.sum(
                    F.when(
                        F.col("_created_ts").isNotNull()
                        & F.col("_closed_ts").isNotNull()
                        & (F.col("_closed_ts") < F.col("_created_ts")),
                        1,
                    ).otherwise(0)
                ).alias("closed_before_created"),
                F.sum(
                    F.when(
                        F.col("latitude").isNotNull()
                        & (
                            (F.col("latitude").cast("double") < -90)
                            | (F.col("latitude").cast("double") > 90)
                        ),
                        1,
                    ).otherwise(0)
                ).alias("invalid_latitude_range"),
                F.sum(
                    F.when(
                        F.col("longitude").isNotNull()
                        & (
                            (F.col("longitude").cast("double") < -180)
                            | (F.col("longitude").cast("double") > 180)
                        ),
                        1,
                    ).otherwise(0)
                ).alias("invalid_longitude_range"),
            )
            .collect()[0]
            .asDict()
        )

        for key, value in date_metrics.items():
            print(f"{key}: {value}")

        definitely_invalid_rows = [
            {
                "classification": "DEFINITELY_INVALID",
                "check_name": "MISSING_OR_UNPARSEABLE_CREATED_DATE",
                "description": "created_date is missing or cannot be parsed.",
                "record_count": int(
                    date_metrics["missing_or_unparseable_created"] or 0
                ),
            },
            {
                "classification": "DEFINITELY_INVALID",
                "check_name": "CREATED_DATE_OUTSIDE_2025",
                "description": "created_date falls outside the intended 2025 period.",
                "record_count": int(
                    date_metrics["created_outside_2025"] or 0
                ),
            },
            {
                "classification": "DEFINITELY_INVALID",
                "check_name": "CLOSED_BEFORE_CREATED",
                "description": "closed_date occurs before created_date.",
                "record_count": int(
                    date_metrics["closed_before_created"] or 0
                ),
            },
            {
                "classification": "DEFINITELY_INVALID",
                "check_name": "INVALID_LATITUDE_RANGE",
                "description": "Latitude is outside the structural range [-90, 90].",
                "record_count": int(
                    date_metrics["invalid_latitude_range"] or 0
                ),
            },
            {
                "classification": "DEFINITELY_INVALID",
                "check_name": "INVALID_LONGITUDE_RANGE",
                "description": "Longitude is outside the structural range [-180, 180].",
                "record_count": int(
                    date_metrics["invalid_longitude_range"] or 0
                ),
            },
        ]

        write_csv(
            REPORT_DIR / "311_definitely_invalid.csv",
            definitely_invalid_rows,
            [
                "classification",
                "check_name",
                "description",
                "record_count",
            ],
        )

        print()
        print("5. DUPLICATE UNIQUE KEYS")
        print("-" * 78)

        non_null_keys = (
            df
            .where(F.col("unique_key").isNotNull())
            .select("unique_key")
        )

        non_null_key_count = non_null_keys.count()
        distinct_key_count = non_null_keys.distinct().count()
        duplicate_unique_key_rows = (
            non_null_key_count - distinct_key_count
        )

        print(f"Non-null unique_key rows: {non_null_key_count:,}")
        print(f"Distinct unique_key values: {distinct_key_count:,}")
        print(f"Duplicate unique_key rows: {duplicate_unique_key_rows:,}")

        write_csv(
            REPORT_DIR / "311_duplicate_count.csv",
            [
                {
                    "business_key": "unique_key",
                    "non_null_rows": non_null_key_count,
                    "distinct_values": distinct_key_count,
                    "duplicate_rows": duplicate_unique_key_rows,
                }
            ],
            [
                "business_key",
                "non_null_rows",
                "distinct_values",
                "duplicate_rows",
            ],
        )

        print()
        print("6. CANDIDATE ANOMALIES")
        print("-" * 78)

        profiled = (
            df
            .withColumn("_created_ts", created_ts)
            .withColumn("_closed_ts", closed_ts)
            .withColumn(
                "_resolution_hours",
                (
                    F.unix_timestamp("_closed_ts")
                    - F.unix_timestamp("_created_ts")
                ) / 3600.0,
            )
        )

        candidate_metrics = (
            profiled
            .agg(
                F.sum(
                    F.when(
                        F.col("latitude").isNull()
                        | F.col("longitude").isNull(),
                        1,
                    ).otherwise(0)
                ).alias("missing_coordinates"),
                F.sum(
                    F.when(
                        F.col("_resolution_hours") > 365 * 24,
                        1,
                    ).otherwise(0)
                ).alias("resolution_over_365_days"),
                F.sum(
                    F.when(
                        F.col("borough").isNull()
                        | (
                            ~F.upper(F.col("borough")).isin(
                                "BRONX",
                                "BROOKLYN",
                                "MANHATTAN",
                                "QUEENS",
                                "STATEN ISLAND",
                                "UNSPECIFIED",
                            )
                        ),
                        1,
                    ).otherwise(0)
                ).alias("missing_or_unexpected_borough"),
            )
            .collect()[0]
            .asDict()
        )

        candidate_rows = [
            {
                "classification": "CANDIDATE_ANOMALY",
                "check_name": "MISSING_COORDINATES",
                "description": (
                    "Latitude or longitude is missing; assess impact on spatial enrichment."
                ),
                "record_count": int(
                    candidate_metrics["missing_coordinates"] or 0
                ),
            },
            {
                "classification": "CANDIDATE_ANOMALY",
                "check_name": "RESOLUTION_OVER_365_DAYS",
                "description": (
                    "Closed complaint has resolution duration greater than 365 days."
                ),
                "record_count": int(
                    candidate_metrics["resolution_over_365_days"] or 0
                ),
            },
            {
                "classification": "CANDIDATE_ANOMALY",
                "check_name": "MISSING_OR_UNEXPECTED_BOROUGH",
                "description": (
                    "Borough is missing or outside the expected NYC/Unspecified set."
                ),
                "record_count": int(
                    candidate_metrics["missing_or_unexpected_borough"] or 0
                ),
            },
            {
                "classification": "CANDIDATE_ANOMALY",
                "check_name": "DUPLICATE_UNIQUE_KEY_ROWS",
                "description": (
                    "Repeated 311 unique_key values require investigation before deduplication."
                ),
                "record_count": int(duplicate_unique_key_rows),
            },
        ]

        for row in candidate_rows:
            print(f"{row['check_name']}: {row['record_count']:,}")

        write_csv(
            REPORT_DIR / "311_candidate_anomalies.csv",
            candidate_rows,
            [
                "classification",
                "check_name",
                "description",
                "record_count",
            ],
        )

        print()
        print("7. DISTRIBUTION / SUSPICIOUS VALUES")
        print("-" * 78)

        distribution_rows = []

        for column in [
            "status",
            "borough",
            "agency",
            "complaint_type",
            "open_data_channel_type",
        ]:
            values = (
                df
                .groupBy(column)
                .count()
                .orderBy(F.desc("count"))
                .limit(20)
                .collect()
            )

            for row in values:
                distribution_rows.append(
                    {
                        "column_name": column,
                        "value": row[column],
                        "count": row["count"],
                    }
                )

            print(f"Top values captured for: {column}")

        write_csv(
            REPORT_DIR / "311_top_distributions.csv",
            distribution_rows,
            [
                "column_name",
                "value",
                "count",
            ],
        )

        print()
        print("8. FINAL SUMMARY")
        print("-" * 78)

        summary = {
            "run_id": run_id,
            "source": "nyc_311",
            "profile_year": 2025,
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "raw_file_count": len(files),
            "row_count": row_count,
            "expected_row_count": EXPECTED_ROWS,
            "row_count_match": row_count == EXPECTED_ROWS,
            "column_count": len(columns),
            "columns": columns,
            "created_min": str(date_metrics["created_min"]),
            "created_max": str(date_metrics["created_max"]),
            "closed_min": str(date_metrics["closed_min"]),
            "closed_max": str(date_metrics["closed_max"]),
            "schema_difference_months_vs_january": schema_differences,
            "duplicate_unique_key_rows": duplicate_unique_key_rows,
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
            REPORT_DIR / "311_profile_summary.json",
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(summary, file, indent=2)

        print(f"Rows profiled: {row_count:,}")
        print(f"Columns profiled: {len(columns)}")
        print(f"Duplicate unique-key rows: {duplicate_unique_key_rows:,}")
        print(
            f"Schema differences vs January: "
            f"{len(schema_differences)} month(s)"
        )
        print(f"Reports: {REPORT_DIR}")
        print()
        print("NYC 311 DATA PROFILING SUCCESS")

    finally:
        spark.stop()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print()
        print("NYC 311 DATA PROFILING FAILED")
        print(f"Error: {exc}")
        sys.exit(1)
