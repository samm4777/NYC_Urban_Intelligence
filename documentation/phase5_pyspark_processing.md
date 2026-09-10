# Phase 5 — PySpark Processing

## Status

IN PROGRESS

## Objective

Taxi data must primarily use PySpark for large-scale ingestion and downstream transformation.

PySpark will be used throughout the project for:

- Full-year Taxi ingestion
- Type conversion
- Validation
- Cleaning
- Joins
- Aggregations
- Gold dataset creation

Smaller supporting datasets may use Pandas where appropriate.

## Spark Code Location

Spark processing code is stored under:

`spark/`

Current files:

- `spark/inspect_taxi.py`
- `spark/build_taxi_bronze.py`
- `spark/validate_taxi_bronze.py`

## Taxi Source Inspection

January 2025 Yellow Taxi data was successfully read with PySpark.

Result:

- Rows: 3,475,226
- Source columns: 20
- Bronze columns after metadata: 26
- Schema inspection: SUCCESS

## Bronze Metadata

The Bronze Taxi dataset includes:

- `_source`
- `_source_file`
- `_ingested_at`
- `_run_id`
- `_processing_year`
- `_processing_month`

No business cleaning is performed in Bronze.

## January Bronze Validation

January Bronze validation result:

- Raw rows: 3,475,226
- Bronze rows: 3,475,226
- Required metadata columns: all present
- Metadata null counts: 0
- Reconciliation: SUCCESS

## Full-Year Taxi Bronze

All 12 monthly 2025 Taxi files were processed.

Physical structure:

`data/bronze/taxi/year=2025/month=01/`
through
`data/bronze/taxi/year=2025/month=12/`

Total Bronze Parquet files:

48

Full-year reconciliation:

- Expected Raw Taxi rows: 48,722,602
- Bronze Taxi rows: 48,722,602
- Difference: 0
- Match: TRUE

Each monthly job emitted run metrics including:

- run_id
- source
- processing_month
- stage
- started_at
- finished_at
- rows_read
- rows_valid
- rows_rejected
- status
- error_message

All 12 monthly Bronze processing runs completed successfully.

## Windows Development Constraint

PySpark successfully performs Taxi ingestion and DataFrame processing on the current Windows development machine.

Native Spark local Parquet writing requires Hadoop Windows permission helpers that are unavailable on the managed office laptop.

Therefore:

- PySpark performs ingestion and DataFrame processing.
- PyArrow is used only as the local Windows Parquet persistence adapter.
- Native Spark DataFrameWriter remains the intended persistence path for Linux/Docker execution.

No unverified third-party Hadoop binaries were installed.

## Git Storage Rule

Generated Bronze Parquet datasets are excluded from Git.

Transformation code and documentation are committed, while runtime data remains local.

## Remaining Phase 5 Work

The following PySpark requirements will be completed during subsequent data-engineering phases:

- Type conversion
- Data validation
- Cleaning
- Taxi Zone joins
- Aggregations
- Gold creation

These operations are intentionally deferred until profiling and formal data-quality rules are established.

Phase 5 remains IN PROGRESS until those requirements are demonstrated.