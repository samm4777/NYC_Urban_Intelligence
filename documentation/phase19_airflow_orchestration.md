# Phase 19 — Apache Airflow Orchestration

## Status

PHASE 19 COMPLETE

## Purpose

Phase 19 introduces Apache Airflow as the orchestration layer for the
NYC Urban Intelligence Platform.

Airflow coordinates the existing ETL components rather than duplicating
transformation logic inside the DAG.

## Implemented Architecture

The implemented pipeline is:

Ingestion
→ Bronze
→ Validation
→ Silver
→ Gold
→ Azure SQL Warehouse
→ Post-load Tests

Gold remains the business-ready analytical data-lake layer.

Azure SQL is the serving warehouse populated from Gold and used by
downstream reporting and analytical workloads.

## DAG

DAG ID:

`nyc_urban_intelligence_pipeline`

DAG file:

`dags/nyc_urban_intelligence_dag.py`

The DAG uses manual execution with configurable:

- `start_month`
- `end_month`

Both parameters accept values from 1 through 12.

The default configuration processes January only so that accidental
full-year execution is avoided.

## Airflow Tasks

1. `ingest_sources`
2. `build_bronze`
3. `validate_bronze`
4. `build_silver`
5. `build_gold`
6. `load_sql_warehouse`
7. `run_post_load_tests`

Dependencies are strictly sequential.

## Runtime Separation

Airflow runtime:

`~/airflow-nyc/.venv`

ETL runtime:

`~/nyc-runtime/.venv`

This separates orchestration dependencies from the data-processing
runtime containing PySpark, pandas, PyArrow, GeoPandas, Shapely and
pyodbc.

## Spark Runtime

WSL2 Ubuntu 24.04 is used for orchestration and ETL execution.

Java:

OpenJDK 17

PySpark:

4.2.0

## Azure SQL Connectivity

Microsoft ODBC Driver 18 for SQL Server is installed in WSL.

Azure SQL credentials are not stored in source code.

Airflow connection:

`nyc_azure_sql`

The connection supplies:

- Server
- Database
- Username
- Password

The password is injected into task execution at runtime through the
`NYC_AZURE_SQL_PASSWORD` environment variable.

Manual executions retain the secure `getpass` fallback.

## Bronze Validation Improvement

The original Taxi Bronze validator was January-specific.

Phase 19 converted the validator into a month-parameterized component
supporting:

`--months 1 2 3 ...`

Validation now checks:

- Bronze files exist
- Dataset contains rows
- Required metadata columns exist
- Required metadata values are non-null
- Source/year/month metadata matches the requested month

The previous hard-coded January row-count dependency was removed.

## Incremental Warehouse Loading

The DAG invokes:

`python/load_gold_incremental_logged.py`

Existing Phase 16/17 idempotency controls remain authoritative.

A Phase 19 test against January 2025 returned:

- Registry status: SUCCESS
- Action: SKIP — file version already processed
- Processed: 0
- Skipped: 1
- Status: SUCCESS

This demonstrated that Airflow orchestration does not duplicate an
already processed warehouse load.

## Post-load Validation

Phase 19 adds:

`python/validate_phase19_warehouse.py`

The validation checks:

- No incomplete processed-file registrations
- Requested month has a SUCCESS registry entry
- Gold fact business grain remains unique
- ETL reconciliation equations are valid
- Completed ETL runs have end times
- No stale STARTED ETL executions remain

January test results:

- Fact rows: 2,303,880
- Distinct grain rows: 2,303,880
- ETL reconciliation violations: 0
- Completed runs missing end_time: 0
- Stale STARTED executions: 0
- Result: SUCCESS

## Azure Transient Failure Handling

During testing Azure SQL temporarily returned error 40613 indicating
that the database was not currently available.

A retry succeeded without code or data changes.

The warehouse load and post-load validation Airflow tasks therefore
include retry protection for transient Azure availability conditions.

## Security

No Azure SQL password is committed to Git.

Secrets remain in the Airflow connection metadata and are supplied only
at task runtime.

Raw data remains immutable.

## Phase 19 Result

Airflow successfully orchestrates the existing NYC Urban Intelligence
pipeline architecture and securely integrates with the Azure SQL
warehouse while retaining incremental loading, duplicate prevention,
ETL logging and post-load validation controls established in earlier
phases.
