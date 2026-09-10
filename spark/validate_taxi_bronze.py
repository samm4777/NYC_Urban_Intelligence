from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.functions import col


PROJECT_ROOT = Path(__file__).resolve().parents[1]

BRONZE_MONTH = (
    PROJECT_ROOT
    / "data"
    / "bronze"
    / "taxi"
    / "year=2025"
    / "month=01"
)


def spark_uri(path: Path) -> str:
    return "file:///" + path.resolve().as_posix()


spark = (
    SparkSession.builder
    .appName("Validate-Taxi-Bronze")
    .master("local[*]")
    .config("spark.driver.memory", "4g")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")

try:
    parquet_files = sorted(
        BRONZE_MONTH.glob("part-*.parquet")
    )

    if not parquet_files:
        raise FileNotFoundError(
            f"No Bronze files found in {BRONZE_MONTH}"
        )

    paths = [
        spark_uri(path)
        for path in parquet_files
    ]

    df = spark.read.parquet(*paths)

    print("=" * 70)
    print("JANUARY TAXI BRONZE VALIDATION")
    print("=" * 70)

    print()
    print("BRONZE SCHEMA")
    df.printSchema()

    print()
    print("COLUMN COUNT")
    print(len(df.columns))

    row_count = df.count()

    print()
    print("ROW COUNT")
    print(f"{row_count:,}")

    required_metadata = [
        "_source",
        "_source_file",
        "_ingested_at",
        "_run_id",
        "_processing_year",
        "_processing_month",
    ]

    missing_metadata = [
        column
        for column in required_metadata
        if column not in df.columns
    ]

    print()
    print("REQUIRED METADATA COLUMNS")

    if missing_metadata:
        print(
            "MISSING:",
            ", ".join(missing_metadata),
        )
    else:
        print("ALL PRESENT")

    print()
    print("METADATA VALUES")

    df.select(
        "_source",
        "_processing_year",
        "_processing_month",
    ).distinct().show(
        truncate=False
    )

    null_conditions = [
        col(column).isNull()
        for column in required_metadata
    ]

    null_counts = []

    for column in required_metadata:
        count = df.filter(
            col(column).isNull()
        ).count()

        null_counts.append(
            (column, count)
        )

    print()
    print("METADATA NULL COUNTS")

    for column, count in null_counts:
        print(
            f"{column}: {count:,}"
        )

    valid = (
        row_count == 3_475_226
        and not missing_metadata
        and all(
            count == 0
            for _, count in null_counts
        )
    )

    print()
    print("=" * 70)

    if valid:
        print(
            "JANUARY TAXI BRONZE VALIDATION SUCCESS"
        )
    else:
        raise RuntimeError(
            "January Bronze validation failed."
        )

finally:
    spark.stop()