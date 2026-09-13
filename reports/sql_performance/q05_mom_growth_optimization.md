# Phase 23 - Q5 Month-over-Month Taxi Demand Growth

## Original Query

Source:

    dw.FactZoneHourlyActivity

Gold rows scanned:

    2,303,880

Rows returned:

    114

### Baseline Performance

FactZoneHourlyActivity:
- Logical reads: 7,413
- LOB logical reads: 861
- Physical reads: 0

DimDate logical reads:
21

Worktable logical reads:
0

CPU time:
422 ms

Elapsed time:
442 ms

Major execution-plan costs included:

- Hash Match Aggregate: approximately 57%
- Clustered Columnstore Scan: approximately 26%
- Sort operators

The main cost was aggregating the full hourly Gold fact before applying
LAG and monthly growth ranking.

## Optimization

The optimized query uses:

    dw.AggZoneDailyActivity

The daily aggregate contains:

    95,995 rows

instead of:

    2,303,880 hourly Gold rows

Monthly aggregation is therefore performed from an already reduced
Zone x Date dataset.

The LAG and DENSE_RANK business logic remained unchanged.

## Optimized Performance

AggZoneDailyActivity:
- Logical reads: 563
- LOB logical reads: 0
- Physical reads: 0

DimDate logical reads:
21

Worktable logical reads:
0

CPU time:
172 ms

Elapsed time:
180 ms

Rows returned:
114

## Improvement

Logical reads:

    7,413 -> 563
    approximately 92.4% reduction

LOB logical reads:

    861 -> 0
    100% reduction

CPU:

    422 ms -> 172 ms
    approximately 59.2% reduction

Elapsed:

    442 ms -> 180 ms
    approximately 59.3% reduction

The analytical output remained unchanged at 114 rows.

## Techniques

- Pre-aggregation
- Reduced scans
- Reduced source-row volume
- Reuse of analytical aggregate
- Retained LAG and ranking semantics

Status:

SUCCESS
