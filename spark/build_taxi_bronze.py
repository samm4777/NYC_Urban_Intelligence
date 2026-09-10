import argparse
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.functions import input_file_name, lit
from pyspark.sql.types import (
    BooleanType, ByteType, DateType, DecimalType, DoubleType, FloatType,
    IntegerType, LongType, ShortType, StringType, TimestampNTZType, TimestampType,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_TAXI_ROOT = PROJECT_ROOT / "data" / "raw" / "taxi" / "year=2025"
BRONZE_TAXI_ROOT = PROJECT_ROOT / "data" / "bronze" / "taxi" / "year=2025"
RUN_LOG = PROJECT_ROOT / "logs" / "pipeline_runs.jsonl"


def spark_uri(path: Path) -> str:
    return "file:///" + path.resolve().as_posix()


def create_spark():
    return (
        SparkSession.builder
        .appName("NYC-Taxi-Bronze")
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.driver.memory", "4g")
        .getOrCreate()
    )


def write_metric(metric: dict):
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(RUN_LOG, "a", encoding="utf-8") as file:
        file.write(json.dumps(metric, default=str) + "\n")


def spark_type_to_arrow(data_type):
    import pyarrow as pa
    if isinstance(data_type, ByteType): return pa.int8()
    if isinstance(data_type, ShortType): return pa.int16()
    if isinstance(data_type, IntegerType): return pa.int32()
    if isinstance(data_type, LongType): return pa.int64()
    if isinstance(data_type, FloatType): return pa.float32()
    if isinstance(data_type, DoubleType): return pa.float64()
    if isinstance(data_type, StringType): return pa.string()
    if isinstance(data_type, BooleanType): return pa.bool_()
    if isinstance(data_type, DateType): return pa.date32()
    if isinstance(data_type, (TimestampType, TimestampNTZType)): return pa.timestamp("us")
    if isinstance(data_type, DecimalType): return pa.decimal128(data_type.precision, data_type.scale)
    raise TypeError(f"Unsupported Spark type for portable Parquet writer: {data_type}")


def build_arrow_schema(spark_schema):
    import pyarrow as pa
    return pa.schema([
        pa.field(field.name, spark_type_to_arrow(field.dataType), nullable=field.nullable)
        for field in spark_schema.fields
    ])


def write_parquet_windows_fallback(dataframe, output_directory: Path, run_id: str, batch_size: int = 50000):
    import pyarrow as pa
    import pyarrow.parquet as pq

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

        partition_schema = worker_pa.ipc.read_schema(worker_pa.BufferReader(serialized_schema))
        file_path = WorkerPath(output_dir_text) / f"part-{partition_index:05d}-{run_tag}.parquet"
        writer = None
        buffer = []
        row_count = 0
        try:
            for row in rows:
                buffer.append(row.asDict(recursive=False))
                if len(buffer) >= batch_size:
                    table = worker_pa.Table.from_pylist(buffer, schema=partition_schema)
                    if writer is None:
                        writer = worker_pq.ParquetWriter(str(file_path), partition_schema, compression="snappy")
                    writer.write_table(table)
                    row_count += len(buffer)
                    buffer.clear()
            if buffer:
                table = worker_pa.Table.from_pylist(buffer, schema=partition_schema)
                if writer is None:
                    writer = worker_pq.ParquetWriter(str(file_path), partition_schema, compression="snappy")
                writer.write_table(table)
                row_count += len(buffer)
        finally:
            if writer is not None:
                writer.close()
        yield row_count

    partition_counts = dataframe.rdd.mapPartitionsWithIndex(write_partition).collect()
    rows_written_by_workers = sum(partition_counts)
    parquet_files = sorted(output_directory.glob("part-*.parquet"))
    rows_verified_from_files = sum(pq.ParquetFile(str(file)).metadata.num_rows for file in parquet_files)
    return rows_written_by_workers, rows_verified_from_files, len(parquet_files)


def write_bronze(dataframe, output_directory: Path, run_id: str):
    if os.name == "nt":
        print("Writer: Windows portable Parquet adapter (PySpark processing + PyArrow filesystem persistence)")
        return write_parquet_windows_fallback(dataframe, output_directory, run_id)

    print("Writer: Native Spark DataFrameWriter")
    dataframe.write.mode("overwrite").parquet(spark_uri(output_directory))
    import pyarrow.parquet as pq
    written_files = sorted(output_directory.glob("part-*.parquet"))
    verified_rows = sum(pq.ParquetFile(str(file)).metadata.num_rows for file in written_files)
    return verified_rows, verified_rows, len(written_files)


def process_month(spark, month: int):
    month_text = f"{month:02d}"
    source_file = RAW_TAXI_ROOT / f"month={month_text}" / f"yellow_tripdata_2025-{month_text}.parquet"
    output_directory = BRONZE_TAXI_ROOT / f"month={month_text}"
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    metric = {
        "run_id": run_id,
        "source": "yellow_taxi",
        "processing_month": f"2025-{month_text}",
        "stage": "bronze",
        "started_at": started_at.isoformat(),
        "finished_at": None,
        "rows_read": 0,
        "rows_valid": 0,
        "rows_rejected": 0,
        "status": "RUNNING",
        "error_message": None,
    }

    try:
        if not source_file.exists():
            raise FileNotFoundError(f"Source file not found: {source_file}")

        print("\n" + "=" * 70)
        print(f"BUILDING TAXI BRONZE - 2025-{month_text}")
        print("=" * 70)
        print(f"Source: {source_file}")
        print(f"Output: {output_directory}")
        print(f"Run ID: {run_id}")

        raw_df = spark.read.parquet(spark_uri(source_file))
        rows_read = raw_df.count()
        metric["rows_read"] = rows_read
        print(f"Rows read: {rows_read:,}")

        ingestion_timestamp = datetime.now(timezone.utc)
        bronze_df = (
            raw_df
            .withColumn("_source", lit("yellow_taxi"))
            .withColumn("_source_file", input_file_name())
            .withColumn("_ingested_at", lit(ingestion_timestamp).cast("timestamp"))
            .withColumn("_run_id", lit(run_id))
            .withColumn("_processing_year", lit(2025))
            .withColumn("_processing_month", lit(month))
        )

        print(f"Spark partitions: {bronze_df.rdd.getNumPartitions()}")
        worker_rows, bronze_rows, output_file_count = write_bronze(bronze_df, output_directory, run_id)

        print("Bronze write complete.")
        print(f"Worker rows: {worker_rows:,}")
        print(f"Bronze rows: {bronze_rows:,}")
        print(f"Bronze Parquet files: {output_file_count}")

        if worker_rows != rows_read:
            raise RuntimeError(f"Worker row reconciliation failed: Raw={rows_read:,}, Worker={worker_rows:,}")
        if bronze_rows != rows_read:
            raise RuntimeError(f"Bronze file reconciliation failed: Raw={rows_read:,}, Bronze={bronze_rows:,}")

        metric.update({
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "rows_valid": bronze_rows,
            "rows_rejected": 0,
            "status": "SUCCESS",
            "error_message": None,
        })
        write_metric(metric)
        print("Reconciliation: SUCCESS")
        print(f"2025-{month_text}: BRONZE SUCCESS")
        return rows_read

    except Exception as exc:
        metric.update({
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": "FAILED",
            "error_message": str(exc),
        })
        write_metric(metric)
        print(f"2025-{month_text}: BRONZE FAILED")
        print(f"Error: {exc}")
        raise


def parse_arguments():
    parser = argparse.ArgumentParser(description="Build Yellow Taxi Bronze datasets using PySpark.")
    parser.add_argument("--months", nargs="+", type=int, default=list(range(1, 13)), help="Months to process. Example: --months 1 2 3")
    return parser.parse_args()


def main():
    args = parse_arguments()
    invalid_months = [month for month in args.months if month < 1 or month > 12]
    if invalid_months:
        raise ValueError(f"Invalid months: {invalid_months}")

    spark = create_spark()
    spark.sparkContext.setLogLevel("WARN")
    total_rows = 0
    try:
        for month in args.months:
            total_rows += process_month(spark, month)
        print("\n" + "=" * 70)
        print("TAXI BRONZE PROCESSING SUMMARY")
        print("=" * 70)
        print(f"Months processed: {len(args.months)}")
        print(f"Total rows: {total_rows:,}")
        print("\nTAXI BRONZE JOB SUCCESS")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
