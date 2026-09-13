# Phase 23 - Q15 7-Day Rolling Taxi Demand

## Original Query

Source:
dw.FactZoneHourlyActivity

The original query scanned the hourly Gold fact and aggregated it to:

    Zone x Date

before computing the 7-day rolling average.

Gold rows scanned:

    2,303,880

Rows returned:

    95,995

### Baseline Performance

FactZoneHourlyActivity:
- Logical reads: 7,413
- LOB logical reads: 861
- Physical reads: 0

Worktable logical reads:
0

CPU time:
1,093 ms

Elapsed time:
1,642 ms

Primary execution-plan costs included:

- Hash Match Aggregate: approximately 38%
- Clustered Columnstore Scan: approximately 18%
- Sort: approximately 16%
- Window Spool and Window Aggregate processing

## Optimization

The query was rewritten to use:

    dw.AggZoneDailyActivity

This table is already stored at the required:

    Zone x Date

grain.

Therefore, the optimized query avoids rescanning and re-aggregating
2,303,880 hourly Gold rows.

The clustered key:

    (zone_key, date_key)

also matches the logical partition/order required by the rolling calculation.

## Optimized Performance

AggZoneDailyActivity:
- Logical reads: 563
- LOB logical reads: 0
- Physical reads: 0

Worktable logical reads:
0

CPU time:
1,063 ms

Elapsed time:
1,611 ms

Rows returned:
95,995

## Improvement

Logical reads:

    7,413 -> 563
    approximately 92.4% reduction

LOB logical reads:

    861 -> 0
    100% reduction

CPU:

    1,093 ms -> 1,063 ms
    approximately 2.7% reduction

Elapsed:

    1,642 ms -> 1,611 ms
    approximately 1.9% reduction

The output remained identical at 95,995 rows.

## Interpretation

Pre-aggregation removed most source-data I/O.

However, elapsed time improved only slightly because the optimized query
still performs the rolling-window calculation, final sorting, and returns
95,995 rows to the SQL client.

The optimized execution plan shows that the performance bottleneck shifted
from scanning/aggregating the hourly fact table toward the final sort and
window-processing stages.

## Techniques

- Pre-aggregation
- Reduced scans
- Grain-aligned analytical table
- Reuse of clustered ordering
- Reduced I/O

Status:

SUCCESS - I/O OPTIMIZATION
