# Phase 22 - SQL Analysis

Status: VALIDATED

## Objective

Create at least 15 meaningful analytical SQL questions against the NYC Urban Intelligence dimensional warehouse.

The analytical SQL is stored at:

    sql/phase22/01_sql_analysis.sql

## Execution Environment

Queries were executed against the populated Azure SQL warehouse:

    Server:
    retailanalytics-sameer-484848.database.windows.net

    Database:
    NYC_Urban_Intelligence_DW

Primary analytical fact:

    dw.FactZoneHourlyActivity

## Full-Year Dataset Validation

The analytical warehouse contains the complete 2025 Gold dataset:

    Gold rows:       2,303,880
    Distinct dates:  365
    Distinct months: 12
    First date:      2025-01-01
    Last date:       2025-12-31

The Gold grain is:

    Date + Hour + Taxi Zone

The 2,303,880 rows reconcile exactly to:

    365 days
    x 24 hours
    x 263 authoritative taxi zones
    = 2,303,880 rows

Full-year analytical totals include:

    Taxi trips:      48,617,295
    311 complaints:  3,603,396
    Taxi revenue:    1,306,369,662.27

## Analytical Questions

1. Which taxi zones have the highest overall taxi demand?
2. Which hours of the day are busiest for taxi demand?
3. Which taxi zones generate the most revenue?
4. Which borough has the highest weighted average taxi fare?
5. Which zones show the strongest month-over-month taxi-demand growth?
6. How does taxi demand change during rainy versus dry conditions?
7. How does snowfall correspond with taxi activity?
8. Among the highest-demand zones, which also generate the most 311 complaints?
9. Which zones have high complaint activity but comparatively low taxi demand?
10. Which hours generate the highest taxi revenue?
11. How does weekday taxi demand compare with weekend demand?
12. Which zones show the greatest hourly revenue volatility?
13. Which zones show the most consistently increasing complaint activity month-over-month?
14. Which zone/date combinations show simultaneous taxi-demand and complaint spikes?
15. What is the 7-day rolling average taxi demand for each zone?
16. How do taxi zones rank by revenue within their own borough?
17. How does taxi activity vary across recorded weather conditions?

## SQL Techniques Demonstrated

The analysis demonstrates:

- Common Table Expressions (CTEs)
- LAG
- Window functions
- DENSE_RANK
- NTILE
- Ranking within partitions
- Rolling-window calculations
- Joins between fact and dimension tables
- SUM, AVG, COUNT, COUNT_BIG, MAX
- Standard deviation
- Date aggregation
- Month-over-month analysis
- Weekday/weekend analysis
- CASE expressions
- NULLIF for safe division
- Weather segmentation
- Z-score based spike detection

## Key Technique Examples

### CTEs

Used extensively for multi-stage analytical transformations, including monthly demand, complaint trends, volatility and spike detection.

### LAG

Used to compare current-month taxi activity and complaint activity with previous months.

### Ranking

DENSE_RANK and NTILE are used for:

- Monthly growth rankings
- Demand quartiles
- Complaint quartiles
- Revenue rankings within boroughs

### Window Functions

Used for:

- Previous-period calculations
- 7-day rolling averages
- Zone-level means
- Zone-level standard deviations
- Ranking

### CASE Logic

Used for:

- Rain versus dry classification
- Snowfall intensity bands
- Weekday versus weekend analysis
- High-complaint / low-demand zone classification

## Detailed Fact Tables

The dimensional schema also contains:

    dw.FactTaxiTrips
    dw.Fact311Complaints

These tables currently contain zero rows in Azure SQL.

Therefore, analyses requiring individual-trip fields such as:

- Tip amount
- Payment method

or individual complaint-level fields such as:

- Complaint type

were not included as production analytical queries.

This avoids presenting queries whose underlying facts are not populated.

The populated Gold fact contains the measures required for the primary cross-domain taxi, 311 and weather analyses.

## Validation Result

All 17 production analytical queries executed successfully in Azure SQL Server Management Studio against the full-year 2025 warehouse.

No query failed with:

- Invalid column errors
- Invalid table errors
- SQL syntax errors
- Join errors
- Window-function errors
- Aggregation errors

## Phase Result

Requirement:

    At least 15 analytical SQL queries

Implemented:

    17 analytical SQL queries

Status:

    VALIDATED
