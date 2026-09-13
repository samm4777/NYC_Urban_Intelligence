# Phase 23 - Q14 Simultaneous Taxi and Complaint Spikes

## Original query

Source:
dw.FactZoneHourlyActivity

Input grain:
Zone x Date x Hour

Rows in Gold:
2,303,880

### Baseline

CPU time: 563 ms
Elapsed time: 561 ms

FactZoneHourlyActivity:
- Logical reads: 7,413
- LOB logical reads: 1,110
- Physical reads: 0
- Columnstore segments read: 2
- Segments skipped: 0

Execution-plan bottlenecks:

- Hash Match Aggregate: approximately 48%
- Clustered Columnstore Scan: approximately 27%
- Sort: approximately 19%

Rows returned:
230

## Index attempt

A covering nonclustered index on:

    zone_key, date_key

including:

    taxi_trips, complaints_311

did not materially improve performance.

Result:

CPU time: 531 ms
Elapsed time: 557 ms
Logical reads: unchanged

SQL Server continued to select the clustered columnstore scan.

Conclusion:
The query processes almost the entire fact table, so the rowstore index did not provide a meaningful advantage.

## First pre-aggregation attempt

Created:

    dw.AggZoneDailyActivity

Grain:

    Zone x Date

Rows:

    95,995

The first rewrite retained four window calculations.

Result:

CPU time: 703 ms
Elapsed time: 706 ms
Worktable logical reads: 196,462

Although source-table reads dropped, Table Spool / window-processing overhead made the query slower.

## Final optimization

The final rewrite:

1. Uses the 95,995-row daily aggregate.
2. Calculates zone statistics once with GROUP BY.
3. Joins the zone statistics back to daily activity.
4. Removes the repeated window-statistics workload.

Final result:

CPU time: 187 ms
Elapsed time: 198 ms
AggZoneDailyActivity logical reads: 1,126
Worktable logical reads: 0
Physical reads: 0
Rows returned: 230

## Improvement

CPU reduction:

    563 ms -> 187 ms
    approximately 66.8% reduction

Elapsed-time reduction:

    561 ms -> 198 ms
    approximately 64.7% reduction

The result set remained unchanged at 230 spike observations.

## Optimization techniques

- Pre-aggregation
- Reduced source-row volume
- GROUP BY instead of repeated window statistics
- Reduced intermediate processing
- Elimination of excessive spool/worktable activity

Status:

SUCCESS
