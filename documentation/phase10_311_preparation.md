# Phase 10 — NYC 311 Data Preparation

## Status

COMPLETE

## Objective

Prepare the full-year 2025 NYC 311 Service Requests dataset for analytical use in the Silver layer.

Phase 10 standardizes and prepares:

- complaint creation date;
- complaint creation time;
- complaint type;
- agency;
- borough;
- latitude;
- longitude;
- incident address;
- status;
- closed date;
- resolution description;
- long-resolution anomaly indicator;
- provenance and processing metadata.

## Input

Raw source:

`data/raw/complaints_311/year=2025/month=MM`

Full-year Raw rows:

`3,655,040`

Raw files:

`80`

## Output

Silver layer:

`data/silver/complaints_311/year=2025/month=MM`

Full-year Silver rows:

`3,604,061`

All twelve months of 2025 were successfully processed.

## Data Quality Policy

Phase 10 remained consistent with the Phase 7 Data Quality catalog and Phase 8 Quarantine implementation.

Only records classified as proven-invalid were excluded from Silver.

Phase 8 identified:

- DQ_311_003 — Closed Before Created: 914 rejection events
- DQ_311_005 — Missing Coordinates: 50,148 rejection events

Total rejection events:

`51,062`

Distinct rejected source records:

`50,979`

Because 83 records violated both rejection conditions, rejection-event count is greater than distinct rejected-record count.

No rejected record was silently deleted.

## Full-Year Reconciliation

| Metric | Rows |
|---|---:|
| Raw 311 | 3,655,040 |
| Distinct rejected records | 50,979 |
| Silver 311 | 3,604,061 |

Equation:

`3,655,040 - 50,979 = 3,604,061`

Result:

`PASS`

## Timestamp Standardization

Raw timestamp fields were provided as strings.

Phase 10 standardizes them into:

- `created_at` — timestamp
- `created_date` — date
- `created_time` — time representation
- `closed_at` — timestamp
- `closed_date` — date

Raw 2025 creation-period validation showed:

- minimum created timestamp: `2025-01-01 00:00:12`
- maximum created timestamp: `2025-12-31 23:59:28`

Missing `closed_date` values are permitted because open or unresolved complaints may not yet have a closure timestamp.

## Borough Standardization

Observed Raw borough values:

- BROOKLYN
- QUEENS
- BRONX
- MANHATTAN
- STATEN ISLAND
- Unspecified

Silver canonical values:

- Brooklyn
- Queens
- Bronx
- Manhattan
- Staten Island
- Unspecified

No additional borough categories were invented.

## Agency Standardization

Agency values are:

- whitespace-normalized;
- converted to uppercase;
- otherwise preserved as the observed agency codes.

The full-year profiling dataset contained 15 distinct agency codes.

## Complaint-Type Standardization

Full-year profiling identified 193 distinct Raw complaint labels.

Normalization was intentionally conservative.

Only demonstrated case-equivalent collisions were merged:

- `PLUMBING` / `Plumbing` -> `Plumbing`
- `ELEVATOR` / `Elevator` -> `Elevator`
- `ASBESTOS` / `Asbestos` -> `Asbestos`

All other complaint labels were preserved after whitespace normalization.

This avoids unsupported semantic recoding of complaint categories.

## Coordinate Standardization

Raw `latitude` and `longitude` fields were strings.

Silver converts them to:

- `latitude` — float64
- `longitude` — float64

Records with missing coordinates were excluded consistently with DQ_311_005 because coordinates are required for later spatial enrichment.

Final Silver validation confirmed:

- null latitude values: `0`
- null longitude values: `0`
- invalid global coordinate ranges: `0`

## Address

The analytical address field is derived directly from:

`incident_address -> address`

Missing source addresses remain null.

Phase 6 found:

`122,936`

Raw records with missing incident addresses.

No synthetic addresses were created.

## Resolution Description

`resolution_description` is preserved after basic whitespace cleanup.

Missing descriptions remain null rather than being fabricated.

Phase 6 found:

`40,399`

Raw records with missing resolution descriptions.

## Long Resolution Duration

DQ_311_007 identifies complaints whose resolution duration exceeds 365 days.

This condition is classified as:

`Flag and Retain`

rather than a rejection condition.

Silver therefore includes:

`is_long_resolution`

to support later analysis while preserving the source complaint.

## January Validation

January processing produced:

| Metric | Rows |
|---|---:|
| Raw | 348,180 |
| Rejected | 3,196 |
| Silver | 344,984 |

January schema and normalization validation passed.

Examples confirmed:

- canonical borough names;
- uppercase agency codes;
- complaint-case collision merging;
- float64 coordinates;
- zero null Silver coordinates;
- long-resolution flag generation.

## Audit and Provenance Fields

Silver retains processing metadata including:

- `_source`
- `_source_file`
- `_run_id`
- `_processed_at`
- `_processing_year`
- `_processing_month`

These fields support lineage, reproducibility, and auditability.

## Implementation

Phase 10 transformation:

`python/prepare_311_silver.py`

Reconciliation report:

`reports/reconciliation/311_silver_reconciliation.csv`

Pipeline log:

`logs/pipeline_runs.jsonl`

Silver output:

`data/silver/complaints_311/year=2025/month=01 ... month=12`

## Phase 10 Result

Phase 10 is COMPLETE.

The project now contains a reconciled, analysis-ready full-year 2025 NYC 311 Silver dataset with:

- standardized timestamps;
- canonical borough values;
- standardized agency codes;
- evidence-based complaint normalization;
- numeric coordinates;
- preserved address and resolution fields;
- Data Quality-consistent rejection handling;
- long-resolution anomaly flags;
- audit metadata;
- twelve monthly Silver partitions;
- full-year reconciliation.

Final Silver rows:

`3,604,061`

Final reconciliation:

`PASS`

The next roadmap stage is:

**Phase 11 — Weather Data Preparation**
