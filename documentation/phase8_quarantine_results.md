# Phase 8 — Quarantine Execution Results

## Status

COMPLETE

## Objective

Implement an auditable Quarantine layer in which rejected records are retained rather than silently deleted.

Each rejection event stores:

- `source`
- `reason_code`
- `reason_description`
- `run_id`
- `rejected_at`
- `original_record`

The implementation also stores `rule_id` and `severity`.

## Execution Results

### Weather and Taxi Zones

Run ID:

`e9d9c118-8e85-4056-8ba4-72b8d60ab6d4`

Result:

- Weather quarantine events: 0
- Taxi Zone quarantine events: 0
- Status: SUCCESS

Interpretation:

Weather passed schema, timestamp-completeness, duplicate, and physical-range controls. Taxi Zones passed schema, LocationID uniqueness, and zone-name completeness controls. Zero quarantine events therefore means the controls executed successfully and found no record-level rejection conditions.

### NYC 311

Run ID:

`7b4233cf-e696-48db-a09a-a260e88dd70b`

Result:

| Rule | Reason code | Rejection events |
|---|---|---:|
| DQ_311_003 | INVALID_311_DURATION | 914 |
| DQ_311_005 | MISSING_311_COORDINATES | 50,148 |
| **Total** |  | **51,062** |

Distinct rejected original records:

`50,979`

Because 51,062 rejection events correspond to 50,979 distinct source records, 83 complaints violated both active rejection rules.

This is intentional. The Quarantine grain is one row per record-rule failure so that no rejection reason is lost when one record violates multiple rules.

All required Quarantine fields contained zero null values.

### Yellow Taxi

Run ID:

`c036197a-e50f-45d4-b385-b0b55d84c587`

Result:

| Rule | Reason code | Rejection events |
|---|---|---:|
| DQ_TAXI_003 | INVALID_TRIP_DURATION | 2,235 |
| DQ_TAXI_004 | INVALID_PICKUP_DATE | 29 |
| DQ_TAXI_006 | DUPLICATE_TAXI_RECORD | 1 |
| **Total** |  | **2,265** |

Distinct rejected original records:

`2,265`

No Taxi record in this execution violated more than one active quarantine rule.

The Taxi result exactly matched the Phase 6 profiling expectation of 2,265 rejection events.

All required Quarantine fields contained zero null values.

## Cross-Source Reconciliation

Across the executed Phase 8 runs:

- Yellow Taxi rejection events: 2,265
- NYC 311 rejection events: 51,062
- Weather rejection events: 0
- Taxi Zone rejection events: 0
- **Total rejection events: 53,327**

Distinct rejected source records across Taxi and 311:

- Yellow Taxi: 2,265
- NYC 311: 50,979
- **Total distinct rejected records: 53,244**

The event count is larger than the distinct-record count because 83 NYC 311 records violated two rules.

## Why Candidate Taxi Anomalies Were Not Quarantined

Phase 7 classified suspicious but not proven-invalid Taxi values such as negative fares, extreme fares, long distances, and long durations as `Flag and Retain`.

For example, Phase 6 found 2,848,620 records with negative `fare_amount`. Profiling alone did not establish that all such values were erroneous. Quarantining them would therefore be an unjustified mass deletion from downstream analysis.

Phase 8 applies only rules whose action is Quarantine (or a pipeline-control failure), preserving consistency between the rule catalog and execution.

## Why Schema Failures and Weather Gaps Fail the Run

A schema mismatch or missing Weather hour is not simply a bad source row.

A missing required column can make row-level validation impossible, while an absent Weather hour has no physical source record to quarantine.

These conditions therefore stop downstream publication rather than fabricating a quarantine row for data that does not exist.

## Auditability

The Quarantine data is partitioned by run ID and source.

Every rejected event retains the original record presented to the validation stage together with the rule and reason metadata.

This supports:

- rule-level monitoring;
- rejected-record investigation;
- reconciliation;
- reproducibility;
- supervisor/auditor explanation.

## Validation

The automated Quarantine contract test suite passed after real Quarantine files were created:

`5 passed`

The tests verify the reason-code dictionary and required Quarantine schema.

## Phase 8 Result

Phase 8 is COMPLETE.

The project now has:

- a controlled reason-code dictionary;
- executable Data Quality rejection logic;
- auditable Quarantine Parquet output;
- preserved original rejected records;
- run IDs and rejection timestamps;
- rule-level rejection reasons;
- cross-phase reconciliation against Phase 6 profiling;
- automated contract tests.

No rejected record is silently deleted.
