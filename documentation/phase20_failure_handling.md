# Phase 20 — Failure Handling

## Status

PHASE 20 COMPLETE

## Objective

Phase 20 hardens the NYC Urban Intelligence Platform against operational,
data-quality, transformation, publication, and warehouse failures.

The required design principle is fail-safe execution:

Failure
→ mark task failed
→ log the error
→ stop downstream execution
→ preserve previously valid data
→ never publish incomplete Gold data

## Failure Scenarios Covered

The following required failure scenarios were deliberately tested:

1. File unavailable
2. API unavailable
3. Invalid schema
4. Empty dataset
5. SQL connection failure
6. Transformation failure
7. Unexpected row count

All seven scenarios passed their failure-handling tests.

## Airflow Failure Propagation

The Airflow DAG uses sequential dependencies:

Ingestion
→ Bronze
→ Validation
→ Silver
→ Gold
→ Azure SQL Warehouse
→ Post-load Tests

Bash tasks use:

`set -euo pipefail`

Therefore a non-zero ETL exit code causes the Airflow task to fail.

Because downstream tasks use normal success dependencies, a failed upstream
task prevents later publication stages from running.

Azure SQL loading and post-load validation also use retry protection for
temporary infrastructure failures.

## File Unavailable Test

Test:

The January Weather Silver directory was temporarily renamed so that the
Gold builder could not find the required input.

Observed error:

`Weather Silver month not found`

Result:

- FileNotFoundError raised
- Gold build marked FAILED
- No replacement Gold published
- No staging directory remained
- No backup directory remained
- Weather Silver directory restored after test

Status: PASS

## API Unavailable Test

Controlled failpoint:

`NYC_PHASE20_FAILPOINT=weather_api_unavailable`

The Weather acquisition pipeline simulated an unavailable external API.

Result:

- Connection exception raised
- Process returned non-zero
- Manifest recorded FAILED
- Pipeline log recorded FAILED
- Existing Raw Weather file remained unchanged
- No `.part` file remained

Status: PASS

## Invalid Schema Test

Controlled failpoint:

`NYC_PHASE20_FAILPOINT=weather_invalid_schema`

The Weather acquisition pipeline simulated an invalid API schema.

Result:

- Invalid payload rejected
- Process returned non-zero
- Manifest recorded FAILED
- Pipeline log recorded FAILED
- Existing valid Raw Weather file remained unchanged

Status: PASS

## Empty Dataset Test

Controlled failpoint:

`NYC_PHASE20_FAILPOINT=weather_empty_dataset`

The Weather acquisition pipeline simulated a zero-row API response.

Result:

- Empty dataset rejected
- Process returned non-zero
- Manifest recorded FAILED
- Pipeline log recorded FAILED
- Existing valid Raw Weather file remained unchanged

Status: PASS

## SQL Connection Failure Test

The Airflow `load_sql_warehouse` task was tested using a deliberately invalid
SQL endpoint.

Observed ODBC failure:

`HYT00 - Login timeout expired`

Result:

- Azure SQL loader returned non-zero
- BashOperator failed
- Airflow marked the task failed/up-for-retry
- Downstream post-load publication could not proceed

A separate test also verified that a missing `nyc_azure_sql` Airflow
connection fails during connection-template resolution rather than silently
continuing.

Status: PASS

## Transformation Failure Test

Controlled failpoint:

`NYC_PHASE20_FAILPOINT=gold_before_publish`

The Gold dataset was completely built into staging and then deliberately
failed immediately before publication.

The previously published January Gold Parquet SHA256 was captured before
and after the test.

Result:

- Transformation/publication failed deliberately
- Gold run log recorded FAILED
- Existing January Gold hash remained identical
- No staging directory remained
- No backup directory remained
- No incomplete Gold was exposed

Status: PASS

## Unexpected Row Count Test

Controlled failpoint:

`NYC_PHASE20_FAILPOINT=gold_unexpected_row_count`

The failpoint removes one row immediately before the existing Gold row-count
contract.

January expected rows:

195,672

Injected result:

195,671

Observed error:

`GOLD_ROW_FAILURE 2025-01: expected 195,672, found 195,671`

Result:

- Row-count contract rejected the dataset
- Process returned non-zero
- Gold run log recorded FAILED
- Existing published January Gold remained byte-for-byte unchanged
- Incomplete Gold was not published

Status: PASS

## Atomic Gold Publication

Before Phase 20, the Gold writer removed the published monthly directory
before writing its replacement.

That behavior created a failure window where a write failure could remove a
previously valid Gold partition.

Phase 20 replaces this with staged publication:

1. Build Gold in memory
2. Write replacement into a staging directory
3. Verify staged Parquet row count
4. Keep existing published Gold untouched during staging
5. Move existing Gold to a temporary backup only after successful staging
6. Promote staged directory to the published path
7. Remove backup only after successful publication
8. Restore previous Gold automatically if promotion fails
9. Remove incomplete staging data on failure

This guarantees that failed publication does not replace a previously valid
Gold partition with incomplete data.

## Weather Raw Publication Protection

Weather acquisition already uses a temporary `.part` file.

The external response is validated before publication.

Only a validated response is promoted to the Raw destination.

On failure:

- `.part` file is deleted
- Manifest receives FAILED
- Pipeline log receives FAILED
- Existing valid Raw data remains untouched

## Failure Logging

Failure evidence is recorded through existing logging mechanisms including:

`logs/pipeline_runs.jsonl`

and acquisition manifests such as:

`reports/acquisition/weather_download_manifest.csv`

Failure records include status and error messages so operational errors are
not silent.

## Controlled Failure Injection

Phase 20 adds environment-controlled failpoints used only for deliberate
testing:

- `weather_api_unavailable`
- `weather_invalid_schema`
- `weather_empty_dataset`
- `gold_before_publish`
- `gold_unexpected_row_count`

Without `NYC_PHASE20_FAILPOINT`, normal production behavior is unchanged.

## Final Result

Phase 20 verifies that the NYC Urban Intelligence Platform fails safely.

Required failure conditions produce non-zero task results, errors are logged,
Airflow prevents downstream execution, existing trusted data is preserved,
and incomplete Gold data is never published.
