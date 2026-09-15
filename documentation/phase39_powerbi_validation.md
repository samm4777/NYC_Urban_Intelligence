# Phase 39 — Power BI Validation

## Overview

Phase 39 independently validates key Power BI results against Azure SQL.

The objective is to ensure that the semantic model, DAX measures, relationships,
filters, and report visuals return the same results as the authoritative
warehouse.

Validation was performed against:

`dw.FactZoneHourlyActivity`

with the warehouse dimensions used by Power BI.

All tested metrics matched SQL exactly.

---

## 1. Full-Year KPI Validation

| Metric | SQL Result | Power BI Result | Difference | Match |
|---|---:|---:|---:|---|
| Total Taxi Trips | 48,617,295 | 48,617,295 | 0 | PASS |
| Total Revenue | $1,306,369,662.27 | $1,306,369,662.27 | $0.00 | PASS |
| Total Complaints | 3,603,396 | 3,603,396 | 0 | PASS |

Power BI dashboard cards display abbreviated values such as:

- Total Trips: 48.62M
- Total Revenue: $1.31bn
- Total Complaints: 3.60M

A temporary validation table was used with display units disabled to confirm
the exact underlying values.

---

## 2. Top Taxi Zone Validation

The SQL query ranked Taxi Zones by total pickup trips.

### Result

| Metric | SQL Result | Power BI Result | Difference | Match |
|---|---|---|---:|---|
| Top Taxi Zone | Upper East Side South | Upper East Side South | N/A | PASS |
| Top Taxi Zone Trips | 2,125,550 | 2,125,550 | 0 | PASS |

Power BI therefore correctly reproduces the warehouse ranking.

---

## 3. Selected Monthly Validation

Three representative months were selected from different parts of the year:

- January
- May
- August

Trips, revenue, and 311 complaints were independently compared.

### January 2025

| Metric | SQL Result | Power BI Result | Difference | Match |
|---|---:|---:|---:|---|
| Taxi Trips | 3,465,589 | 3,465,589 | 0 | PASS |
| Revenue | $88,653,301.50 | $88,653,301.50 | $0.00 | PASS |
| Complaints | 344,934 | 344,934 | 0 | PASS |

### May 2025

| Metric | SQL Result | Power BI Result | Difference | Match |
|---|---:|---:|---:|---|
| Taxi Trips | 4,582,056 | 4,582,056 | 0 | PASS |
| Revenue | $122,966,401.05 | $122,966,401.05 | $0.00 | PASS |
| Complaints | 289,747 | 289,747 | 0 | PASS |

### August 2025

| Metric | SQL Result | Power BI Result | Difference | Match |
|---|---:|---:|---:|---|
| Taxi Trips | 3,566,471 | 3,566,471 | 0 | PASS |
| Revenue | $93,940,545.09 | $93,940,545.09 | $0.00 | PASS |
| Complaints | 299,569 | 299,569 | 0 | PASS |

---

## 4. Monthly Control Validation

The SQL validation also confirmed that monthly Taxi totals reconcile to the
full-year total.

| Metric | Result |
|---|---:|
| Sum of Monthly Taxi Trips | 48,617,295 |
| Full-Year Taxi Trips | 48,617,295 |
| Variance | 0 |
| Status | PASS |

This verifies that the monthly aggregation used by Power BI preserves the
full-year warehouse total.

---

## 5. Visual Formatting Validation

Some report visuals intentionally use abbreviated display units.

Examples:

- 48,617,295 → 48.62M
- $1,306,369,662.27 → $1.31bn
- 2,125,550 → 2.13M

These are presentation-level formatting differences only.

Exact-value Power BI tables confirmed that the underlying DAX results match
Azure SQL without numerical variance.

---

## 6. Mismatch Investigation

No numerical or categorical mismatch was identified during Phase 39.

Therefore:

- No DAX correction was required.
- No relationship correction was required.
- No warehouse correction was required.
- No report filter correction was required.

All validated Power BI results are consistent with the authoritative Azure SQL
warehouse.

---

## 7. Validation Summary

| Validation Area | Status |
|---|---|
| Total Taxi Trips | PASS |
| Total Revenue | PASS |
| Total Complaints | PASS |
| Top Taxi Zone | PASS |
| Top Taxi Zone Trips | PASS |
| January Monthly Metrics | PASS |
| May Monthly Metrics | PASS |
| August Monthly Metrics | PASS |
| Monthly-to-Annual Control | PASS |

## Final Status

**PHASE 39 — PASS / COMPLETE**

---

## Implementation Files

SQL validation:

`sql/phase39/01_powerbi_validation.sql`

Documentation:

`documentation/phase39_powerbi_validation.md`