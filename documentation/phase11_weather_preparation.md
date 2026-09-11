# Phase 11 — Weather Data Preparation

## Status

COMPLETE

## Objective

Prepare the full-year 2025 Open-Meteo weather dataset for analytical use at an hourly grain compatible with the planned Gold dataset.

## Source

Open-Meteo historical weather data.

Timezone requested during acquisition:

`America/New_York`

The returned hourly timestamps are preserved as NYC local wall-clock timestamps so they remain compatible with the project's hourly Taxi and Gold analytical grain.

## Raw Input

Location:

`data/raw/weather/year=2025/month=MM`

Raw files:

`12`

Full-year Raw rows:

`8,760`

Expected hourly rows for non-leap-year 2025:

`8,760`

## Silver Output

Location:

`data/silver/weather/year=2025/month=MM`

Grain:

`1 row = 1 NYC local weather hour`

Full-year Silver rows:

`8,760`

## Prepared Fields

Core analytical weather fields:

- `weather_timestamp`
- `weather_date`
- `weather_hour`
- `weather_timezone`
- `temperature_c`
- `rain_mm`
- `snowfall_cm`
- `wind_speed_kmh`
- `weather_code`
- `weather_condition`

Additional retained measurements:

- `relative_humidity_pct`
- `apparent_temperature_c`
- `precipitation_mm`
- `wind_gust_kmh`

Source metadata:

- `source_latitude`
- `source_longitude`
- `source_elevation_m`

Audit metadata:

- `_source`
- `_source_file`
- `_run_id`
- `_processed_at`
- `_processing_year`
- `_processing_month`

## Weather Condition Mapping

`weather_code` is translated into a readable `weather_condition` using the WMO interpretation used by Open-Meteo.

Examples include:

- 0 -> Clear sky
- 1 -> Mainly clear
- 2 -> Partly cloudy
- 3 -> Overcast
- 51 -> Light drizzle
- 53 -> Moderate drizzle
- 55 -> Dense drizzle
- 61 -> Slight rain
- 63 -> Moderate rain
- 71 -> Slight snowfall
- 73 -> Moderate snowfall
- 75 -> Heavy snowfall

January validation confirmed that all observed weather codes were successfully mapped.

## Units

The Silver layer uses the source weather units explicitly:

- Temperature: Celsius
- Apparent temperature: Celsius
- Precipitation: millimetres
- Rain: millimetres
- Snowfall: centimetres
- Wind speed: kilometres per hour
- Wind gust: kilometres per hour
- Relative humidity: percent

## Weather Gap Policy

Weather gaps must never be silently filled.

Phase 11 compares each monthly source against the complete expected hourly grid.

If an expected hour is absent:

1. the missing timestamp is written to:

   `reports/reconciliation/weather_gap_report.csv`

2. the Silver publication fails;

3. no interpolation is performed;

4. no forward-fill or backward-fill is performed;

5. no synthetic weather record is created.

For valid published weather rows:

`is_weather_gap = False`

An absent hour has no physical source row on which to store `True`, therefore missing hours are represented in the dedicated gap report.

## Data Quality Controls

The Phase 11 implementation remains consistent with the Phase 7 Data Quality rules.

Validated controls include:

- DQ_WEATHER_001 — Missing Expected Hour
- DQ_WEATHER_002 — Duplicate Weather Timestamp
- DQ_WEATHER_003 — Invalid Weather Measurement
- DQ_WEATHER_004 — Weather Timestamp Outside 2025
- DQ_WEATHER_005 — Weather Schema Mismatch

Phase 8 Weather quarantine events:

`0`

Phase 11 validation also found:

- Missing hours: `0`
- Duplicate timestamps: `0`
- Unexpected timestamps: `0`
- Invalid measurements: `0`
- Unmapped weather codes: `0`

## January Validation

January contained:

`744`

hourly records.

Validation confirmed:

- 744 rows;
- 744 unique timestamps;
- minimum timestamp `2025-01-01 00:00:00`;
- maximum timestamp `2025-01-31 23:00:00`;
- zero duplicate timestamps;
- zero core-field nulls;
- zero weather gaps;
- correct WMO condition decoding.

## Monthly Silver Row Counts

| Month | Rows |
|---|---:|
| January | 744 |
| February | 672 |
| March | 744 |
| April | 720 |
| May | 744 |
| June | 720 |
| July | 744 |
| August | 744 |
| September | 720 |
| October | 744 |
| November | 720 |
| December | 744 |

Total:

`8,760`

## Full-Year Reconciliation

| Metric | Value |
|---|---:|
| Months | 12 |
| Raw rows | 8,760 |
| Silver rows | 8,760 |
| Missing hours | 0 |
| Duplicate timestamps | 0 |
| Unexpected timestamps | 0 |
| Invalid measurements | 0 |
| Gap report rows | 0 |

Result:

`PASS`

## Implementation

Transformation:

`python/prepare_weather_silver.py`

Reconciliation report:

`reports/reconciliation/weather_silver_reconciliation.csv`

Gap report:

`reports/reconciliation/weather_gap_report.csv`

Pipeline log:

`logs/pipeline_runs.jsonl`

## Phase 11 Result

Phase 11 is COMPLETE.

The project now contains a complete, hourly, analysis-ready 2025 Weather Silver dataset suitable for hourly Gold-layer joins.

Final Silver rows:

`8,760`

Final reconciliation:

`PASS`

The next roadmap stage is:

**Phase 12 — Geospatial Preparation**
