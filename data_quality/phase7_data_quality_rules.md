# Phase 7 — Data Quality Rules

## Status

COMPLETE — RULE CATALOG DEFINED

## Objective

Define explicit and defensible Data Quality rules using the Phase 6 profiling evidence.

No rejected record may be silently deleted. Rules with a `Quarantine` action retain the rejected record and its rejection metadata in the Quarantine layer during Phase 8 implementation.

## Decision Principles

1. Structural impossibilities are quarantined.
2. Records outside the intended analytical period are quarantined.
3. Missing fields required for downstream joins or grain construction are quarantined.
4. Duplicate business records are separated rather than silently dropped.
5. Candidate anomalies are flagged and retained unless profiling plus business evidence supports rejection.
6. Schema failures and incomplete Weather coverage fail the run and prevent downstream publication.
7. Source-defined Taxi Zone special labels such as `N/A` are preserved literally.
8. Raw data is never modified.

## Why Negative Taxi Fares Are Not Automatically Quarantined

Phase 6 found 2,848,620 Taxi rows with `fare_amount < 0` and 973,721 with `total_amount < 0`.

Because these values occur at material scale, profiling alone is not sufficient evidence that every negative value is an erroneous trip. A blanket rejection rule would remove a substantial portion of the source and could distort revenue analysis.

Therefore:

- negative fare and negative total amount are **candidate anomalies**;
- severity is `Medium`;
- action is `Flag and Retain`.

This is intentionally more defensible than blindly converting the example rule into a mass-rejection rule.

## Hard Taxi Rejection Rules

The following are treated as definitely invalid for the analytical pipeline:

- missing pickup timestamp;
- missing drop-off timestamp;
- drop-off before pickup;
- pickup outside calendar year 2025;
- missing required Taxi location IDs;
- exact duplicate record occurrences beyond the first;
- negative trip distance.

Extreme fares, distances, durations, and passenger counts are flagged for analysis but retained.

## 311 Rules

Hard rejection conditions include:

- missing/unparseable `created_date`;
- created date outside 2025;
- `closed_date < created_date`;
- duplicate `unique_key` occurrences beyond the first;
- missing coordinates needed for Taxi Zone point-in-polygon enrichment;
- coordinates outside global structural ranges.

Resolution durations greater than 365 days are flagged but retained.

## Weather Rules

Weather is expected to provide exactly one observation per hour for 2025.

Because Weather joins at hourly grain, unresolved gaps or duplicate timestamps can invalidate Gold joins. Missing expected hours therefore fail the run. Duplicate timestamps are quarantined and also prevent publication until resolved.

Physically impossible values such as humidity outside 0–100 or negative precipitation/wind measurements are quarantined.

## Schema Rules

Schema controls are pipeline-level rules rather than row-level rejection rules.

A missing required field or incompatible schema:

- marks the stage failed;
- prevents downstream publication;
- does not publish incomplete Silver or Gold datasets.

## Taxi Zone Reference Rules

`LocationID` must be present and unique.

Literal TLC source labels such as `Unknown`, `N/A`, and `Outside of NYC` are not nulls. They are preserved as reference values and handled explicitly during enrichment.

## Rule Catalog

The machine-readable catalog is stored at:

`data_quality/dq_rules.csv`

Every rule contains the required fields:

- `rule_id`
- `rule_name`
- `description`
- `severity`
- `action`

The catalog additionally records:

- source
- condition
- classification
- rationale

## Phase 6 Evidence Used

Key observed profiling results used to define the rules include:

### Taxi

- 48,722,602 total rows
- 2,235 drop-off-before-pickup records
- 29 pickup timestamps outside 2025
- 1 exact duplicate record
- 2,848,620 negative fares
- 973,721 negative total amounts
- 2,348 trips at least 150 miles
- 12,989 trips at least 10 hours
- 260,062 passenger counts <= 0
- 146 passenger counts > 6
- 0 monthly schema differences

### NYC 311

- 3,655,040 total rows
- 914 records with close time before creation time
- 50,148 records missing coordinates
- 5,022 resolutions longer than 365 days
- 0 duplicate `unique_key` rows
- 0 created dates outside 2025
- 0 invalid global coordinate ranges

### Weather

- 8,760 hourly observations
- 0 missing hours
- 0 duplicate timestamps
- 0 unexpected timestamps
- 0 physical-range anomalies in the investigated checks
- 0 monthly schema problems

### Taxi Zones

- 265 lookup rows
- 265 distinct `LocationID` values
- 0 duplicate LocationIDs
- 0 true missing zone names
- 2 special reference rows containing source labels such as `N/A`/`Unknown`

## Phase 8 Contract

Rows rejected by Phase 7 rules will be written to Quarantine with at least:

- source
- reason_code
- reason_description
- run_id
- rejected_at
- original_record

Quarantine counts must reconcile with processing metrics.

## Phase 7 Result

The project now has an explicit, evidence-based Data Quality rule catalog covering:

- Taxi fares
- Taxi trip distances
- Taxi trip durations
- Missing locations
- Duplicate records
- Invalid dates
- Missing 311 locations
- Weather gaps
- Schema changes
- Additional structural and reference-data controls

Phase 7 rule definition is COMPLETE. Rule execution and rejected-record persistence are implemented in subsequent validation, Quarantine, and Silver phases.
