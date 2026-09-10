# Data Lake Architecture — Raw / Bronze / Silver / Gold

## Status

PHASE 4 ARCHITECTURE DEFINED

## Overview

The NYC Urban Intelligence Platform uses a layered data-lake architecture:

RAW
→ BRONZE
→ VALIDATION / DATA QUALITY
→ SILVER
→ GOLD

Records that fail important validation rules are routed from the validation stage to QUARANTINE.

Gold datasets are subsequently consumed by:

- SQL Server
- Power BI
- Machine Learning

---

# 1. RAW Layer

Location:

`data/raw/`

Purpose:

The Raw layer contains source data acquired from the original systems.

Rules:

- Preserve source data without business transformation.
- Do not manually edit Raw files.
- Maintain source/year/month partitioning where applicable.
- Raw data acts as the immutable source-of-record for downstream processing.
- Transformations must not overwrite Raw files.

Examples:

- Yellow Taxi monthly Parquet files
- NYC 311 paginated JSON responses
- Open-Meteo historical weather responses
- Taxi Zone lookup and geographic files

Raw data is read by Bronze ingestion jobs.

---

# 2. BRONZE Layer

Location:

`data/bronze/`

Purpose:

Bronze contains a programmatically ingested representation of Raw source data.

Bronze is the first processing layer.

Allowed operations include:

- Schema capture
- Source-file identification
- Ingestion timestamp capture
- Run ID attachment
- Basic ingestion metadata
- Conversion into processing-friendly storage where required

Typical metadata columns may include:

- `_source`
- `_source_file`
- `_ingested_at`
- `_run_id`
- `_processing_year`
- `_processing_month`

No business cleaning occurs in Bronze.

Bronze must not:

- Remove suspicious business records
- Correct invalid values
- Deduplicate business records
- Apply analytical aggregations
- Perform business enrichment

The purpose of Bronze is traceable and reproducible ingestion.

---

# 3. VALIDATION / DATA QUALITY STAGE

Bronze data passes through formal profiling and data-quality validation before publication to Silver.

Validation may identify:

- Invalid dates
- Missing required fields
- Invalid taxi fares
- Invalid trip distances
- Impossible trip durations
- Missing locations
- Duplicate records
- Missing 311 coordinates
- Weather gaps
- Schema mismatches

A record either proceeds toward Silver or is handled according to the relevant data-quality rule.

Records must never be silently discarded.

---

# 4. QUARANTINE Layer

Location:

`data/quarantine/`

Purpose:

Quarantine contains records rejected by important data-quality rules.

Every quarantined record must retain enough information to explain and reproduce the rejection.

Required rejection information includes:

- Source
- Rejection reason
- Run ID
- Original record information

The detailed implementation will retain:

- `source`
- `reason_code`
- `reason_description`
- `run_id`
- `rejected_at`
- `original_record`

Examples of future reason codes include:

- `NEGATIVE_FARE`
- `INVALID_DURATION`
- `MISSING_PICKUP_ZONE`
- `INVALID_DATE`
- `DUPLICATE_RECORD`
- `MISSING_311_COORDINATES`
- `SCHEMA_MISMATCH`

Quarantined records are evidence of data-quality handling and must not be silently deleted.

---

# 5. SILVER Layer

Location:

`data/silver/`

Purpose:

Silver contains cleaned, standardized, validated, and analytically usable detailed data.

Typical Silver operations include:

- Type casting
- Column standardization
- Deduplication
- Business validation
- Date/time standardization
- Geographic enrichment
- Rejected-record separation

Examples include:

### Taxi

- Standardized timestamps
- Standardized numeric fields
- Validated trip records
- Duplicate handling
- Taxi Zone enrichment
- Borough enrichment
- Derived trip duration where appropriate

### NYC 311

- Standardized complaint timestamps
- Deduplicated complaint identifiers
- Standardized complaint fields
- Validated coordinates
- Taxi Zone geographic enrichment

### Weather

- Standardized hourly timestamps
- Standardized weather measures
- Validation of hourly continuity
- Consistent weather field names and data types

Silver remains primarily detailed/granular data.

---

# 6. GOLD Layer

Location:

`data/gold/`

Purpose:

Gold contains business-ready analytical datasets.

Gold may contain:

- Aggregations
- Cross-source joins
- Business metrics
- Date-hour-zone analytical datasets
- Machine-learning feature datasets

The principal analytical grain for this project will be:

`Date + Hour + Taxi Zone`

Candidate Gold measures include:

- Taxi trip count
- Taxi demand
- Total revenue
- Average fare
- Average trip distance
- Average trip duration
- 311 complaint count
- Weather measures
- Precipitation indicators
- Snow indicators
- Temperature
- Demand prediction features

Gold is designed for downstream analytical consumption.

Gold feeds:

- SQL Server dimensional warehouse
- Power BI dashboards
- Machine-learning workflows

---

# 7. Layer Transition Rules

## Raw → Bronze

Programmatic ingestion only.

Capture schema and lineage metadata.

No business cleaning.

## Bronze → Validation

Profile and evaluate records against explicit quality rules.

## Validation → Quarantine

Records failing important rules are retained with rejection metadata and original-record information.

## Validation → Silver

Accepted records are standardized, cleaned, deduplicated, validated, and enriched.

## Silver → Gold

Validated detailed datasets are aggregated and joined into business-ready analytical structures.

## Gold → Consumers

Gold datasets are loaded or consumed by:

- SQL Server
- Power BI
- Machine Learning

---

# 8. Processing Principles

The architecture follows these principles:

1. Raw files remain immutable.
2. Every processing stage is reproducible.
3. Data lineage must be retained.
4. Rejected data is quarantined rather than silently deleted.
5. Business cleaning occurs only after Bronze.
6. Silver contains validated detailed data.
7. Gold contains business-ready analytical data.
8. Gold is created before SQL warehouse loading.
9. Monthly partitioning should be retained where practical.
10. Logging and reconciliation apply across all layers.

---

# 9. Physical Structure

```text
data/
├── raw/
├── bronze/
├── silver/
├── gold/
└── quarantine/