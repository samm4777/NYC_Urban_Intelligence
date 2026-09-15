# Phase 40 — Automated Testing

## Overview

Phase 40 finalizes the automated testing layer for the NYC Urban Intelligence Platform.

The automated test suite validates the production Azure SQL warehouse after load and is designed to fail the pipeline when critical warehouse-quality checks do not pass.

The Phase 40 implementation uses:

- `pytest`
- `pyodbc`
- Azure SQL validation queries
- Airflow post-load orchestration

Primary test file:

`tests/test_warehouse_quality.py`

Airflow DAG:

`dags/nyc_urban_intelligence_dag.py`

---

## 1. Test Scope

The automated suite covers the required Phase 40 categories:

| Requirement | Automated Coverage |
|---|---|
| Duplicate keys | Gold business key and surrogate key checks |
| Null required fields | Required Gold warehouse columns |
| Invalid dates | Gold dates constrained to calendar year 2025 |
| Missing relationships | Gold-to-dimension relationship checks |
| Unexpected row counts | Gold and prediction control counts |
| Invalid values | Structurally impossible negative measures |
| Referential integrity | Prediction fact to Date, Time, and Zone dimensions |

---

## 2. Automated Tests Implemented

A total of 11 automated tests are implemented.

### Duplicate Key Tests

1. `test_no_duplicate_zone_hourly_business_keys`

Validates uniqueness of the Gold business grain:

`date_key + time_key + zone_key`

Expected duplicate groups:

`0`

2. `test_no_duplicate_zone_hourly_surrogate_keys`

Validates uniqueness of:

`zone_hourly_key`

Expected duplicates:

`0`

---

### Required Field Test

3. `test_zone_hourly_required_fields_not_null`

Checks required fields in:

`dw.FactZoneHourlyActivity`

Required fields include:

- `date_key`
- `time_key`
- `zone_key`
- `weather_condition_key`
- `taxi_trips`
- `taxi_revenue`
- `complaints_311`
- `temperature_c`
- `rain_mm`
- `snowfall_cm`

Expected invalid rows:

`0`

---

### Date Validation Test

4. `test_zone_hourly_dates_are_in_2025`

Validates that Gold activity rows resolve to dates within:

`2025-01-01 <= full_date < 2026-01-01`

Expected invalid rows:

`0`

---

### Missing Relationship Test

5. `test_zone_hourly_dimension_relationships_complete`

Validates that every Gold activity row resolves to valid members in:

- `dw.DimDate`
- `dw.DimTime`
- `dw.DimZone`
- `dw.DimWeatherCondition`

Expected missing relationships:

`0`

---

### Row Count and Control Total Tests

6. `test_full_year_gold_row_count`

Expected Gold grain:

`263 Taxi Zones × 8,760 hours`

Expected rows:

`2,303,880`

7. `test_full_year_taxi_trip_control_total`

Expected Taxi trips represented in Gold:

`48,617,295`

8. `test_full_year_complaint_control_total`

Expected 311 complaints represented in Gold:

`3,603,396`

---

### Invalid Value Test

9. `test_no_invalid_gold_measure_values`

Checks for structurally invalid values such as:

- `taxi_trips < 0`
- `complaints_311 < 0`
- `rain_mm < 0`
- `snowfall_cm < 0`
- negative non-null `average_trip_distance`

Expected invalid rows:

`0`

Negative `taxi_revenue` and negative `average_fare` are intentionally not treated as hard failures in this test because the established Phase 7 data-quality rules classify negative Taxi monetary values as candidate anomalies that are flagged and retained rather than automatically quarantined.

This distinction prevents the automated test suite from contradicting the project's established data-quality policy.

---

### Prediction Referential Integrity Tests

10. `test_prediction_dimension_referential_integrity`

Validates that every row in:

`dw.FactDemandPrediction`

resolves to valid:

- Date
- Time
- Zone

dimension members.

Expected orphan rows:

`0`

11. `test_prediction_row_count`

Expected prediction rows:

`385,032`

This corresponds to:

`61 forecast dates × 24 hours × 263 Taxi Zones`

for November–December 2025.

---

## 3. Test Execution Result

The final warehouse suite was executed with:

```powershell
python -m pytest tests/test_warehouse_quality.py -v
```

Final result:

```text
11 passed in 4.71s
```

All automated warehouse assertions passed.

---

## 4. Issue Found During Test Development

The initial invalid-value test treated negative Taxi revenue and negative average fare as automatically invalid.

That test returned:

`35,930`

Gold rows matching the overly strict condition.

Investigation confirmed that this was a test-design issue rather than a warehouse defect.

The established Phase 7 rules intentionally classify negative Taxi monetary values as candidate anomalies to be flagged and retained. Therefore those conditions were removed from the hard-failure assertion.

After aligning the test with the documented data-quality policy, the full suite passed.

---

## 5. Azure SQL Connection Handling

The pytest suite reads Azure SQL connection information from environment variables:

- `NYC_AZURE_SQL_SERVER`
- `NYC_AZURE_SQL_DATABASE`
- `NYC_AZURE_SQL_USER`
- `NYC_AZURE_SQL_PASSWORD`

No database password is stored in the repository.

The test connection includes retry handling for transient Azure SQL connectivity delays.

---

## 6. Airflow Integration

The Phase 40 pytest suite has been added as the final automated gate in:

`dags/nyc_urban_intelligence_dag.py`

The pipeline sequence is now:

```text
Ingestion
→ Bronze
→ Validation
→ Silver
→ Gold
→ SQL Warehouse
→ Post-load Tests
→ Phase 40 Pytest Gate
```

The new Airflow task is:

`run_phase40_pytest`

It executes:

```bash
python -m pytest tests/test_warehouse_quality.py -q
```

using the same Azure SQL environment variables supplied through the Airflow connection.

Because the task is downstream of the existing warehouse post-load validation, any failing pytest assertion prevents the automated quality gate from completing successfully.

---

## 7. DAG Validation

The updated DAG passed Python syntax validation using:

```powershell
python -m py_compile dags\nyc_urban_intelligence_dag.py
```

The Phase 40 task definition and dependency were also statically verified in the DAG:

- `run_phase40_pytest = BashOperator(...)`
- `>> run_phase40_pytest`

Apache Airflow itself is not installed in the current office Windows virtual environment. The local `airflow` import on that machine resolves to the project's `airflow/` directory rather than the Apache Airflow package.

Therefore the updated DAG was syntax-validated on the office machine, while execution of the Airflow runtime remains associated with the project's established Airflow environment.

---

## 8. Phase 40 Validation Summary

| Test Area | Result |
|---|---|
| Duplicate Gold business keys | PASS |
| Duplicate Gold surrogate keys | PASS |
| Required NULL fields | PASS |
| Invalid dates | PASS |
| Missing dimension relationships | PASS |
| Gold row count | PASS |
| Taxi trip control total | PASS |
| 311 complaint control total | PASS |
| Structurally invalid values | PASS |
| Prediction referential integrity | PASS |
| Prediction row count | PASS |
| Pytest suite | 11 / 11 PASS |
| DAG Python syntax | PASS |
| Phase 40 task wired into DAG | PASS |

---

## Final Status

**PHASE 40 — AUTOMATED TESTING IMPLEMENTED AND VALIDATED**

The automated warehouse test suite passes completely and the critical test suite is integrated into the Airflow DAG as the final post-load quality gate.

---

## Implementation Files

```text
tests/test_warehouse_quality.py
dags/nyc_urban_intelligence_dag.py
documentation/phase40_automated_testing.md
```
