# Phase 38 — Reconciliation

## Overview

Phase 38 validates that records have not disappeared unexpectedly while moving through the NYC Urban Intelligence Platform.

The reconciliation covers:

- Raw/Input → Silver validation
- Rejected/quarantined records
- Gold aggregation grain
- Taxi Silver → Gold representation
- 311 Silver → Gold representation
- Existing warehouse reconciliation checks

All reconciliation checks completed successfully with zero unexplained variance.

---

## 1. Record-Level Reconciliation

For record-level sources, the expected relationship is:

Raw Records = Silver Valid Records + Distinct Rejected Records

### Results

| Source | Raw Records | Silver Valid Records | Rejected Records | Variance | Status |
|---|---:|---:|---:|---:|---|
| Taxi | 48,722,602 | 48,720,337 | 2,265 | 0 | PASS |
| NYC 311 | 3,655,040 | 3,604,061 | 50,979 | 0 | PASS |
| Weather | 8,760 | 8,760 | 0 | 0 | PASS |

### Overall Reconciliation

| Metric | Count |
|---|---:|
| Total Raw Records | 52,386,402 |
| Total Valid Records | 52,333,158 |
| Total Rejected Records | 53,244 |
| Reconciliation Variance | 0 |
| Status | PASS |

Therefore:

52,386,402 = 52,333,158 + 53,244

No unexplained record loss was detected.

---

## 2. Quarantine Event Handling

Quarantine event counts are not always equal to distinct rejected record counts.

For NYC 311:

- Distinct rejected source records: 50,979
- Physical quarantine events: 51,062

The difference occurs because a single source record can fail more than one data-quality rule.

Record-level reconciliation therefore uses distinct rejected source records rather than quarantine event rows.

---

## 3. Gold Grain Reconciliation

The Gold analytical table is aggregated and therefore its physical row count is not expected to equal Silver row counts.

The authoritative Gold grain is:

Date × Hour × Taxi Zone

The platform contains:

- 263 authoritative Taxi Zones
- 8,760 hours in calendar year 2025

Expected Gold rows:

263 × 8,760 = 2,303,880

### Result

| Metric | Value |
|---|---:|
| Expected Gold Rows | 2,303,880 |
| Actual Gold Rows | 2,303,880 |
| Variance | 0 |
| Status | PASS |

The dense Gold grid is complete.

---

## 4. Taxi Silver → Gold Reconciliation

Valid Taxi Silver records:

48,720,337

The Gold spatial domain includes authoritative polygon-backed Taxi Zone IDs 1–263.

Taxi pickup Location IDs 264 and 265 are documented special/reference zones and are intentionally excluded from the spatial Gold aggregate.

### Reconciliation

| Metric | Count |
|---|---:|
| Silver Valid Taxi Records | 48,720,337 |
| Documented Zone 264/265 Exclusions | 103,042 |
| Expected Gold Taxi Trips | 48,617,295 |
| Actual SUM(Gold Taxi Trips) | 48,617,295 |
| Variance | 0 |
| Status | PASS |

Therefore:

48,720,337 - 103,042 = 48,617,295

The difference between Silver and Gold is fully explained by documented geographic-domain exclusions.

---

## 5. NYC 311 Silver → Gold Reconciliation

Valid NYC 311 Silver records:

3,604,061

Some valid 311 complaints cannot be represented in Taxi Zone-level Gold because their coordinates fall outside the authoritative Taxi Zone polygons.

### Reconciliation

| Metric | Count |
|---|---:|
| Silver 311 Records | 3,604,061 |
| Outside Taxi Zone Polygon Exclusions | 665 |
| Expected Gold 311 Complaints | 3,603,396 |
| Actual SUM(Gold 311 Complaints) | 3,603,396 |
| Variance | 0 |
| Status | PASS |

Therefore:

3,604,061 - 665 = 3,603,396

No unexplained 311 record loss was detected.

---

## 6. Warehouse Reconciliation Health

The existing warehouse reconciliation framework was also validated.

### Result

| Metric | Value |
|---|---:|
| Reconciliation Metric | zone_hourly_rows |
| Total Checks | 24 |
| Passed Checks | 24 |
| Failed Checks | 0 |
| Maximum Absolute Variance | 0.000000 |
| Status | PASS |

All warehouse reconciliation checks passed.

---

## 7. Phase 38 Validation Summary

Phase 38 successfully proves:

- Raw records reconcile to valid plus rejected records.
- Quarantine-event duplication is explicitly accounted for.
- Gold row count follows the defined Date × Hour × Zone grain.
- Taxi Gold totals reconcile to Silver after documented special-zone exclusions.
- 311 Gold totals reconcile after documented spatial exclusions.
- Existing warehouse reconciliation checks show zero variance.
- No unexplained record loss was detected.

## Final Status

**PHASE 38 — PASS / COMPLETE**

---

## Implementation Files

SQL validation:

`sql/phase38/01_reconciliation.sql`

Documentation:

`documentation/phase38_reconciliation.md`