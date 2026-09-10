# NYC Urban Intelligence Platform

## Master Project Execution Plan

This README is the master implementation roadmap for the **NYC Urban Intelligence Platform**.

The project builds an end-to-end urban data platform combining:

- NYC Yellow Taxi trip data
- NYC 311 Service Requests
- NYC historical weather
- NYC Taxi Zone geographic data

The final platform will support analysis of:

- Taxi demand
- Revenue
- Busy locations
- Busy hours
- Weather impact
- 311 complaint activity
- Year/month trends
- Predicted future taxi demand

The target architecture is:

```text
NYC Taxi Data ──┐
NYC 311 Data ───┤
Weather API ────┤
Taxi Zones ─────┘
        |
        v
      RAW
        |
        v
     BRONZE
        |
        v
Validation / Data Quality
        |
   +----+----+
   |         |
   v         v
SILVER   QUARANTINE
   |
   v
  GOLD
   |
   +-------------------> SQL Server Warehouse
   |
   +-------------------> Machine Learning
   |
   +-------------------> Power BI
```

Apache Airflow orchestrates the pipeline. Docker provides reproducibility. Logging, testing, reconciliation, incremental loading, and Git history are treated as cross-cutting requirements throughout the build.

---

# 1. Technology Stack

The project uses:

- Python
- Pandas
- PySpark
- SQL Server
- Power BI
- DAX
- Scikit-learn
- Git / GitHub
- Apache Airflow
- Docker / Docker Compose

---

# 2. Data Sources

## 2.1 NYC Yellow Taxi Trips

Use Yellow Taxi trip data for 2025.

Source:

```text
https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page
```

Use multiple monthly Parquet files rather than only one month.

---

## 2.2 NYC Taxi Zones

Use the official TLC:

- Taxi Zone lookup CSV
- Taxi Zone shapefile / geographic file

These are required for zone and borough enrichment and spatial mapping.

---

## 2.3 NYC 311 Service Requests

Use NYC 311 Service Requests for 2025.

Source:

```text
https://data.cityofnewyork.us/resource/erm2-nwe9.json
```

The full required period must be retrieved using pagination.

---

## 2.4 NYC Historical Weather

Use historical NYC weather for 2025.

Source:

```text
https://open-meteo.com/en/docs/historical-weather-api
```

Useful fields include:

- Temperature
- Rain
- Snow
- Wind
- Weather condition

---

# 3. Final Repository Structure

```text
NYC_Urban_Intelligence/
│
├── airflow/
├── python/
├── spark/
├── sql/
├── tests/
├── data_quality/
├── model/
├── reports/
├── documentation/
├── docker/
├── config/
├── data/
│   ├── raw/
│   ├── bronze/
│   ├── silver/
│   ├── gold/
│   └── quarantine/
│
├── NYC_Urban_Intelligence.pbix
├── Architecture_Diagram.png
├── README.md
└── GitHub_Repository_Link.txt
```

---

# 4. Data-Lake Layer Definitions

## RAW

Exact downloaded source files.

Rules:

- Never manually modified
- Preserve source-system representation
- Organized by source and time partition
- Used as immutable evidence of source data

Example:

```text
data/raw/
├── taxi/year=2025/month=01/
├── taxi/year=2025/month=02/
├── complaints_311/year=2025/month=01/
├── weather/year=2025/month=01/
└── taxi_zones/
```

---

## BRONZE

Programmatically ingested copy of Raw.

Allowed operations:

- Schema capture
- Ingestion metadata
- Source filename
- Ingestion timestamp
- Run ID

No business cleaning occurs here.

---

## SILVER

Cleaned and standardized data.

Typical operations:

- Type casting
- Column standardization
- Deduplication
- Business validation
- Date/time standardization
- Geographic enrichment
- Rejected-record separation

---

## QUARANTINE

Contains records that fail important quality rules.

Each rejected record must include:

- Source
- Rejection reason
- Run ID
- Original record information

Rejected records must never be silently deleted.

---

## GOLD

Business-ready datasets.

Gold may contain:

- Aggregations
- Joins
- Business metrics
- Zone-hour analytical tables
- Machine-learning feature tables

Gold feeds:

- SQL Server
- Power BI
- Machine Learning

---

# 5. Execution Model

This roadmap contains:

- **46 original execution phases**
- **1 additional cross-cutting phase: Phase 0B**

Phase 0B exists to prevent logging, testing, reconciliation, incremental loading, Docker, and Airflow requirements from being retrofitted later.

---

# 6. Quick Phase Mapping

| Phase | Original Requirement | Topic |
|---|---:|---|
| 0 | 41, 42, 46 | Git, Secrets, Folder Structure |
| 0B | Cross-cutting | Logging, Reconciliation, Partitions, Schema Draft, Airflow/Docker/Test Skeletons |
| 1 | 1 | Tools Setup |
| 2 | 2 | Data Sources |
| 3 | 3 | Raw Data Storage |
| 4 | 4 | Bronze / Silver / Gold Architecture |
| 5 | 5 | PySpark Processing |
| 6 | 6 | Data Profiling |
| 7 | 7 | Data Quality |
| 8 | 8 | Quarantine |
| 9 | 9 | Taxi Preparation |
| 10 | 10 | 311 Preparation |
| 11 | 11 | Weather Preparation |
| 12 | 12 | Geospatial Mapping |
| 13 | 13 | Combined Gold Dataset |
| 14 | 15 | Star Schema Design |
| 15 | 14 | SQL Warehouse |
| 16 | 16 | Incremental Loading |
| 17 | 17 | Duplicate Prevention |
| 18 | 18 | ETL Logging |
| 19 | 19 | Airflow |
| 20 | 20 | Failure Handling |
| 21 | 21 | Docker |
| 22 | 22 | SQL Analysis |
| 23 | 23 | SQL Optimization |
| 24 | 24 | ML Feature Setup |
| 25 | 25 | Baseline Model |
| 26 | 26 | ML Model Comparison |
| 27 | 27 | Time-Based Testing |
| 28 | 28 | Model Evaluation |
| 29 | 29 | Feature Importance |
| 30 | 30 | Store Predictions |
| 31 | 31 | Power BI Executive Overview |
| 32 | 32 | Power BI Location Analysis |
| 33 | 33 | Power BI Time Analysis |
| 34 | 34 | Weather & Urban Activity |
| 35 | 35 | Forecast Analysis |
| 36 | 36 | Data Quality Dashboard |
| 37 | 37 | DAX |
| 38 | 38 | Reconciliation |
| 39 | 39 | Power BI Validation |
| 40 | 40 | Automated Testing |
| 41 | 43 | Architecture Diagram |
| 42 | 44 | Documentation |
| 43 | 45 | Final Analytical Findings |
| 44 | 46 | Submission Packaging |
| 45 | 47 | Final Demonstration |

---

# 7. PHASE 0 — Project Foundation

## Goal

Set up the project correctly before writing production code.

## Tasks

1. Create GitHub repository:

```text
NYC_Urban_Intelligence
```

2. Create the full repository folder structure.

3. Create `.gitignore`.

Include:

- `.venv/`
- `venv/`
- `__pycache__/`
- Spark logs
- Data files
- `.env`
- Airflow local metadata
- Docker volumes
- Power BI temporary files

4. Create `.env`.

Example variables:

```text
SQL_SERVER_HOST=
SQL_SERVER_DATABASE=
SQL_USER=
SQL_PASSWORD=
NYC311_API_TOKEN=
```

5. Create `.env.example` with variable names only.

6. Load configuration using environment variables or `python-dotenv`.

7. Never hard-code:

- Passwords
- Database credentials
- API secrets
- Machine-specific paths

8. Create:

```text
GitHub_Repository_Link.txt
```

9. Commit incrementally throughout the project.

The final Git history must show actual project development rather than one final commit.

---

# 8. PHASE 0B — Cross-Cutting Foundations

These components begin now and are finalized in later phases.

---

## 8.1 Logging Architecture

Every pipeline execution should produce a structured log.

Minimum fields:

```text
run_id
source
processing_month
started_at
finished_at
rows_read
rows_valid
rows_rejected
status
error_message
```

Create a shared helper such as:

```text
python/logging_utils.py
```

Initially it may log to:

- Console
- JSON
- CSV
- Local file

Later, Phase 18 moves this into SQL Server.

---

## 8.2 Reconciliation Capture

From the first ingestion, record row counts at every transition:

```text
Raw
→ Bronze
→ Silver
→ Gold
→ SQL
```

Do not wait until Phase 38 to reconstruct these numbers.

---

## 8.3 Partitioning Strategy

Use time-based storage from the start.

Example:

```text
data/
├── raw/
│   └── taxi/year=2025/month=01/
├── bronze/
│   └── taxi/year=2025/month=01/
├── silver/
│   └── taxi/year=2025/month=01/
└── gold/
    └── zone_hourly/year=2025/month=01/
```

Apply equivalent monthly partitions to:

- Taxi
- 311
- Weather

Taxi zones are reference data and do not require monthly partitions.

---

## 8.4 Draft Dimensional Model

Create an initial draft only.

Example:

```text
DimDate
DimTime
DimZone
DimPaymentType
DimComplaintType
DimWeatherCondition

FactTaxiTrips
Fact311Complaints
FactZoneHourlyActivity
FactDemandPrediction
```

The final structure is decided later after Gold schemas exist.

---

## 8.5 Airflow Skeleton

Create a basic DAG placeholder.

Potential structure:

```text
Ingestion
→ Bronze
→ Validation
→ Silver
→ Gold
→ SQL Warehouse
```

Tasks can initially be placeholders.

---

## 8.6 Docker Skeleton

Create an initial:

```text
docker-compose.yml
```

Services can be added gradually.

---

## 8.7 Test Harness

Create:

```text
tests/
```

Add at least one trivial passing test.

As real transformations are built, add tests immediately.

---

# 9. PHASE 1 — Tools & Environment Setup

## Tasks

1. Install Python.
2. Create a virtual environment.
3. Create `requirements.txt`.
4. Install Pandas.
5. Install PySpark.
6. Install Scikit-learn.
7. Install SQL connectivity libraries.
8. Install `requests`.
9. Install `python-dotenv`.
10. Verify Java for PySpark.
11. Install or configure SQL Server.
12. Install SQL Server Management Studio or another SQL client.
13. Install Power BI Desktop.
14. Verify Airflow.
15. Verify Docker.
16. Verify Docker Compose.
17. Verify Git.
18. Verify GitHub repository connectivity.

---

# 10. PHASE 2 — Data Acquisition

## Taxi

Download multiple monthly 2025 Yellow Taxi Parquet files.

Record:

- File name
- Source URL
- Month
- Download date
- File size

---

## Taxi Zones

Download:

- Taxi Zone lookup CSV
- Taxi Zone shapefile / geographic dataset

---

## 311

Pull full 2025 NYC 311 records.

Use pagination.

Track:

- Query range
- Page size
- Offset
- Row count
- Retrieval timestamp

---

## Weather

Pull historical NYC weather for 2025.

Prefer hourly data if the Gold grain will be hourly.

---

## Logging

Every acquisition run should log:

```text
source
processing_month
rows_read
run_id
status
```

---

# 11. PHASE 3 — Raw Data Storage

Store downloaded files exactly as received.

Example:

```text
data/raw/
├── taxi/
│   └── year=2025/
│       ├── month=01/
│       ├── month=02/
│       └── ...
├── complaints_311/
│   └── year=2025/
│       ├── month=01/
│       └── ...
├── weather/
│   └── year=2025/
│       ├── month=01/
│       └── ...
└── taxi_zones/
```

Never manually edit these files.

---

# 12. PHASE 4 — Bronze / Silver / Gold Architecture

Create:

```text
data/bronze/
data/silver/
data/gold/
data/quarantine/
```

Document precisely what happens at each layer.

Use the layer definitions stated earlier in this README.

---

# 13. PHASE 5 — PySpark Processing

Taxi data must primarily use PySpark.

## Taxi

Use PySpark for:

- Full-year ingestion
- Type conversion
- Validation
- Cleaning
- Joins
- Aggregations
- Gold creation

## Smaller Datasets

Pandas may be used where appropriate for:

- Taxi zone lookup
- Small weather summaries
- Profiling summaries
- Small support tables

Store Spark code under:

```text
spark/
```

Every job should emit run metrics.

---

# 14. PHASE 6 — Data Profiling

Profile every source before cleaning.

## Required Checks

- Row count
- Columns
- Data types
- Missing values
- Duplicate counts
- Min/max dates
- Schema differences
- Outliers
- Suspicious values
- Obvious invalid records

## Important Distinction

Phase 6 should separate:

### Definitely invalid

Examples:

- Drop-off before pickup
- Missing required timestamp
- Invalid date outside intended period
- Structurally impossible data

### Candidate anomalies

Examples:

- Fare = 900
- Trip distance = 150 miles
- Duration = 10 hours

Candidate anomalies become formal quality rules in Phase 7 after analysis.

Create a profiling report under:

```text
reports/
```

or:

```text
data_quality/
```

---

# 15. PHASE 7 — Data Quality Rules

Define explicit and defensible rules.

At minimum investigate:

- Invalid taxi fares
- Invalid trip distances
- Impossible trip durations
- Missing locations
- Duplicate records
- Invalid dates
- Missing 311 locations
- Weather gaps
- Schema changes

Every rule must have:

```text
rule_id
rule_name
description
severity
action
```

Example:

```text
DQ_TAXI_001
Negative Fare
fare_amount < 0
Critical
Quarantine
```

Do not silently delete rejected records.

---

# 16. PHASE 8 — Quarantine Invalid Data

Create:

```text
data/quarantine/
```

Each rejected record must retain:

```text
source
reason_code
reason_description
run_id
rejected_at
original_record
```

Create a reason-code dictionary.

Example:

```text
NEGATIVE_FARE
INVALID_DURATION
MISSING_PICKUP_ZONE
INVALID_DATE
DUPLICATE_RECORD
MISSING_311_COORDINATES
SCHEMA_MISMATCH
```

---

# 17. PHASE 9 — Taxi Data Preparation

Prepare taxi data for analysis by:

- Date
- Hour
- Pickup location
- Drop-off location
- Borough
- Distance
- Duration
- Fare
- Tip
- Payment method
- Revenue

## Derived Fields

Potential fields:

```text
pickup_date
pickup_hour
trip_duration_minutes
pickup_zone
dropoff_zone
pickup_borough
dropoff_borough
```

## Revenue Definition

Do not choose the revenue formula until the actual Yellow Taxi schema is inspected.

Possible options:

```text
Revenue = total_amount
```

or a carefully justified component-based calculation.

Whichever definition is chosen must be documented and used consistently in:

- SQL
- Power BI
- DAX
- ML features
- Analytical findings

---

# 18. PHASE 10 — 311 Data Preparation

Prepare:

- Date
- Time
- Complaint Type
- Agency
- Borough
- Latitude
- Longitude
- Address
- Status
- Closed Date
- Resolution Description

Standardize:

- Timestamps
- Borough names
- Complaint labels
- Agency values
- Coordinate data types

---

# 19. PHASE 11 — Weather Data Preparation

Prepare:

- Temperature
- Rain
- Snow
- Wind
- Weather condition

Use a time grain compatible with the Gold dataset.

If Gold is hourly:

```text
weather grain = hourly
```

Weather gaps must be:

- Flagged
- Documented
- Never silently filled without explanation

---

# 20. PHASE 12 — Geospatial Mapping

Map 311 complaints into Taxi Zones.

## Authoritative Mapping Method

Use:

```text
311 Latitude/Longitude
→ Point Geometry
→ Point-in-Polygon Spatial Join
→ Taxi Zone Polygon
→ LocationID
```

Do not use borough alone as an authoritative Taxi Zone assignment.

## Mapping Metrics

Record:

```text
Total 311 records
Successfully mapped
Unmapped - missing coordinates
Unmapped - outside taxi polygons
Mapping success %
```

Store mapped Taxi Zone ID on valid 311 records.

---

# 21. PHASE 13 — Combined Gold Analytical Dataset

Create at least one Gold table at approximately:

```text
Date + Hour + Taxi Zone
```

Potential fields:

```text
date
hour
taxi_zone_id
borough
taxi_trips
taxi_revenue
average_fare
average_trip_distance
complaints_311
temperature
rain
snow
weather_condition
```

## Aggregations

Taxi:

- Trip count
- Revenue sum
- Average fare
- Average distance

311:

- Complaint count

Weather:

- Temperature
- Rain
- Snow
- Condition

Document:

- Grain
- Join keys
- Aggregation rules
- Revenue definition

---

# 22. PHASE 14 — Star Schema / Dimensional Model Design

This phase intentionally occurs before SQL schema creation.

## Candidate Dimensions

```text
DimDate
DimTime
DimZone
DimPaymentType
DimComplaintType
DimWeatherCondition
```

## Candidate Facts

```text
FactTaxiTrips
Fact311Complaints
FactZoneHourlyActivity
FactDemandPrediction
```

Finalize:

- Grain
- Primary keys
- Surrogate keys
- Business keys
- Foreign keys
- Relationships

The Power BI model should follow the same dimensional structure.

---

# 23. PHASE 15 — SQL Server Data Warehouse

Create a dedicated SQL Server database.

## Recommended Build Order

1. Create schemas
2. Create dimensions
3. Create fact tables
4. Add primary keys
5. Add foreign keys
6. Add constraints
7. Create loading procedures
8. Load Gold data

SQL loading must be designed to support idempotency and future MERGE/upsert logic.

Do not create one giant flat table.

---

# 24. PHASE 16 — Incremental Loading

The platform must support new monthly data without rebuilding all historical data.

Use:

- Monthly partitions
- Watermarks
- Last-successful-load markers
- Processed-file registry

## Mandatory Test

1. Process January–June.
2. Add July.
3. Re-run.
4. Verify July is processed.
5. Verify January–June are not unnecessarily rebuilt.

Document the result.

---

# 25. PHASE 17 — Duplicate Prevention

Running the same pipeline twice must not duplicate warehouse records.

Define business keys.

Examples:

- 311: unique complaint ID
- Gold zone-hour: date + hour + zone
- Dimensions: natural lookup value or surrogate-key mapping

Use:

- SQL MERGE
- Upsert
- Deduplication before load
- Unique constraints where appropriate

## Mandatory Test

Run the same load twice.

Expected result:

```text
row_count_after_run_1 == row_count_after_run_2
```

unless source records genuinely changed.

---

# 26. PHASE 18 — ETL Logging

Create a formal SQL logging table.

Suggested structure:

```text
etl_run_log
-----------
run_id
source
processing_month
stage
start_time
end_time
rows_processed
rows_valid
rows_rejected
status
error_message
```

Every major task writes:

- Start entry
- Success entry
- Failure entry

Quarantine counts must reconcile with `rows_rejected`.

---

# 27. PHASE 19 — Airflow Orchestration

The original brief lists:

```text
Ingestion
→ Validation
→ Transformation
→ SQL Load
→ Gold Dataset
```

However, because Gold is also defined as the business-ready layer used by SQL, Power BI, and ML, the implemented architecture will use:

```text
Ingestion
→ Bronze
→ Validation
→ Silver
→ Gold
→ SQL Warehouse
```

This interpretation must be documented clearly in:

- DAG comments
- Architecture documentation
- Final README
- Final demonstration

## Airflow Tasks

Possible DAG:

```text
ingest_sources
    ↓
build_bronze
    ↓
validate_bronze
    ↓
build_silver
    ↓
build_gold
    ↓
load_sql_warehouse
    ↓
run_post_load_tests
```

---

# 28. PHASE 20 — Failure Handling

Handle at minimum:

- File unavailable
- API unavailable
- Invalid schema
- Empty dataset
- SQL connection failure
- Transformation failure
- Unexpected row count

On failure:

- Mark task failed
- Log error
- Prevent downstream publication
- Do not publish incomplete Gold data

Test failures deliberately.

---

# 29. PHASE 21 — Docker

Create reproducible services.

Potential services:

- Airflow webserver
- Airflow scheduler
- Airflow metadata DB
- Spark
- SQL Server
- Supporting Python environment

Create:

```text
docker/
├── Dockerfile
├── docker-compose.yml
└── ...
```

A new developer should be able to clone the repository and start the environment using documented commands.

---

# 30. PHASE 22 — SQL Analysis

Create at least 15 meaningful analytical questions.

Queries should demonstrate:

- CTEs
- Window functions
- LAG
- Ranking
- Joins
- Aggregations
- Date analysis
- CASE logic

Example questions:

1. Which zones have the highest taxi demand?
2. Which hours are busiest?
3. Which zones generate the most revenue?
4. Which borough has the highest average fare?
5. Which zones show the highest month-over-month growth?
6. How does taxi demand change during rain?
7. How does snowfall correspond with taxi activity?
8. Which complaint types dominate high-taxi-demand zones?
9. Which zones show high complaints but low taxi demand?
10. Which hours generate the highest tips?
11. Which payment methods are most common?
12. How does weekday demand compare with weekend demand?
13. Which zones show the largest revenue volatility?
14. Which zones have increasing complaints over time?
15. Which locations show simultaneous taxi-demand and complaint spikes?

Store SQL under:

```text
sql/
```

---

# 31. PHASE 23 — SQL Performance Optimization

Select at least three slower analytical queries.

For each query:

1. Record original execution time.
2. Capture execution plan.
3. Identify bottleneck.
4. Apply optimization.
5. Re-run.
6. Capture new execution plan.
7. Compare performance.

Potential techniques:

- Indexing
- Join rewrites
- Filter pushdown
- Reduced scans
- Better predicates
- Pre-aggregation

Store evidence in:

```text
reports/sql_performance/
```

---

# 32. PHASE 24 — Taxi Demand Prediction Setup

Choose a useful prediction grain.

Recommended candidate:

```text
Taxi Zone + Hour
```

Potential features:

- Previous demand
- Lagged demand
- Hour
- Day of week
- Month
- Weekend flag
- Zone
- Borough
- Temperature
- Rain
- Snow
- Weather condition
- 311 complaint count

Store ML code under:

```text
model/
```

---

# 33. PHASE 25 — Baseline Model

Create a simple baseline first.

Examples:

```text
Predicted demand = previous period demand
```

or:

```text
Predicted demand = historical mean for same zone/hour
```

Evaluate the baseline using the same test period as final models.

The final model must outperform the baseline.

---

# 34. PHASE 26 — Machine Learning Models

Train at least two appropriate models.

Possible candidates:

- Linear Regression
- Ridge Regression
- Random Forest Regressor
- Gradient Boosting Regressor
- HistGradientBoostingRegressor

Use the same:

- Features
- Training period
- Test period
- Metrics

Compare:

- Baseline
- Model 1
- Model 2

Choose the final model based on measured performance.

---

# 35. PHASE 27 — Time-Based Model Testing

Do not randomly mix historical and future records.

Example:

```text
Training:
January 2025 → October 2025

Testing:
November 2025 → December 2025
```

Prevent leakage.

Lag features must only use information that would have been available at prediction time.

---

# 36. PHASE 28 — Model Evaluation

Recommended primary metrics:

- MAE
- RMSE

Supporting metric:

- R²

MAPE should only be used where actual demand is greater than zero because zero-demand observations make normal MAPE unstable.

Alternative:

- sMAPE, if justified

Evaluate:

- Overall
- By zone
- By hour
- By day
- By demand level

Explain:

- Where model performs well
- Where model performs poorly
- Why errors may occur

---

# 37. PHASE 29 — Feature Importance

Measure actual influence.

Possible methods:

- Model coefficients
- Tree feature importance
- Permutation importance

Do not assume the final answer.

Rank measured features and explain results.

Potential features include:

- Historical demand
- Hour
- Zone
- Day
- Weather
- 311 activity

---

# 38. PHASE 30 — Store Predictions

Write predictions back into the analytical platform.

Suggested table:

```text
FactDemandPrediction
```

Possible fields:

```text
date_key
time_key
zone_key
actual_demand
predicted_demand
absolute_error
percentage_error
model_version
prediction_run_id
```

Power BI must be able to analyze:

```text
Actual Demand vs Predicted Demand
```

---

# 39. PHASE 31 — Power BI Executive Overview

Create KPIs:

- Total Trips
- Total Revenue
- Average Fare
- 311 Complaints
- Average Temperature

Create visuals:

- Taxi demand trend
- Revenue trend
- Top zones

---

# 40. PHASE 32 — Power BI Location Analysis

Include:

- Top Pickup Zones
- Top Drop-off Zones
- Borough performance
- Taxi activity by location
- Complaints by location
- Revenue by location

Use maps only where geographically meaningful.

---

# 41. PHASE 33 — Power BI Time Analysis

Analyze:

- Trips by hour
- Trips by day
- Trips by month
- Peak vs off-peak
- Weekday vs weekend

Create a demand heatmap such as:

```text
Hour × Day of Week
```

---

# 42. PHASE 34 — Weather & Urban Activity

Compare taxi demand against:

- Rain
- Snow
- Temperature bands
- Weather conditions

Compare 311 activity where useful.

Explicitly state:

> Correlation does not automatically imply causation.

---

# 43. PHASE 35 — Forecast Analysis

Include:

- Actual Demand
- Predicted Demand
- Prediction Error
- Error by Zone
- Error by Time
- Best Predicted Areas
- Worst Predicted Areas

---

# 44. PHASE 36 — Power BI Data Quality

Show:

- Raw Records
- Valid Records
- Rejected Records
- Duplicate Records
- Quality Issues
- Pipeline Status
- Last Successful Run

Source data from:

- ETL logs
- Quarantine
- Quality metrics

---

# 45. PHASE 37 — DAX Measures

Create at least 12 meaningful measures.

Required categories:

- Totals
- Averages
- Percentages
- Previous-period comparisons
- Growth %
- Rolling calculations
- Actual vs Forecast
- Forecast Error

Possible measures:

```text
Total Trips
Total Revenue
Average Fare
Average Trip Distance
Total Complaints
Trips Previous Month
Trips MoM Growth %
Revenue Previous Month
Revenue Growth %
Rolling 7-Day Trips
Forecast Error
Forecast Error %
Average Absolute Error
```

---

# 46. PHASE 38 — Reconciliation

Reconciliation must prove that data has not disappeared unexpectedly.

## Record-Level Reconciliation

For sources such as Taxi:

```text
Raw rows
=
Silver valid rows
+
Quarantined rows
```

after accounting for Bronze duplication rules and any documented deduplication handling.

## Gold Reconciliation

Gold is aggregated, therefore:

```text
Gold row count != Silver row count
```

That is expected.

Instead validate:

```text
Sum(Gold taxi_trips)
=
Number of valid Silver taxi trips represented
```

Example:

```text
Raw Taxi Records       20,000,000
Bronze Records         20,000,000

Silver Valid           19,750,000
Quarantined               250,000
                       ----------
Reconciled              20,000,000

Gold Rows                1,800,000
Gold Grain           Zone × Date × Hour

SUM(Gold Taxi Trips)    19,750,000
```

This is the correct way to reconcile aggregated Gold data.

---

# 47. PHASE 39 — Power BI Validation

Validate key Power BI numbers independently using SQL.

At minimum verify:

- Total Taxi Trips
- Total Revenue
- Top Taxi Zone
- Total Complaints
- Selected monthly totals

For each measure:

```text
SQL Result
Power BI Result
Match?
Difference
Resolution
```

Investigate every mismatch.

---

# 48. PHASE 40 — Automated Testing

Automated testing begins early but is finalized here.

Test:

- Duplicate keys
- Null required fields
- Invalid dates
- Missing relationships
- Unexpected row counts
- Invalid values
- Referential integrity

Potential tooling:

- pytest
- PySpark assertions
- SQL validation scripts

Store tests under:

```text
tests/
```

Ideally include critical tests in the Airflow DAG.

---

# 49. PHASE 41 — Architecture Diagram

Create a professional final architecture diagram reflecting the actual implementation.

It should show:

- Four data sources
- Raw
- Bronze
- Validation
- Silver
- Quarantine
- Gold
- SQL Server
- Machine Learning
- Power BI
- Airflow orchestration
- Logging
- Reconciliation
- Docker environment

Export:

```text
Architecture_Diagram.png
```

---

# 50. PHASE 42 — Final Documentation

The final README must explain:

- Project objective
- Architecture
- Data sources
- Data-quality decisions
- Raw/Bronze/Silver/Gold design
- SQL warehouse
- PySpark processing
- Airflow
- Incremental loading
- ML model
- Model results
- Power BI dashboards
- Major issues encountered
- Major insights
- Limitations

Documentation should be updated continuously rather than written only at the end.

---

# 51. PHASE 43 — Final Analytical Findings

Produce at least 10 meaningful findings.

Examples:

1. Where is taxi demand highest?
2. When is taxi demand highest?
3. Which areas generate the most revenue?
4. How does weather correspond with demand?
5. Which complaint categories are concentrated geographically?
6. Are high-complaint areas also high-traffic areas?
7. Which features matter most for demand prediction?
8. Where does the model perform best?
9. Where does the model struggle?
10. Which zones show unusual demand/revenue/complaint combinations?

Do not merely describe chart values.

Every finding should answer:

```text
What happened?
Why does it matter?
What is the practical interpretation?
```

---

# 52. PHASE 44 — Final Submission Packaging

Final project must contain:

```text
NYC_Urban_Intelligence/
│
├── airflow/
├── python/
├── spark/
├── sql/
├── tests/
├── data_quality/
├── model/
├── reports/
├── documentation/
├── docker/
├── NYC_Urban_Intelligence.pbix
├── Architecture_Diagram.png
├── README.md
└── GitHub_Repository_Link.txt
```

Perform a final repository audit before submission.

---

# 53. PHASE 45 — Final Demonstration

Prepare to demonstrate:

1. Raw source files
2. Bronze layer
3. Silver layer
4. Gold layer
5. PySpark transformation
6. SQL warehouse
7. Airflow DAG
8. Quarantine records
9. Data-quality failures
10. Incremental loading
11. Duplicate prevention
12. SQL analytics
13. SQL optimization
14. ML baseline
15. ML models
16. Model evaluation
17. Feature importance
18. Stored predictions
19. Power BI dashboards
20. Actual vs Predicted Demand
21. Reconciliation
22. Git commit history

Be ready to explain:

- Why the architecture was chosen
- Why PySpark was used for taxi data
- Why the dimensional model was designed as it was
- Why Gold is created before SQL loading
- Why the incremental strategy works
- Why the chosen ML model was selected
- Why particular data-quality thresholds were chosen

---

# 54. Execution Milestones

| Milestone | Phases |
|---|---|
| 1 — Foundation | 0, 0B, 1, 2, 3, 4 |
| 2 — Data Engineering | 5–13 |
| 3 — Warehouse | 14–18 |
| 4 — Production Pipeline | 19–21 |
| 5 — SQL Analytics | 22–23 |
| 6 — Machine Learning | 24–30 |
| 7 — Power BI | 31–37, 39 |
| 8 — Quality & Delivery | 38, 40–45 |

These milestones are for planning only.

Cross-cutting work such as:

- Logging
- Reconciliation
- Testing
- Incremental partitioning
- Documentation
- Git commits

must continue throughout the project.

---

# 55. Status Tracking Convention

Use the following format after completing each phase.

Example:

```text
PHASE 5 — PySpark Processing
Status: COMPLETE

Requirement 5:

[x] Taxi ingestion uses PySpark
[x] Full-scale taxi transformations use PySpark
[x] Pandas limited to smaller datasets
[x] Spark code stored under spark/
[x] Run logging implemented
[x] Evidence captured for final demonstration
```

Suggested status values:

```text
NOT STARTED
IN PROGRESS
BLOCKED
COMPLETE
VALIDATED
```

---

# 56. Definition of Done

The project is complete only when:

- All original requirements are implemented.
- Every phase is marked complete.
- All important data-quality issues are documented.
- Reconciliation succeeds.
- SQL and Power BI figures match.
- Incremental loading is demonstrated.
- Duplicate prevention is demonstrated.
- Airflow runs end to end.
- Docker setup is reproducible.
- The ML model beats the baseline.
- Predictions are stored in the analytical platform.
- Power BI contains all required pages.
- At least 12 DAX measures exist.
- At least 15 analytical SQL queries exist.
- At least 3 SQL queries have before/after optimization evidence.
- At least 10 meaningful analytical findings are documented.
- Git history demonstrates real development.
- Final architecture diagram matches the actual implementation.
- Final presentation can explain every major design decision.

---

# 57. Final Architecture Principle

The project should be built as a reproducible, auditable pipeline:

```text
Source Data
    ↓
Immutable Raw
    ↓
Bronze Ingestion
    ↓
Validation
    ↓
Silver Clean Data
    ↓
Gold Business Data
    ↓
SQL Dimensional Warehouse
    ↓
Analytics / ML / Power BI
```

With parallel support for:

```text
Quarantine
Logging
Testing
Reconciliation
Incremental Loading
Failure Handling
Docker
Git
Documentation
```

The final system should not only produce dashboards and predictions; it should also demonstrate **data lineage, quality, reproducibility, explainability, and operational reliability**.
