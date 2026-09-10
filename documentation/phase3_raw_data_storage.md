@'
# Phase 3 — Raw Data Storage

## Status

COMPLETE

## Objective

The Raw layer stores acquired source data without business transformations, cleansing, filtering, aggregation, deduplication, column renaming, or manual editing.

Raw datasets are treated as immutable source records.

## Raw Storage Structure

The project uses source, year, and month partitioning where applicable.

```text
data/raw/
├── taxi/
│   └── year=2025/
│       ├── month=01/
│       ├── month=02/
│       └── ...
│
├── complaints_311/
│   └── year=2025/
│       ├── month=01/
│       ├── month=02/
│       └── ...
│
├── weather/
│   └── year=2025/
│       ├── month=01/
│       ├── month=02/
│       └── ...
│
└── taxi_zones/