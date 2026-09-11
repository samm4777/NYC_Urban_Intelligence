# Phase 16 — Incremental Loading

## Status

**COMPLETE**

Phase 16 implements incremental monthly loading for the NYC Urban Intelligence Platform.

## Incremental Controls

The implementation uses:

- Monthly source partitions
- `etl.ProcessedFileRegistry`
- SHA-256 file-version identification
- `etl.LoadWatermark`
- `audit.LoadBatch`
- Last-successful-load tracking
- Idempotent reruns
- Recovery of interrupted loads

## Mandatory Incremental Test

January through June were processed first.

After that, the loader was executed against January through July.

Result:

- January — SKIPPED
- February — SKIPPED
- March — SKIPPED
- April — SKIPPED
- May — SKIPPED
- June — SKIPPED
- July — PROCESSED

Run summary:

- Processed: 1
- Skipped: 6
- Status: SUCCESS

This proves that previously processed January–June partitions were not unnecessarily rebuilt when July became available.

The watermark advanced from:

`2025-06-30 23:59:59.999`

to:

`2025-07-31 23:59:59.999`

## Failure Recovery Test

During October processing, the Azure SQL connection failed with:

`08S01 Communication link failure`

At that point:

- October remained incomplete
- the audit batch remained STARTED
- the processed-file registry remained PROCESSING
- 155,000 staging rows had already been committed

The incremental loader was rerun.

It:

- skipped already successful August and September
- detected the incomplete October load
- cleared the partial October staging rows
- reprocessed October successfully
- continued with November and December

This validates recovery from an interrupted monthly load.

## Final Incremental State

Processed-file registry:

- SUCCESS files: 12
- incomplete/failed files: 0

Final watermark:

`2025-12-31 23:59:59.999`

Incremental audit:

- successful batches: 12
- rows read: 2,303,880
- rows inserted: 0
- rows updated: 2,303,880
- rows rejected: 0

Phase 15 had already loaded the complete 2025 Gold dataset, so Phase 16 replayed existing monthly grains as updates rather than inserts.

The purpose of Phase 16 was to validate:

- incremental file discovery
- processed-file tracking
- monthly partition handling
- selective processing
- idempotency
- watermark advancement
- interrupted-load recovery

All required controls passed.

## Phase 16 Assets

Python:

`python/load_gold_incremental.py`

SQL:

`sql/phase16/01_create_incremental_controls.sql`

`sql/phase16/02_validate_incremental_loading.sql`

No Azure password or connection secret is stored in Git.

## Result

**Phase 16 — Incremental Loading: COMPLETE**
