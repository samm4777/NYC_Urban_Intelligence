# Phase 9 — Yellow Taxi Data Preparation

## Status

COMPLETE

## Objective

Prepare the full-year 2025 NYC Yellow Taxi dataset for analytical use in the Silver layer.

The Phase 9 transformation produces analysis-ready Taxi records enriched with:

- pickup date;
- pickup hour;
- pickup and drop-off Taxi zones;
- pickup and drop-off boroughs;
- service zones;
- trip distance;
- trip duration;
- fare;
- tip;
- payment method;
- revenue;
- anomaly indicators;
- Bronze provenance and audit metadata.

## Input

Source layer:

`data/bronze/taxi/year=2025/month=MM`

Full-year Bronze rows:

`48,722,602`

Taxi Zone lookup:

`data/raw/taxi_zones/taxi_zone_lookup.csv`

## Output

Silver layer:

`data/silver/taxi/year=2025/month=MM`

All twelve months of 2025 were successfully produced.

Full-year Silver rows:

`48,720,337`

## Data Quality and Rejection Policy

Phase 9 remained consistent with the Phase 7 Data Quality catalog and Phase 8 Quarantine implementation.

Only records classified as proven-invalid were excluded from Silver.

Full-year rejected Taxi records:

`2,265`

These correspond to the active Phase 8 rejection rules, including:

- drop-off before pickup;
- pickup timestamp outside the 2025 analytical period;
- exact duplicate records beyond the first occurrence.

Candidate anomalies classified as `Flag and Retain` were preserved in Silver.

Examples include:

- negative fares;
- negative total amounts;
- extreme fares;
- extreme trip distances;
- extreme trip durations;
- unusual passenger counts.

No additional records were silently deleted.

## Exact Duplicate Handling

Exact-source duplicate detection follows the Phase 8 implementation.

The complete Taxi source record is serialized and hashed using SHA-256.

Rows sharing the same source-record hash are ordered deterministically and assigned a row number.

The first occurrence is retained.

Only occurrences where:

`row_number > 1`

are rejected.

Full-year duplicate hashes detected:

`1`

Duplicate records rejected:

`1`

## Derived Analytical Fields

Phase 9 created the following principal derived attributes:

- `pickup_date`
- `pickup_hour`
- `trip_duration_minutes`
- `payment_method`
- `revenue`
- `pickup_zone`
- `pickup_borough`
- `pickup_service_zone`
- `dropoff_zone`
- `dropoff_borough`
- `dropoff_service_zone`

## Revenue Definition

The project defines:

`revenue = total_amount`

This preserves the reported Yellow Taxi trip-level total directly from the source instead of reconstructing revenue from component fields.

Negative `total_amount` values were not converted, removed, or replaced because Phase 7 classified them as candidate anomalies rather than proven-invalid records.

## Payment Method Mapping

The analytical `payment_method` field maps the Yellow Taxi `payment_type` codes as follows:

| payment_type | payment_method |
|---:|---|
| 0 | Flex Fare |
| 1 | Credit Card |
| 2 | Cash |
| 3 | No Charge |
| 4 | Dispute |
| 5 | Unknown |
| 6 | Voided Trip |
| other | Unmapped |

Observed full-year payment-type counts were:

| payment_type | rows |
|---:|---:|
| 0 | 11,611,894 |
| 1 | 31,054,000 |
| 2 | 4,654,345 |
| 3 | 308,147 |
| 4 | 1,094,213 |
| 5 | 3 |

The counts reconcile to the full Bronze population of 48,722,602 rows.

## Taxi Zone Enrichment

Pickup geography was joined using:

`PULocationID -> LocationID`

Drop-off geography was joined using:

`DOLocationID -> LocationID`

All observed Taxi location IDs were present in the official lookup.

Special TLC reference values were preserved.

Examples:

LocationID 264:

- Borough = `Unknown`
- Zone = null
- service_zone = null

LocationID 265:

- Borough = null
- Zone = `Outside of NYC`
- service_zone = null

These valid reference records were not treated as failed joins.

Final enrichment validation:

- unmatched pickup LocationIDs: `0`
- unmatched drop-off LocationIDs: `0`

## Windows Processing Strategy

PySpark performs the large-scale Taxi transformations.

Because the local Windows environment does not provide the native Hadoop `winutils.exe` implementation required by some Spark filesystem operations, Phase 9 uses the same proven approach established during Phase 5:

- Spark DataFrames for processing;
- explicit local file URIs for Spark reads;
- PyArrow for portable Windows-safe Parquet persistence.

This preserves PySpark as the primary Taxi transformation engine while avoiding Windows-specific Hadoop filesystem failures.

## Full-Year Reconciliation

Final reconciliation:

| Metric | Rows |
|---|---:|
| Bronze Taxi | 48,722,602 |
| Rejected | 2,265 |
| Silver Taxi | 48,720,337 |

Equation:

`48,722,602 - 2,265 = 48,720,337`

Result:

`PASS`

All twelve Silver partitions were physically verified from Parquet metadata.

## Audit Artifacts

Implementation:

`spark/build_taxi_silver.py`

Reconciliation report:

`reports/reconciliation/taxi_silver_reconciliation.csv`

Pipeline execution log:

`logs/pipeline_runs.jsonl`

Silver output:

`data/silver/taxi/year=2025/month=01 ... month=12`

## Phase 9 Result

Phase 9 is COMPLETE.

The project now contains a full-year, analysis-ready Yellow Taxi Silver dataset with:

- deterministic rejection handling;
- Phase 7/8-consistent Data Quality behavior;
- preserved candidate anomalies;
- Taxi Zone enrichment;
- payment-method decoding;
- trip-duration derivation;
- revenue definition;
- anomaly flags;
- provenance metadata;
- full-year reconciliation;
- zero unmatched Taxi Zone identifiers.

The next roadmap stage is:

**Phase 10 — NYC 311 Data Preparation**
