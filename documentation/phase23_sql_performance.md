# Phase 23 - SQL Performance Optimization

Status: VALIDATED

## Objective

Select at least three analytical SQL queries, measure their original
performance, inspect actual execution plans, identify bottlenecks, apply
optimizations, re-run the queries, and compare the results.

Execution environment:

    Azure SQL
    NYC_Urban_Intelligence_DW

Primary Gold fact:

    dw.FactZoneHourlyActivity

Gold rows:

    2,303,880

Three Phase 22 analytical queries were selected:

    Q5  - Month-over-month taxi-demand growth
    Q14 - Simultaneous taxi-demand and complaint spikes
    Q15 - 7-day rolling taxi-demand average


===============================================================================
OPTIMIZATION ASSET
===============================================================================

A reusable aggregate was introduced:

    dw.AggZoneDailyActivity

Grain:

    Zone x Date

Rows:

    95,995

Reconciliation:

    263 authoritative zones
    x 365 days
    = 95,995 rows

Primary key:

    (zone_key, date_key)

The table reduces repeated analytical scans from:

    2,303,880 Zone x Date x Hour rows

to:

    95,995 Zone x Date rows

for analyses whose natural grain is daily.

The aggregate is an analytical optimization structure rather than a
replacement for the authoritative Gold fact.

For future monthly loads, this aggregate should be refreshed or maintained
as part of the analytical warehouse load process.


===============================================================================
Q14 - SIMULTANEOUS TAXI AND COMPLAINT SPIKES
===============================================================================

Original performance:

    CPU time:             563 ms
    Elapsed time:         561 ms
    Logical reads:        7,413
    LOB logical reads:    1,110
    Physical reads:       0
    Rows returned:        230

Original execution-plan bottlenecks:

    Hash Match Aggregate             ~48%
    Clustered Columnstore Scan       ~27%
    Sort                             ~19%

First optimization attempt:

A nonclustered covering index was tested on:

    (zone_key, date_key)

including:

    taxi_trips
    complaints_311

Result:

    CPU time:             531 ms
    Elapsed time:         557 ms
    Logical reads:        unchanged

SQL Server continued to select the clustered columnstore scan.

The experimental index was therefore removed.

Second optimization attempt:

The daily aggregate was used while retaining multiple window statistics.

Result:

    CPU time:             703 ms
    Elapsed time:         706 ms
    Worktable reads:      196,462

This was slower because window/spool processing replaced the original scan
as the dominant cost.

Final optimization:

Zone-level statistics were calculated once with GROUP BY and joined back to
the daily aggregate rather than repeatedly calculated through window
statistics.

Final performance:

    CPU time:             187 ms
    Elapsed time:         198 ms
    Aggregate reads:      1,126
    Worktable reads:      0
    Physical reads:       0
    Rows returned:        230

Improvement:

    CPU reduction:        ~66.8%
    Elapsed reduction:    ~64.7%

Result-set cardinality remained unchanged.

Status:

    SUCCESS


===============================================================================
Q15 - 7-DAY ROLLING TAXI DEMAND
===============================================================================

Original performance:

    CPU time:             1,093 ms
    Elapsed time:         1,642 ms
    Logical reads:        7,413
    LOB logical reads:    861
    Physical reads:       0
    Worktable reads:      0
    Rows returned:        95,995

Original plan included:

    Hash Match Aggregate
    Clustered Columnstore Scan
    Sort
    Window Spool
    Window Aggregate

Optimization:

The query was rewritten to read directly from:

    dw.AggZoneDailyActivity

This removes the repeated aggregation of the 2,303,880-row hourly Gold fact
because the required Zone x Date grain already exists.

Optimized performance:

    CPU time:             1,063 ms
    Elapsed time:         1,611 ms
    Aggregate reads:      563
    LOB logical reads:    0
    Physical reads:       0
    Worktable reads:      0
    Rows returned:        95,995

Improvement:

    Logical-read reduction:       ~92.4%
    LOB-read reduction:           100%
    CPU reduction:                ~2.7%
    Elapsed reduction:            ~1.9%

Interpretation:

The optimization substantially reduced database I/O.

Runtime changed only slightly because the remaining cost is dominated by
the rolling-window calculation, final sorting, and returning 95,995 rows
to the client.

Status:

    SUCCESS - I/O OPTIMIZATION


===============================================================================
Q5 - MONTH-OVER-MONTH TAXI-DEMAND GROWTH
===============================================================================

Original performance:

    CPU time:             422 ms
    Elapsed time:         442 ms
    Logical reads:        7,413
    LOB logical reads:    861
    Physical reads:       0
    Worktable reads:      0
    Rows returned:        114

Original plan bottlenecks:

    Hash Match Aggregate             ~57%
    Clustered Columnstore Scan       ~26%
    Sort operators

Optimization:

The monthly calculation was changed to aggregate from:

    dw.AggZoneDailyActivity

instead of scanning and aggregating the entire hourly Gold fact.

LAG and DENSE_RANK analytical semantics were preserved.

Optimized performance:

    CPU time:             172 ms
    Elapsed time:         180 ms
    Aggregate reads:      563
    LOB logical reads:    0
    Physical reads:       0
    Worktable reads:      0
    Rows returned:        114

Improvement:

    Logical-read reduction:       ~92.4%
    LOB-read reduction:           100%
    CPU reduction:                ~59.2%
    Elapsed reduction:            ~59.3%

Status:

    SUCCESS


===============================================================================
SUMMARY
===============================================================================

Query   Original    Optimized    Main result
-----   --------    ---------    ----------------------------------------------
Q5      442 ms      180 ms       ~59.3% faster
Q14     561 ms      198 ms       ~64.7% faster
Q15     1642 ms     1611 ms      ~92.4% lower source logical reads

Techniques demonstrated:

- Execution-plan analysis
- STATISTICS IO
- STATISTICS TIME
- Pre-aggregation
- Reduced scans
- Reduced source-row volume
- Join rewrite
- GROUP BY rewrite
- Window-processing analysis
- Index experimentation
- Removal of ineffective index
- Reusable analytical aggregate design

Execution plans preserved under:

    reports/sql_performance/execution_plans/

Files:

    q05_original.sqlplan
    q05_optimized.sqlplan
    q14_original.sqlplan
    q14_optimized.sqlplan
    q15_original.sqlplan
    q15_optimized.sqlplan

Detailed benchmark notes:

    reports/sql_performance/q05_mom_growth_optimization.md
    reports/sql_performance/q14_spike_optimization.md
    reports/sql_performance/q15_rolling_optimization.md

Reproducible SQL:

    sql/phase23/01_create_daily_aggregate.sql
    sql/phase23/02_optimized_queries.sql

Phase 23 requirement:

    Optimize at least three slower analytical queries and capture
    before/after evidence.

Implemented:

    3 queries
    6 actual execution plans
    before/after STATISTICS IO/TIME
    documented bottlenecks
    documented optimization decisions

Status:

    VALIDATED
