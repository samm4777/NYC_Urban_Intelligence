# Phase 2 — Data Acquisition

## Status

COMPLETE

## Yellow Taxi

- Source: NYC Taxi & Limousine Commission
- Year: 2025
- Monthly files acquired: 12
- Format: Parquet
- Total records: 48,722,602
- Raw storage pattern: `data/raw/taxi/year=2025/month=MM/`
- Acquisition manifest: `reports/acquisition/taxi_download_manifest.csv`
- Download metadata includes file name, source URL, month, retrieval timestamp, file size, row count, run ID, and status.

## Taxi Zones

The following official TLC reference assets were acquired:

- Taxi Zone lookup CSV
- Taxi Zone geographic shapefile archive
- Extracted SHP, SHX, DBF, PRJ and CPG files

Raw location:

`data/raw/taxi_zones/`

Acquisition manifest:

`reports/acquisition/taxi_zone_download_manifest.csv`

## NYC 311 Service Requests

- Year acquired: 2025
- Acquisition method: Socrata API
- Pagination size: 50,000 records
- Monthly partitioning: January through December
- Raw JSON pages: 80
- Total downloaded records: 3,655,040
- Official API count: 3,655,040
- Reconciliation difference: 0

Manifest tracks:

- Query range
- Page size
- Offset
- Page number
- Row count
- Retrieval timestamp
- Run ID
- Status

Raw storage pattern:

`data/raw/complaints_311/year=2025/month=MM/`

## Weather

- Source: Open-Meteo Historical Weather API
- Location: New York City
- Coordinates: 40.7128, -74.0060
- Timezone: America/New_York
- Year: 2025
- Grain: Hourly
- Monthly files: 12
- Total hourly observations: 8,760
- Unique timestamps: 8,760
- Integrity errors: 0

Variables acquired include temperature, relative humidity, apparent temperature, precipitation, rain, snowfall, weather code, wind speed, and wind gusts.

Raw storage pattern:

`data/raw/weather/year=2025/month=MM/`

## Acquisition Logging

Acquisition runs use structured run logging containing:

- source
- processing_month
- rows_read
- run_id
- status
- timestamps
- validation/rejection counts
- error information

Runtime log:

`logs/pipeline_runs.jsonl`

## Phase 2 Result

All required 2025 source datasets have been successfully acquired and validated.

Phase 2 is complete.