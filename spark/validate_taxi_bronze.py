import argparse
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.functions import col


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Validate 2025 Yellow Taxi Bronze monthly datasets."
    )
    parser.add_argument(
        "--months",
        type=int,
        nargs="+",
        choices=range(1, 13),
        default=[1],
        help="Months to validate. Example: --months 1 2 3",
    )
    return parser.parse_args()


def spark_uri(path: Path) -> str:
    return "file:///" + path.resolve().as_posix()


def validate_month(spark, month: int):
    bronze_month = (
        PROJECT_ROOT
        / "data"
        / "bronze"
        / "taxi"
        / "year=2025"
        / f"month={month:02d}"
    )

    parquet_files = sorted(
        bronze_month.glob("part-*.parquet")
    )

    if not parquet_files:
        raise FileNotFoundError(
            f"No Bronze files found in {bronze_month}"
        )

    paths = [
        spark_uri(path)
        for path in parquet_files
    ]

    df = spark.read.parquet(*paths)

    print("=" * 70)
    print(f"TAXI BRONZE VALIDATION - 2025-{month:02d}")
    print("=" * 70)

    row_count = df.count()

    print(f"ROW COUNT: {row_count:,}")

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

    if missing_metadata:
        raise RuntimeError(
            "Missing required metadata columns: "
            + ", ".join(missing_metadata)
        )

    null_counts = {}

    for column in required_metadata:
        null_counts[column] = (
            df.filter(col(column).isNull()).count()
        )

    metadata_values = (
        df.select(
            "_source",
            "_processing_year",
            "_processing_month",
        )
        .distinct()
        .collect()
    )

    expected_metadata = {
        ("yellow_taxi", 2025, month)
    }

    actual_metadata = {
        (
            row["_source"],
            row["_processing_year"],
            row["_processing_month"],
        )
        for row in metadata_values
    }

    validation_errors = []

    if row_count <= 0:
        validation_errors.append(
            "Bronze dataset contains zero rows."
        )

    for column, count in null_counts.items():
        if count != 0:
            validation_errors.append(
                f"{column} contains {count:,} null values."
            )

    if actual_metadata != expected_metadata:
        validation_errors.append(
            "Unexpected processing metadata. "
            f"Expected {expected_metadata}, "
            f"found {actual_metadata}."
        )

    if validation_errors:
        raise RuntimeError(
            "\n".join(validation_errors)
        )

    print(
        f"TAXI BRONZE VALIDATION SUCCESS - 2025-{month:02d}"
    )


def main():
    args = parse_args()

    spark = (
        SparkSession.builder
        .appName("Validate-Taxi-Bronze")
        .master("local[*]")
        .config("spark.driver.memory", "4g")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    try:
        for month in args.months:
            validate_month(
                spark,
                month,
            )
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
