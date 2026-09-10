# Phase 8 — Quarantine Invalid Data

## Purpose

The Quarantine layer retains records rejected by record-level Data Quality rules. Rejected records are never silently deleted.

## Location

Runtime Quarantine data is written under:

`data/quarantine/run_id=<run_id>/source=<source>/`

Each source is stored as Parquet using a Windows-safe PyArrow writer after Data Quality evaluation.

## Required Record Contract

Every quarantined record contains:

- `source`
- `reason_code`
- `reason_description`
- `run_id`
- `rejected_at`
- `original_record`

The implementation additionally stores:

- `rule_id`
- `severity`

`original_record` is a JSON serialization of the record presented to the validation stage so the rejected input can be reconstructed and audited.

## Grain

The Quarantine dataset uses **one row per record-rule rejection event**.

If one input record violates two quarantine rules, two Quarantine rows are written. Both rows preserve the same original record but carry different reason codes.

This design preserves every rejection reason and supports rule-level reconciliation.

## Reason-Code Dictionary

The controlled reason-code dictionary is stored at:

`data_quality/reason_codes.csv`

It maps Data Quality `rule_id` values to:

- reason code
- source
- reason description
- severity
- action
- whether the rule is record-level

Schema mismatches and Weather gaps are included in the dictionary even though they are pipeline-control failures rather than rejected source records.

## Source Behavior

### Yellow Taxi

Taxi validation runs against the Bronze layer.

Record-level Quarantine rules include missing required timestamps, drop-off before pickup, pickup outside 2025, missing location IDs, negative trip distance, and exact duplicate source records beyond the first occurrence.

Candidate anomaly rules such as negative fares, extreme fares, extreme distances, and extreme durations are not quarantined because Phase 7 defined them as Flag-and-Retain conditions.

### NYC 311

311 validation runs against the immutable Raw JSON source until its formal Bronze/Silver preparation stage.

Record-level Quarantine rules include invalid created dates, close-before-create, duplicate unique keys beyond the first, missing coordinates, and structurally invalid coordinate ranges.

### Weather

Weather is validated for schema, complete 2025 hourly coverage, duplicate timestamps, date range, and physical measurement ranges.

Missing expected hours fail the run because no source record exists to quarantine for an absent timestamp.

### Taxi Zones

Taxi Zone schema/key controls fail the run when violated. Literal TLC source values such as `N/A`, `Unknown`, and `Outside of NYC` are preserved.

## Windows Constraint

PySpark performs large-scale filtering and duplicate detection. Runtime Quarantine Parquet is persisted with PyArrow rather than Spark `DataFrameWriter` on the managed Windows development laptop because the local Hadoop writer requires unavailable Windows native helpers.

The logical pipeline remains Spark-based for the large Taxi and 311 validation work.

## Auditability

Every run receives a unique `run_id`.

The output path includes that run ID, and every Quarantine row stores the same value along with the UTC rejection timestamp.

A run summary is written to:

`reports/quarantine/quarantine_latest_summary.json`

## Reconciliation

Quarantine counts are reported as **rejection-event counts**, not necessarily distinct source-record counts, because a record can fail multiple rules.

Downstream processing must reconcile:

`input records = accepted distinct records + rejected distinct records`

while rule-level monitoring may separately reconcile the total rejection-event count.

## Result

Phase 8 provides an auditable Quarantine contract, a controlled reason-code dictionary, large-source validation with PySpark, Windows-safe Parquet persistence, and tests verifying the required schema.
