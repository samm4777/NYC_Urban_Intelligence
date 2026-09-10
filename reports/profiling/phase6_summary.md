# Phase 6 — Data Profiling Report

## Status

COMPLETE

## Objective

Profile every source before cleaning and distinguish between:

- Definitely invalid records
- Candidate anomalies requiring investigation before formal Data Quality rules

No cleaning was performed during profiling.

---

# 1. Yellow Taxi — 2025

## Scale

- Raw files: 12 monthly Parquet files
- Rows profiled: 48,722,602
- Expected rows: 48,722,602
- Row-count reconciliation: PASS
- Source columns: 20
- Monthly schema differences: 0

## Date Range

- Minimum pickup timestamp: 2007-12-05 18:45:00
- Maximum pickup timestamp: 2025-12-31 23:59:59
- Minimum drop-off timestamp: 2007-12-05 19:02:00
- Maximum drop-off timestamp: 2026-01-05 13:00:34

The presence of pickup records outside the intended 2025 period is a confirmed quality issue.

## Duplicate Records

Exact duplicate source records detected:

- 1

Duplicate detection used a SHA-256 hash of the complete source record.

## Definitely Invalid Taxi Records

| Check | Count |
|---|---:|
| Missing pickup timestamp | 0 |
| Missing drop-off timestamp | 0 |
| Drop-off before pickup | 2,235 |
| Pickup outside 2025 | 29 |

These conditions are structurally or temporally invalid and are candidates for formal quarantine rules.

## Taxi Candidate Anomalies

| Candidate anomaly | Count |
|---|---:|
| Fare >= 900 | 145 |
| Negative fare | 2,848,620 |
| Negative total amount | 973,721 |
| Distance >= 150 miles | 2,348 |
| Negative trip distance | 0 |
| Duration >= 10 hours | 12,989 |
| Missing pickup location | 0 |
| Missing drop-off location | 0 |
| Passenger count <= 0 | 260,062 |
| Passenger count > 6 | 146 |

These values are not automatically rejected during profiling.

In particular, negative fare and negative total values occur frequently enough that their business meaning must be investigated before they are converted into formal Data Quality rules.

---

# 2. NYC 311 Service Requests — 2025

## Scale

- Raw JSON pages: 80
- Rows profiled: 3,655,040
- Expected rows: 3,655,040
- Row-count reconciliation: PASS
- Combined source columns discovered: 44
- Duplicate unique_key rows: 0

The first sampled page contained fewer fields than the full-year union because the Socrata JSON source can omit fields that are absent from individual records.

Full-year profiling therefore used the union of source fields.

## Date Range

- Minimum created timestamp: 2025-01-01 00:00:12
- Maximum created timestamp: 2025-12-31 23:59:28
- Minimum closed timestamp: 2024-10-21 11:06:00
- Maximum closed timestamp: 2026-09-08 14:13:07

Closed dates can legitimately extend outside 2025 because the dataset is selected by complaint creation date.

Therefore, closed_date outside 2025 is not itself classified as invalid.

## Definitely Invalid 311 Records

| Check | Count |
|---|---:|
| Missing or unparseable created_date | 0 |
| created_date outside 2025 | 0 |
| closed_date before created_date | 914 |
| Invalid latitude range | 0 |
| Invalid longitude range | 0 |

The 914 records where closed_date precedes created_date are structurally inconsistent and should become a formal Data Quality rule.

## 311 Candidate Anomalies

| Candidate anomaly | Count |
|---|---:|
| Missing coordinates | 50,148 |
| Resolution greater than 365 days | 5,022 |
| Missing or unexpected borough | 0 |
| Duplicate unique_key rows | 0 |

Missing coordinates are especially important because geographic enrichment of 311 complaints requires latitude and longitude.

These records should not be silently deleted; their treatment will be defined during the Data Quality and Quarantine phases.

---

# 3. NYC Historical Weather — 2025

## Scale

- Raw files: 12
- Hourly rows profiled: 8,760
- Expected rows: 8,760
- Row-count reconciliation: PASS
- Hourly variables: 10
- Monthly schema problems: 0

## Time Coverage

- Minimum timestamp: 2025-01-01 00:00:00
- Maximum timestamp: 2025-12-31 23:00:00
- Unparseable timestamps: 0
- Duplicate timestamps: 0
- Missing expected hours: 0
- Unexpected timestamps: 0
- Non-hourly gaps: 0

The Weather dataset provides complete hourly coverage for 2025.

## Missing Values

All profiled Weather fields have:

- Missing count: 0

## Candidate Anomalies

The following checks all returned zero records:

- Temperature outside plausible NYC range
- Humidity outside 0–100
- Negative precipitation
- Negative rain
- Negative snowfall
- Negative wind speed
- Negative wind gust

No Weather records currently require quarantine based on the investigated profiling conditions.

---

# 4. TLC Taxi Zone Reference Data

## Scale

- Lookup rows: 265
- Expected rows: 265
- Columns: 4
- LocationID range: 1–265
- Distinct LocationID values: 265
- Duplicate LocationID rows: 0
- Geographic support files missing: 0
- Expected schema: PASS

Columns:

- LocationID
- Borough
- Zone
- service_zone

## Definitely Invalid Taxi Zone Records

| Check | Count |
|---|---:|
| Missing LocationID | 0 |
| Duplicate LocationID rows | 0 |
| Missing Zone name | 0 |

## Candidate Reference Values

Two rows contain special source labels such as:

- Unknown
- N/A
- Outside of NYC

These are literal TLC reference values, not missing values.

Pandas profiling therefore uses `keep_default_na=False` so strings such as `N/A` are preserved rather than incorrectly interpreted as null.

Candidate placeholder/reference rows:

- 2

These values must be retained and handled explicitly during enrichment rather than treated as accidental missing data.

---

# 5. Profiling Methodology

Large datasets were profiled with PySpark:

- Yellow Taxi
- NYC 311

Small supporting datasets were profiled with Pandas:

- Weather
- Taxi Zone lookup

Parquet metadata and PyArrow were used where appropriate for efficient row-count and schema inspection.

No source data was modified.

No records were deleted during profiling.

---

# 6. Phase 7 Inputs

Profiling findings will be converted into explicit Data Quality rules during Phase 7.

Highest-priority findings include:

1. Taxi drop-off before pickup
2. Taxi pickup timestamp outside 2025
3. Taxi exact duplicate record
4. 311 closed timestamp before created timestamp
5. 311 records missing geographic coordinates
6. Taxi fare and total-amount anomalies
7. Taxi extreme trip distances
8. Taxi extreme trip durations
9. Taxi passenger-count anomalies
10. Taxi Zone special reference values

Each Phase 7 rule will define:

- rule_id
- rule_name
- description
- severity
- action

Candidate anomalies will not automatically become rejection rules without further analysis.

---

# 7. Profiling Artifacts

Profiling outputs are stored under:

`reports/profiling/`

Taxi artifacts include:

- taxi_profile_summary.json
- taxi_missing_values.csv
- taxi_duplicate_count.csv
- taxi_definitely_invalid.csv
- taxi_candidate_anomalies.csv
- taxi_outlier_quantiles.csv
- taxi_schema_by_month.csv
- taxi_schema_differences.csv
- taxi_monthly_rows.csv

311 artifacts include:

- 311_profile_summary.json
- 311_column_types.csv
- 311_missing_values.csv
- 311_duplicate_count.csv
- 311_definitely_invalid.csv
- 311_candidate_anomalies.csv
- 311_schema_differences.csv
- 311_top_distributions.csv

Weather artifacts include:

- weather_profile_summary.json
- weather_missing_values.csv
- weather_definitely_invalid.csv
- weather_candidate_anomalies.csv
- weather_outlier_quantiles.csv
- weather_schema_by_month.csv

Taxi Zone artifacts include:

- taxi_zone_profile_summary.json
- taxi_zone_schema.csv
- taxi_zone_distributions.csv
- taxi_zone_definitely_invalid.csv
- taxi_zone_candidate_anomalies.csv
- taxi_zone_geographic_files.csv

---

# Phase 6 Result

All four project data sources were profiled before cleaning.

Required profiling checks covering row counts, schemas, data types, missing values, duplicates, date ranges, schema differences, outliers, suspicious values, and obvious invalid records have been performed.

Definitely invalid records and candidate anomalies have been explicitly separated.

Phase 6 is COMPLETE.