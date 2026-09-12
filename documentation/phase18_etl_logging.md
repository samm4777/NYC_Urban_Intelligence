# Phase 18 — ETL Logging

## Status

**COMPLETE**

Phase 18 implements formal SQL-based ETL execution logging for the NYC
Urban Intelligence Platform.

## Logging Architecture

The formal logging table is:

`audit.ETLRunLog`

Each execution records:

- run_id
- pipeline_name
- source
- processing_month
- stage
- start_time
- end_time
- rows_processed
- rows_valid
- rows_rejected
- quarantine_rows
- status
- error_message
- optional load_batch_id

Supported execution states are:

- STARTED
- SUCCESS
- FAILED

## Logging Procedures

Three reusable SQL procedures were created:

- `etl.usp_LogETLStart`
- `etl.usp_LogETLSuccess`
- `etl.usp_LogETLFailure`

A task first writes a STARTED record.

On successful completion the same run is updated to SUCCESS.

On execution failure the same run is updated to FAILED with the captured
error message and completion timestamp.

## Reconciliation Rules

Successful ETL execution must satisfy:

`rows_processed = rows_valid + rows_rejected`

Rejected rows must also reconcile exactly with quarantine:

`rows_rejected = quarantine_rows`

These rules are enforced both by SQL constraints and by the success
logging procedure.

A run cannot be marked SUCCESS when quarantine reconciliation fails.

## Framework Tests

Three controlled tests were performed.

### Success Test

Input:

- rows_processed = 100
- rows_valid = 95
- rows_rejected = 5
- quarantine_rows = 5

Result:

`SUCCESS`

### Failure Test

A simulated ETL error was formally logged.

Input:

- rows_processed = 20
- rows_valid = 18
- rows_rejected = 2
- quarantine_rows = 2

Result:

`FAILED`

The simulated error message was preserved.

### Quarantine Guardrail Test

An invalid success attempt was made using:

- rows_processed = 100
- rows_valid = 97
- rows_rejected = 3
- quarantine_rows = 2

The framework rejected the SUCCESS transition because rejected and
quarantine counts did not reconcile.

The run was then formally closed as FAILED.

This proves that quarantine-count reconciliation is enforced.

## Production Pipeline Integration

A reusable Python logging helper was created:

`python/etl_logging.py`

A logging-enabled incremental Gold pipeline was created:

`python/load_gold_incremental_logged.py`

The wrapper integrates formal logging with the existing incremental
monthly Gold loader.

## Real SUCCESS Path

July 2025 was invoked through the logging-enabled incremental pipeline.

The source file had already been processed during Phase 16, so the
processed-file registry correctly skipped warehouse processing.

Formal ETL result:

- processing_month = 2025-07-01
- stage = INCREMENTAL_GOLD_MONTH
- rows_processed = 0
- rows_valid = 0
- rows_rejected = 0
- quarantine_rows = 0
- status = SUCCESS
- error_message = NULL

This proves that an idempotent skip is still formally logged as a
successful pipeline execution.

## Real FAILURE Path

January 2026 was deliberately invoked when no corresponding Gold
Parquet source partition existed.

The pipeline first wrote its STARTED record and then failed during
source discovery.

Formal result:

- processing_month = 2026-01-01
- stage = INCREMENTAL_GOLD_MONTH
- status = FAILED
- end_time populated
- error_message populated

No warehouse data was modified by this controlled failure test.

## Relationship to Existing Audit Framework

Phase 18 complements the existing:

- `audit.LoadBatch`
- `audit.ReconciliationResult`
- `etl.ProcessedFileRegistry`
- `etl.LoadWatermark`

`audit.LoadBatch` remains the batch-level ingestion audit.

`audit.ETLRunLog` provides formal task/stage execution logging.

## Phase 18 Assets

SQL:

- `sql/phase18/01_create_etl_logging.sql`
- `sql/phase18/02_test_etl_logging.sql`
- `sql/phase18/03_validate_etl_logging.sql`

Python:

- `python/etl_logging.py`
- `python/load_gold_incremental_logged.py`

## Result

**Phase 18 — ETL Logging: COMPLETE**

The platform now records formal task start, success and failure events,
captures execution metrics and errors, and enforces rejected-row versus
quarantine reconciliation.
