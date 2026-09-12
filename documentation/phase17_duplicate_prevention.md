# Phase 17 — Duplicate Prevention

## Status

**COMPLETE**

Phase 17 validates duplicate prevention and idempotent warehouse loading
for the NYC Urban Intelligence Platform.

## Business Keys

The warehouse uses explicit business or natural keys wherever reliable
source identifiers exist.

| Object | Business / Natural Key |
|---|---|
| FactZoneHourlyActivity | date_key + time_key + zone_key |
| Fact311Complaints | unique_key |
| DimDate | full_date |
| DimTime | hour_of_day |
| DimZone | location_id |
| DimPaymentType | payment_type_code |
| DimComplaintType | complaint_type |
| DimWeatherCondition | weather_code |

Taxi trip data does not expose a reliable unique source trip identifier.
Taxi duplicate prevention therefore relies on source-file/batch
idempotency and controlled ingestion rather than an invented trip key.

## Database Enforcement

Duplicate prevention is enforced through unique constraints and indexes.

Important examples include:

- UQ_FactZoneHourly_Grain
- UQ_Fact311Complaints_UniqueKey
- UQ_DimDate_FullDate
- UX_DimTime_HourOfDay
- UQ_DimZone_LocationID
- UQ_DimPaymentType_Code
- UQ_DimComplaintType_Name
- unique weather-code constraint

The Gold loading procedure also performs UPDATE + INSERT upsert logic
against the existing Date + Hour + Zone grain.

## Duplicate Audit

The Phase 17 validation returned:

- Gold rows: 2,303,880
- Distinct Gold business keys: 2,303,880
- Duplicate Gold grains: 0
- Duplicate 311 unique keys: 0
- Duplicate dimension natural keys: 0

Fact311Complaints is schema-ready but was not bulk-loaded during Phase
15. Its duplicate prevention is therefore currently guaranteed
structurally by its unique business-key constraint.

## Mandatory Same-Load-Twice Test

July 2025 was used for the mandatory test.

Baseline:

- full Gold fact rows: 2,303,880
- July rows: 195,672

The identical July source file was submitted again through the
incremental pipeline.

The processed-file registry recognized the same file version using its
source path and SHA-256 identity.

Result:

- Registry status: SUCCESS
- Action: SKIP
- Processed: 0
- Skipped: 1
- Run status: SUCCESS

After repeating the load:

- full Gold fact rows: 2,303,880
- July rows: 195,672

Therefore:

`row_count_before == row_count_after`

and no duplicate Date + Hour + Zone grain was introduced.

## Duplicate Prevention Layers

The platform now uses multiple defensive layers:

1. Source file SHA-256 identification
2. Processed-file registry
3. Idempotency keys in audit.LoadBatch
4. Deduplication/business-grain validation before load
5. Transactional upsert behavior
6. Unique SQL constraints
7. Post-load duplicate validation

This prevents duplicate creation even if the same monthly pipeline is
executed repeatedly.

## Phase 17 Assets

SQL:

- `sql/phase17/01_validate_duplicate_prevention.sql`
- `sql/phase17/02_validate_idempotent_rerun.sql`

Supporting loaders:

- `python/load_gold_to_azure_sql.py`
- `python/load_gold_incremental.py`

## Result

**Phase 17 — Duplicate Prevention: COMPLETE**

The warehouse preserves unique analytical grains and repeated execution
of the same source load does not increase warehouse row counts.
