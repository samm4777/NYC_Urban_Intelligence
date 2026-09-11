# Phase 15 — Azure SQL Data Warehouse

## Status

**COMPLETE**

Phase 15 implements the SQL data warehouse layer for the NYC Urban
Intelligence Platform using Azure SQL Database.

Database:

`NYC_Urban_Intelligence_DW`

The existing `NYCTaxiWarehouse` database belongs to another project and
was not modified.

---

## Architecture

The warehouse uses a dimensional star-schema design with separate
schemas:

- `dw` — dimensions and facts
- `etl` — staging and ETL control objects
- `audit` — batch and reconciliation auditing

The warehouse does not use one large denormalized flat table.

---

## Dimensions

The following conformed dimensions were created and populated:

| Dimension | Rows |
|---|---:|
| DimDate | 2,558 |
| DimTime | 25 |
| DimZone | 267 |
| DimPaymentType | 8 |
| DimComplaintType | 184 |
| DimWeatherCondition | 13 |

### Zone domain

`DimZone` preserves both TLC source members and warehouse technical
members.

- `location_id = -1` — Unmapped / Outside Taxi Polygon
- `location_id = 0` — DW Unknown / Not Provided
- `location_id = 1–263` — authoritative TLC polygon zones
- `location_id = 264` — TLC source Unknown
- `location_id = 265` — TLC source Outside of NYC

Warehouse `zone_key` is the surrogate key. `location_id` remains the
business key.

---

## Fact Tables

The following fact-table structures were created:

- `dw.FactTaxiTrips`
- `dw.Fact311Complaints`
- `dw.FactZoneHourlyActivity`
- `dw.FactDemandPrediction`

Large analytical facts use clustered columnstore indexes.

`FactDemandPrediction` is reserved for the future machine-learning
phase.

The detailed Taxi and 311 fact structures are schema-ready but were not
bulk-loaded in Phase 15.

Phase 15 loads the combined Gold analytical dataset into:

`dw.FactZoneHourlyActivity`

---

## FactZoneHourlyActivity Grain

The fact grain is:

**one NYC local date + one hour + one authoritative Taxi Zone**

Business grain:

`date_key + time_key + zone_key`

The target enforces this grain with a unique nonclustered constraint.

---

## Gold Source

Source:

`data/gold/zone_hourly/year=2025/month=MM`

There are 12 monthly Parquet files.

The dense Gold design contains:

- 263 authoritative Taxi Zones
- 24 hours per day
- 365 dates in 2025

Expected annual rows:

`263 × 24 × 365 = 2,303,880`

Monthly expected row counts depend only on month length:

- 31-day month: 195,672
- 30-day month: 189,360
- February 2025: 176,736

---

## ETL Design

Gold loading follows:

Parquet  
→ `audit.LoadBatch`  
→ `etl.StageZoneHourlyActivity`  
→ `etl.usp_UpsertZoneHourlyActivity`  
→ `dw.FactZoneHourlyActivity`  
→ reconciliation

The process is idempotent.

Each monthly source file receives an idempotency key based on:

- source partition
- SHA-256 source-file hash

Already successful batches are skipped on rerun.

Failed or incomplete batches can be recovered and retried.

The warehouse upsert uses transactional UPDATE + INSERT logic rather
than direct uncontrolled appends.

---

## Audit Objects

Created:

- `audit.LoadBatch`
- `audit.ReconciliationResult`
- `etl.LoadWatermark`

`LoadBatch` records:

- pipeline
- source
- partition
- load type
- status
- rows read
- rows inserted
- rows updated
- rows rejected
- timestamps
- errors

`ReconciliationResult` stores source-to-target validation outcomes.

---

## Final 2025 Gold Reconciliation

Azure SQL final result:

| Metric | Gold Source | Azure SQL | Result |
|---|---:|---:|---|
| Zone-hour rows | 2,303,880 | 2,303,880 | PASS |
| Taxi trips | 48,617,295 | 48,617,295 | PASS |
| Taxi revenue | 1,306,369,662.27 | 1,306,369,662.27 | PASS |
| 311 complaints | 3,603,396 | 3,603,396 | PASS |
| Distinct dates | 365 | 365 | PASS |

Additional controls:

- successful monthly load batches: **12**
- failed monthly batches: **0**
- reconciliation PASS results: **12**
- remaining staging rows: **0**
- fact rows: **2,303,880**
- distinct Date + Hour + Zone grains: **2,303,880**

No duplicate Gold grain exists in the warehouse.

---

## Storage Strategy

Azure SQL free-tier storage is limited, so the warehouse deliberately
does not copy the Raw, Bronze, or Silver lake wholesale into SQL.

Large fact structures use clustered columnstore indexes to improve
analytical compression and query performance.

The immediate SQL analytical publication target is the combined Gold
zone-hourly fact.

---

## Referential Integrity

Fact tables reference conformed dimensions through foreign keys.

No cascading deletes are used.

Role-playing dimensions support:

- Taxi pickup/dropoff date
- Taxi pickup/dropoff time
- Taxi pickup/dropoff zone
- 311 created/closed date
- 311 created/closed time

Power BI can reuse the same conformed dimensional model.

---

## Reproducible Phase 15 Assets

SQL scripts:

1. `01_create_schemas.sql`
2. `02_create_dimensions.sql`
3. `03_create_fact_tables.sql`
4. `04_add_foreign_keys.sql`
5. `05_create_etl_audit_tables.sql`
6. `06_seed_core_dimensions.sql`
7. `07_load_reference_dimensions.sql`
8. `08_create_gold_load_objects.sql`
9. `09_validate_phase15.sql`

Python loader:

`python/load_gold_to_azure_sql.py`

These assets allow the Phase 15 warehouse implementation to be reviewed
and reproduced without storing Azure credentials in Git.

---

## Phase 15 Result

Phase 15 is complete.

The project now has:

- Azure SQL dimensional warehouse
- conformed dimensions
- fact-table structures
- enforced foreign keys
- clustered columnstore analytical storage
- idempotent Gold loading
- monthly ETL audit history
- reconciliation controls
- full-year Gold publication
- exact source-to-target reconciliation
