import sys
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.functions import input_file_name


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_TAXI_ROOT = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "taxi"
    / "year=2025"
)


# ---------------------------------------------------------
# Spark
# ---------------------------------------------------------

def create_spark():

    return (
        SparkSession.builder
        .appName("NYC-Taxi-Schema-Inspection")
        .master("local[*]")
        .config(
            "spark.sql.shuffle.partitions",
            "8",
        )
        .config(
            "spark.driver.memory",
            "4g",
        )
        .getOrCreate()
    )


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():

    spark = create_spark()

    spark.sparkContext.setLogLevel(
        "WARN"
    )

    try:

        january_file = (
    RAW_TAXI_ROOT
    / "month=01"
    / "yellow_tripdata_2025-01.parquet"
)

        if not january_file.exists():
            raise FileNotFoundError(
        f"Taxi file not found: {january_file}"
        )

        january_path = "file:///" + january_file.resolve().as_posix()

        print("=" * 70)
        print("PHASE 5 - PYSPARK TAXI INSPECTION")
        print("=" * 70)

        print(
            f"Reading: {january_path}"
        )

        taxi_df = (
            spark.read
            .parquet(january_path)
            .withColumn(
                "_source_file",
                input_file_name(),
            )
        )

        print()
        print("SCHEMA")
        print("-" * 70)

        taxi_df.printSchema()

        print()
        print("COLUMN COUNT")
        print("-" * 70)

        print(
            len(taxi_df.columns)
        )

        print()
        print("COLUMNS")
        print("-" * 70)

        for column in taxi_df.columns:
            print(column)

        print()
        print("JANUARY ROW COUNT")
        print("-" * 70)

        row_count = taxi_df.count()

        print(
            f"{row_count:,}"
        )

        print()
        print("SAMPLE")
        print("-" * 70)

        taxi_df.show(
            5,
            truncate=False,
        )

        print()
        print(
            "PYSPARK TAXI INSPECTION SUCCESS"
        )

    finally:

        spark.stop()


if __name__ == "__main__":
    main()