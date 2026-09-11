#!/usr/bin/env python
"""
Phase 13 - Build the combined Gold zone-hourly analytical dataset.

Authoritative Gold grain:
    1 row = 1 NYC local calendar date + 1 hour + 1 TLC Taxi Zone polygon

Zone domain:
    TLC polygon-backed LocationID 1..263 only.

Important exclusions / audit behavior:
- Taxi pickup LocationID 264 ("Unknown") and 265 ("Outside of NYC") are excluded
  from the spatial Gold table but explicitly reconciled.
- Any Taxi pickup LocationID outside 1..265 causes publication failure.
- 311 records with spatial_mapping_status != MAPPED are excluded from the
  zone-level complaint aggregate but explicitly reconciled.
- Missing Weather hours cause publication failure; Weather is never silently
  imputed.
- Zones with no Taxi trips or 311 complaints remain in the dense Gold grid.
"""

from __future__ import annotations

import argparse
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[1]

TAXI_ROOT = PROJECT_ROOT / "data" / "silver" / "taxi" / "year=2025"
COMPLAINT_ROOT = (
    PROJECT_ROOT
    / "data"
    / "silver"
    / "complaints_311_mapped"
    / "year=2025"
)
WEATHER_ROOT = PROJECT_ROOT / "data" / "silver" / "weather" / "year=2025"

ZONE_LOOKUP = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "taxi_zones"
    / "taxi_zone_lookup.csv"
)

OUTPUT_ROOT = (
    PROJECT_ROOT
    / "data"
    / "gold"
    / "zone_hourly"
    / "year=2025"
)

RECONCILIATION_REPORT = (
    PROJECT_ROOT
    / "reports"
    / "reconciliation"
    / "gold_zone_hourly_reconciliation.csv"
)

SUMMARY_JSON = (
    PROJECT_ROOT
    / "reports"
    / "gold"
    / "phase13_zone_hourly_summary.json"
)

RUN_LOG = PROJECT_ROOT / "logs" / "pipeline_runs.jsonl"

YEAR = 2025
ZONE_MIN = 1
ZONE_MAX = 263
SPECIAL_IDS = {264, 265}
EXPECTED_ZONE_COUNT = 263
EXPECTED_WEATHER_HOURS = 8760
EXPECTED_FULL_YEAR_GOLD_ROWS = EXPECTED_ZONE_COUNT * EXPECTED_WEATHER_HOURS

EXPECTED_TAXI_SILVER_ROWS = 48_720_337
EXPECTED_TAXI_GOLD_DOMAIN_ROWS = 48_617_295
EXPECTED_TAXI_SPECIAL_ROWS = 103_042
EXPECTED_TAXI_CROSS_PARTITION_ROWS = 185

EXPECTED_311_MAPPED_SILVER_ROWS = 3_604_061
EXPECTED_311_SPATIALLY_MAPPED_ROWS = 3_603_396
EXPECTED_311_OUTSIDE_ROWS = 665

MAPPED_STATUS = "MAPPED"
OUTSIDE_STATUS = "OUTSIDE_TAXI_ZONE_POLYGONS"

GOLD_SCHEMA = pa.schema(
    [
        pa.field("date", pa.date32(), nullable=False),
        pa.field("hour", pa.int32(), nullable=False),
        pa.field("taxi_zone_id", pa.int32(), nullable=False),
        pa.field("taxi_zone_name", pa.string(), nullable=False),
        pa.field("borough", pa.string(), nullable=False),
        pa.field("taxi_trips", pa.int64(), nullable=False),
        pa.field("taxi_revenue", pa.float64(), nullable=False),
        pa.field("average_fare", pa.float64(), nullable=True),
        pa.field("average_trip_distance", pa.float64(), nullable=True),
        pa.field("complaints_311", pa.int64(), nullable=False),
        pa.field("temperature_c", pa.float64(), nullable=False),
        pa.field("rain_mm", pa.float64(), nullable=False),
        pa.field("snowfall_cm", pa.float64(), nullable=False),
        pa.field("weather_condition", pa.string(), nullable=False),
        pa.field("_run_id", pa.string(), nullable=False),
        pa.field("_processed_at", pa.timestamp("us"), nullable=False),
        pa.field("_processing_year", pa.int32(), nullable=False),
        pa.field("_processing_month", pa.int32(), nullable=False),
    ]
)


def write_run_log(record: dict) -> None:
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RUN_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


def month_folder(root: Path, month: int) -> Path:
    return root / f"month={month:02d}"


def expected_month_hours(month: int) -> pd.DatetimeIndex:
    start = pd.Timestamp(YEAR, month, 1, 0, 0, 0)
    days_in_month = pd.Period(
        f"{YEAR}-{month:02d}",
        freq="M",
    ).days_in_month

    return pd.date_range(
        start=start,
        periods=days_in_month * 24,
        freq="h",
    )


def load_zone_dimension() -> pd.DataFrame:
    if not ZONE_LOOKUP.exists():
        raise FileNotFoundError(f"Taxi Zone lookup not found: {ZONE_LOOKUP}")

    zones = pd.read_csv(ZONE_LOOKUP)

    required = {"LocationID", "Borough", "Zone"}
    missing = required - set(zones.columns)
    if missing:
        raise RuntimeError(
            f"ZONE_LOOKUP_SCHEMA_FAILURE: missing columns {sorted(missing)}"
        )

    zones = zones[
        zones["LocationID"].between(ZONE_MIN, ZONE_MAX)
    ][["LocationID", "Borough", "Zone"]].copy()

    if len(zones) != EXPECTED_ZONE_COUNT:
        raise RuntimeError(
            f"ZONE_DOMAIN_FAILURE: expected {EXPECTED_ZONE_COUNT} polygon zones, "
            f"found {len(zones)}"
        )

    if zones["LocationID"].nunique() != EXPECTED_ZONE_COUNT:
        raise RuntimeError("ZONE_DOMAIN_FAILURE: duplicate polygon LocationID")

    if zones["LocationID"].isna().any():
        raise RuntimeError("ZONE_DOMAIN_FAILURE: null LocationID")

    if zones["Zone"].isna().any():
        raise RuntimeError("ZONE_DOMAIN_FAILURE: null Zone name in IDs 1..263")

    if zones["Borough"].isna().any():
        raise RuntimeError("ZONE_DOMAIN_FAILURE: null Borough in IDs 1..263")

    observed = set(zones["LocationID"].astype(int))
    expected = set(range(ZONE_MIN, ZONE_MAX + 1))
    if observed != expected:
        raise RuntimeError(
            "ZONE_DOMAIN_FAILURE: lookup does not contain exact LocationIDs 1..263"
        )

    zones = zones.rename(
        columns={
            "LocationID": "taxi_zone_id",
            "Zone": "taxi_zone_name",
            "Borough": "borough",
        }
    )

    zones["taxi_zone_id"] = zones["taxi_zone_id"].astype("int32")
    zones["taxi_zone_name"] = zones["taxi_zone_name"].astype(str)
    zones["borough"] = zones["borough"].astype(str)

    return zones.sort_values("taxi_zone_id").reset_index(drop=True)


def reduce_partial_taxi_aggregates(parts: list[pd.DataFrame]) -> pd.DataFrame:
    if not parts:
        return pd.DataFrame(
            columns=[
                "date",
                "hour",
                "taxi_zone_id",
                "taxi_trips",
                "taxi_revenue",
                "_fare_sum",
                "_fare_count",
                "_distance_sum",
                "_distance_count",
            ]
        )

    combined = pd.concat(parts, ignore_index=True)

    reduced = (
        combined.groupby(
            ["date", "hour", "taxi_zone_id"],
            as_index=False,
            sort=False,
            observed=True,
        )
        .agg(
            taxi_trips=("taxi_trips", "sum"),
            taxi_revenue=("taxi_revenue", "sum"),
            _fare_sum=("_fare_sum", "sum"),
            _fare_count=("_fare_count", "sum"),
            _distance_sum=("_distance_sum", "sum"),
            _distance_count=("_distance_count", "sum"),
        )
    )

    reduced["average_fare"] = (
        reduced["_fare_sum"] / reduced["_fare_count"]
    )
    reduced["average_trip_distance"] = (
        reduced["_distance_sum"] / reduced["_distance_count"]
    )

    return reduced[
        [
            "date",
            "hour",
            "taxi_zone_id",
            "taxi_trips",
            "taxi_revenue",
            "average_fare",
            "average_trip_distance",
        ]
    ]



def audit_taxi_temporal_routing() -> dict:
    """
    Validate the physical Taxi month partitions against the actual pickup_date.

    Gold month membership is controlled by pickup_date, never by the physical
    source partition. The 2025 audit established 185 cross-partition rows, all
    within calendar year 2025 and all spilling only to an adjacent month.
    """
    total_rows = 0
    cross_partition_rows = 0
    outside_year_rows = 0
    non_adjacent_rows = 0
    null_pickup_date_rows = 0

    for source_month in range(1, 13):
        folder = month_folder(TAXI_ROOT, source_month)
        if not folder.exists():
            raise FileNotFoundError(
                f"Taxi Silver month not found: {folder}"
            )

        dataset = ds.dataset(str(folder), format="parquet")

        if "pickup_date" not in dataset.schema.names:
            raise RuntimeError(
                f"TAXI_TEMPORAL_SCHEMA_FAILURE 2025-{source_month:02d}: "
                "pickup_date missing"
            )

        scanner = dataset.scanner(
            columns=["pickup_date"],
            batch_size=1_000_000,
        )

        for batch in scanner.to_batches():
            s = pd.to_datetime(
                batch.column("pickup_date").to_pandas(),
                errors="coerce",
            )

            total_rows += len(s)
            null_pickup_date_rows += int(s.isna().sum())

            valid = s.notna()
            year = s.dt.year
            event_month = s.dt.month

            outside_year = valid & year.ne(YEAR)
            outside_year_rows += int(outside_year.sum())

            in_year = valid & year.eq(YEAR)
            cross = in_year & event_month.ne(source_month)
            cross_partition_rows += int(cross.sum())

            non_adjacent = cross & (
                (event_month - source_month).abs().ne(1)
            )
            non_adjacent_rows += int(non_adjacent.sum())

    if total_rows != EXPECTED_TAXI_SILVER_ROWS:
        raise RuntimeError(
            f"TAXI_TEMPORAL_ROW_FAILURE: expected "
            f"{EXPECTED_TAXI_SILVER_ROWS:,}, found {total_rows:,}"
        )

    if null_pickup_date_rows:
        raise RuntimeError(
            f"TAXI_TEMPORAL_NULL_FAILURE: "
            f"{null_pickup_date_rows:,} null pickup_date rows"
        )

    if outside_year_rows:
        raise RuntimeError(
            f"TAXI_TEMPORAL_YEAR_FAILURE: "
            f"{outside_year_rows:,} rows outside calendar 2025"
        )

    if non_adjacent_rows:
        raise RuntimeError(
            f"TAXI_TEMPORAL_ROUTING_FAILURE: "
            f"{non_adjacent_rows:,} cross-partition rows spill beyond "
            "an adjacent month"
        )

    if cross_partition_rows != EXPECTED_TAXI_CROSS_PARTITION_ROWS:
        raise RuntimeError(
            f"TAXI_TEMPORAL_AUDIT_FAILURE: expected "
            f"{EXPECTED_TAXI_CROSS_PARTITION_ROWS:,} cross-partition rows, "
            f"found {cross_partition_rows:,}"
        )

    return {
        "taxi_silver_rows": total_rows,
        "cross_partition_rows": cross_partition_rows,
        "outside_calendar_year_rows": outside_year_rows,
        "non_adjacent_cross_partition_rows": non_adjacent_rows,
        "status": "PASS",
    }


def aggregate_taxi_month(month: int) -> tuple[pd.DataFrame, dict]:
    """
    Aggregate Taxi trips by their actual pickup_date month.

    A small number of TLC rows are physically stored in an adjacent monthly
    Parquet file. For Gold, event time is authoritative. Therefore the target
    month reads its own partition plus adjacent partitions and retains only
    records whose pickup_date belongs to the target calendar month.
    """
    candidate_source_months = [
        source_month
        for source_month in (month - 1, month, month + 1)
        if 1 <= source_month <= 12
    ]

    parts: list[pd.DataFrame] = []

    total_rows = 0
    cross_partition_rows = 0
    domain_rows = 0
    special_264_rows = 0
    special_265_rows = 0
    invalid_location_rows = 0

    domain_revenue = 0.0
    special_264_revenue = 0.0
    special_265_revenue = 0.0

    null_total_amount = 0
    null_fare_amount = 0
    null_trip_distance = 0
    null_pickup_hour = 0
    null_pickup_location = 0

    for source_month in candidate_source_months:
        folder = month_folder(TAXI_ROOT, source_month)
        if not folder.exists():
            raise FileNotFoundError(
                f"Taxi Silver month not found: {folder}"
            )

        dataset = ds.dataset(str(folder), format="parquet")

        required = {
            "pickup_date",
            "pickup_hour",
            "PULocationID",
            "total_amount",
            "fare_amount",
            "trip_distance",
        }
        missing = required - set(dataset.schema.names)
        if missing:
            raise RuntimeError(
                f"TAXI_SCHEMA_FAILURE source 2025-{source_month:02d}: "
                f"missing {sorted(missing)}"
            )

        scanner = dataset.scanner(
            columns=[
                "pickup_date",
                "pickup_hour",
                "PULocationID",
                "total_amount",
                "fare_amount",
                "trip_distance",
            ],
            batch_size=750_000,
        )

        for batch in scanner.to_batches():
            df = batch.to_pandas()

            event_date = pd.to_datetime(
                df["pickup_date"],
                errors="coerce",
            )

            target_mask = (
                event_date.notna()
                & event_date.dt.year.eq(YEAR)
                & event_date.dt.month.eq(month)
            )

            if not target_mask.any():
                continue

            df = df.loc[target_mask].copy()

            total_rows += len(df)
            if source_month != month:
                cross_partition_rows += len(df)

            null_total_amount += int(
                df["total_amount"].isna().sum()
            )
            null_fare_amount += int(
                df["fare_amount"].isna().sum()
            )
            null_trip_distance += int(
                df["trip_distance"].isna().sum()
            )
            null_pickup_hour += int(
                df["pickup_hour"].isna().sum()
            )
            null_pickup_location += int(
                df["PULocationID"].isna().sum()
            )

            zone_domain_mask = df["PULocationID"].between(
                ZONE_MIN, ZONE_MAX
            )
            mask_264 = df["PULocationID"].eq(264)
            mask_265 = df["PULocationID"].eq(265)
            valid_known_mask = (
                zone_domain_mask | mask_264 | mask_265
            )

            invalid_location_rows += int(
                (~valid_known_mask).sum()
            )

            special_264_rows += int(mask_264.sum())
            special_265_rows += int(mask_265.sum())

            special_264_revenue += float(
                df.loc[
                    mask_264,
                    "total_amount",
                ].sum(skipna=True)
            )
            special_265_revenue += float(
                df.loc[
                    mask_265,
                    "total_amount",
                ].sum(skipna=True)
            )

            domain = df.loc[
                zone_domain_mask,
                [
                    "pickup_date",
                    "pickup_hour",
                    "PULocationID",
                    "total_amount",
                    "fare_amount",
                    "trip_distance",
                ],
            ].copy()

            domain_rows += len(domain)
            domain_revenue += float(
                domain["total_amount"].sum(skipna=True)
            )

            if len(domain):
                partial = (
                    domain.groupby(
                        [
                            "pickup_date",
                            "pickup_hour",
                            "PULocationID",
                        ],
                        as_index=False,
                        sort=False,
                        observed=True,
                    )
                    .agg(
                        taxi_trips=(
                            "PULocationID",
                            "size",
                        ),
                        taxi_revenue=(
                            "total_amount",
                            "sum",
                        ),
                        _fare_sum=(
                            "fare_amount",
                            "sum",
                        ),
                        _fare_count=(
                            "fare_amount",
                            "count",
                        ),
                        _distance_sum=(
                            "trip_distance",
                            "sum",
                        ),
                        _distance_count=(
                            "trip_distance",
                            "count",
                        ),
                    )
                    .rename(
                        columns={
                            "pickup_date": "date",
                            "pickup_hour": "hour",
                            "PULocationID": "taxi_zone_id",
                        }
                    )
                )
                parts.append(partial)

    if invalid_location_rows:
        raise RuntimeError(
            f"TAXI_LOCATION_DOMAIN_FAILURE event-month "
            f"2025-{month:02d}: {invalid_location_rows:,} rows "
            "outside IDs 1..265"
        )

    nulls = {
        "total_amount": null_total_amount,
        "fare_amount": null_fare_amount,
        "trip_distance": null_trip_distance,
        "pickup_hour": null_pickup_hour,
        "PULocationID": null_pickup_location,
    }

    if any(nulls.values()):
        raise RuntimeError(
            f"TAXI_NULL_AGGREGATION_INPUT_FAILURE "
            f"event-month 2025-{month:02d}: {nulls}"
        )

    agg = reduce_partial_taxi_aggregates(parts)

    if not agg.empty:
        agg["taxi_zone_id"] = (
            agg["taxi_zone_id"].astype("int32")
        )
        agg["hour"] = agg["hour"].astype("int32")

    special_rows = special_264_rows + special_265_rows

    if domain_rows + special_rows != total_rows:
        raise RuntimeError(
            f"TAXI_RECONCILIATION_FAILURE event-month "
            f"2025-{month:02d}: domain={domain_rows:,} + "
            f"special={special_rows:,} != total={total_rows:,}"
        )

    metrics = {
        "taxi_input_rows": total_rows,
        "taxi_cross_partition_rows": cross_partition_rows,
        "taxi_gold_domain_rows": domain_rows,
        "taxi_special_264_rows": special_264_rows,
        "taxi_special_265_rows": special_265_rows,
        "taxi_special_rows": special_rows,
        "taxi_other_invalid_rows": invalid_location_rows,
        "taxi_gold_domain_revenue": domain_revenue,
        "taxi_special_264_revenue": special_264_revenue,
        "taxi_special_265_revenue": special_265_revenue,
        "taxi_special_revenue": (
            special_264_revenue + special_265_revenue
        ),
    }

    return agg, metrics

def aggregate_311_month(month: int) -> tuple[pd.DataFrame, dict]:
    folder = month_folder(COMPLAINT_ROOT, month)
    if not folder.exists():
        raise FileNotFoundError(f"Mapped 311 month not found: {folder}")

    dataset = ds.dataset(str(folder), format="parquet")

    required = {
        "created_at",
        "created_date",
        "taxi_zone_location_id",
        "spatial_mapping_status",
    }
    missing = required - set(dataset.schema.names)
    if missing:
        raise RuntimeError(
            f"311_SCHEMA_FAILURE 2025-{month:02d}: missing {sorted(missing)}"
        )

    scanner = dataset.scanner(
        columns=[
            "created_at",
            "created_date",
            "taxi_zone_location_id",
            "spatial_mapping_status",
        ],
        batch_size=500_000,
    )

    parts: list[pd.DataFrame] = []

    input_rows = 0
    mapped_rows = 0
    outside_rows = 0
    other_status_rows = 0

    for batch in scanner.to_batches():
        df = batch.to_pandas()
        input_rows += len(df)

        mapped_mask = df["spatial_mapping_status"].eq(MAPPED_STATUS)
        outside_mask = df["spatial_mapping_status"].eq(OUTSIDE_STATUS)

        mapped_rows += int(mapped_mask.sum())
        outside_rows += int(outside_mask.sum())
        other_status_rows += int((~(mapped_mask | outside_mask)).sum())

        mapped = df.loc[
            mapped_mask,
            [
                "created_at",
                "created_date",
                "taxi_zone_location_id",
            ],
        ].copy()

        if mapped["taxi_zone_location_id"].isna().any():
            raise RuntimeError(
                f"311_MAPPING_ID_FAILURE 2025-{month:02d}: "
                "mapped rows contain null Taxi Zone IDs"
            )

        bad_zone = ~mapped["taxi_zone_location_id"].between(
            ZONE_MIN, ZONE_MAX
        )
        if bad_zone.any():
            raise RuntimeError(
                f"311_MAPPING_ID_FAILURE 2025-{month:02d}: "
                f"{int(bad_zone.sum())} mapped rows outside IDs 1..263"
            )

        mapped["hour"] = pd.to_datetime(
            mapped["created_at"]
        ).dt.hour.astype("int32")

        mapped = mapped.rename(
            columns={
                "created_date": "date",
                "taxi_zone_location_id": "taxi_zone_id",
            }
        )

        partial = (
            mapped.groupby(
                ["date", "hour", "taxi_zone_id"],
                as_index=False,
                sort=False,
                observed=True,
            )
            .size()
            .rename(columns={"size": "complaints_311"})
        )

        parts.append(partial)

    if other_status_rows:
        raise RuntimeError(
            f"311_MAPPING_STATUS_FAILURE 2025-{month:02d}: "
            f"{other_status_rows} unexpected status rows"
        )

    if mapped_rows + outside_rows != input_rows:
        raise RuntimeError(
            f"311_RECONCILIATION_FAILURE 2025-{month:02d}"
        )

    if parts:
        combined = pd.concat(parts, ignore_index=True)
        agg = (
            combined.groupby(
                ["date", "hour", "taxi_zone_id"],
                as_index=False,
                sort=False,
                observed=True,
            )["complaints_311"]
            .sum()
        )
    else:
        agg = pd.DataFrame(
            columns=[
                "date",
                "hour",
                "taxi_zone_id",
                "complaints_311",
            ]
        )

    if not agg.empty:
        agg["taxi_zone_id"] = agg["taxi_zone_id"].astype("int32")
        agg["hour"] = agg["hour"].astype("int32")

    if int(agg["complaints_311"].sum()) != mapped_rows:
        raise RuntimeError(
            f"311_AGGREGATION_RECONCILIATION_FAILURE 2025-{month:02d}"
        )

    metrics = {
        "complaints_input_rows": input_rows,
        "complaints_spatially_mapped_rows": mapped_rows,
        "complaints_outside_polygon_rows": outside_rows,
        "complaints_gold_count": int(
            agg["complaints_311"].sum()
        ),
    }

    return agg, metrics


def load_weather_month(month: int) -> tuple[pd.DataFrame, dict]:
    folder = month_folder(WEATHER_ROOT, month)
    if not folder.exists():
        raise FileNotFoundError(f"Weather Silver month not found: {folder}")

    dataset = ds.dataset(str(folder), format="parquet")

    required = {
        "weather_date",
        "weather_hour",
        "temperature_c",
        "rain_mm",
        "snowfall_cm",
        "weather_condition",
        "is_weather_gap",
    }
    missing = required - set(dataset.schema.names)
    if missing:
        raise RuntimeError(
            f"WEATHER_SCHEMA_FAILURE 2025-{month:02d}: missing {sorted(missing)}"
        )

    table = dataset.to_table(
        columns=[
            "weather_date",
            "weather_hour",
            "temperature_c",
            "rain_mm",
            "snowfall_cm",
            "weather_condition",
            "is_weather_gap",
        ]
    )

    df = table.to_pandas().rename(
        columns={
            "weather_date": "date",
            "weather_hour": "hour",
        }
    )

    expected_hours = expected_month_hours(month)
    expected_count = len(expected_hours)

    if len(df) != expected_count:
        raise RuntimeError(
            f"WEATHER_ROW_FAILURE 2025-{month:02d}: "
            f"expected {expected_count}, found {len(df)}"
        )

    if df[["date", "hour"]].duplicated().any():
        raise RuntimeError(
            f"WEATHER_DUPLICATE_HOUR_FAILURE 2025-{month:02d}"
        )

    if df["is_weather_gap"].any():
        raise RuntimeError(
            f"WEATHER_GAP_FAILURE 2025-{month:02d}"
        )

    core = [
        "temperature_c",
        "rain_mm",
        "snowfall_cm",
        "weather_condition",
    ]
    if df[core].isna().any().any():
        raise RuntimeError(
            f"WEATHER_NULL_FAILURE 2025-{month:02d}"
        )

    expected_keys = {
        (ts.date(), int(ts.hour))
        for ts in expected_hours
    }
    observed_keys = set(
        zip(df["date"], df["hour"].astype(int))
    )

    if observed_keys != expected_keys:
        missing = sorted(expected_keys - observed_keys)[:20]
        unexpected = sorted(observed_keys - expected_keys)[:20]
        raise RuntimeError(
            f"WEATHER_HOUR_GRID_FAILURE 2025-{month:02d}: "
            f"missing sample={missing}, unexpected sample={unexpected}"
        )

    weather = df[
        [
            "date",
            "hour",
            "temperature_c",
            "rain_mm",
            "snowfall_cm",
            "weather_condition",
        ]
    ].copy()

    weather["hour"] = weather["hour"].astype("int32")

    metrics = {
        "weather_rows": len(weather),
        "weather_expected_rows": expected_count,
        "weather_gap_rows": 0,
    }

    return weather, metrics


def build_dense_grid(
    month: int,
    zones: pd.DataFrame,
) -> pd.DataFrame:
    hours = expected_month_hours(month)

    time_df = pd.DataFrame(
        {
            "date": [ts.date() for ts in hours],
            "hour": [int(ts.hour) for ts in hours],
        }
    )
    time_df["hour"] = time_df["hour"].astype("int32")

    # Cross join: every authoritative Taxi Zone polygon x every local hour.
    grid = time_df.merge(zones, how="cross")

    expected = len(hours) * EXPECTED_ZONE_COUNT
    if len(grid) != expected:
        raise RuntimeError(
            f"GOLD_GRID_FAILURE 2025-{month:02d}: "
            f"expected {expected:,}, found {len(grid):,}"
        )

    return grid


def build_gold_month(
    month: int,
    zones: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    taxi_agg, taxi_metrics = aggregate_taxi_month(month)
    complaint_agg, complaint_metrics = aggregate_311_month(month)
    weather, weather_metrics = load_weather_month(month)

    gold = build_dense_grid(month, zones)

    gold = gold.merge(
        taxi_agg,
        how="left",
        on=["date", "hour", "taxi_zone_id"],
        validate="one_to_one",
    )

    gold = gold.merge(
        complaint_agg,
        how="left",
        on=["date", "hour", "taxi_zone_id"],
        validate="one_to_one",
    )

    gold = gold.merge(
        weather,
        how="left",
        on=["date", "hour"],
        validate="many_to_one",
    )

    gold["taxi_trips"] = (
        gold["taxi_trips"].fillna(0).astype("int64")
    )
    gold["taxi_revenue"] = (
        gold["taxi_revenue"].fillna(0.0).astype("float64")
    )
    gold["complaints_311"] = (
        gold["complaints_311"].fillna(0).astype("int64")
    )

    if gold[
        [
            "temperature_c",
            "rain_mm",
            "snowfall_cm",
            "weather_condition",
        ]
    ].isna().any().any():
        raise RuntimeError(
            f"GOLD_WEATHER_JOIN_FAILURE 2025-{month:02d}: "
            "Gold rows with missing Weather detected"
        )

    if gold[["date", "hour", "taxi_zone_id"]].duplicated().any():
        raise RuntimeError(
            f"GOLD_KEY_DUPLICATE_FAILURE 2025-{month:02d}"
        )

    expected_rows = (
        len(expected_month_hours(month)) * EXPECTED_ZONE_COUNT
    )
    if len(gold) != expected_rows:
        raise RuntimeError(
            f"GOLD_ROW_FAILURE 2025-{month:02d}: "
            f"expected {expected_rows:,}, found {len(gold):,}"
        )

    taxi_trip_sum = int(gold["taxi_trips"].sum())
    taxi_revenue_sum = float(gold["taxi_revenue"].sum())
    complaint_sum = int(gold["complaints_311"].sum())

    if taxi_trip_sum != taxi_metrics["taxi_gold_domain_rows"]:
        raise RuntimeError(
            f"GOLD_TAXI_COUNT_RECONCILIATION_FAILURE 2025-{month:02d}: "
            f"Gold={taxi_trip_sum:,}, "
            f"expected={taxi_metrics['taxi_gold_domain_rows']:,}"
        )

    if not np.isclose(
        taxi_revenue_sum,
        taxi_metrics["taxi_gold_domain_revenue"],
        rtol=0,
        atol=0.01,
    ):
        raise RuntimeError(
            f"GOLD_TAXI_REVENUE_RECONCILIATION_FAILURE 2025-{month:02d}: "
            f"Gold={taxi_revenue_sum:.2f}, "
            f"expected={taxi_metrics['taxi_gold_domain_revenue']:.2f}"
        )

    if complaint_sum != complaint_metrics["complaints_gold_count"]:
        raise RuntimeError(
            f"GOLD_311_COUNT_RECONCILIATION_FAILURE 2025-{month:02d}"
        )

    # No-trip averages are analytically undefined and remain NULL, not zero.
    no_trip = gold["taxi_trips"].eq(0)
    gold.loc[no_trip, "average_fare"] = np.nan
    gold.loc[no_trip, "average_trip_distance"] = np.nan

    run_id = str(uuid.uuid4())
    processed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    gold["_run_id"] = run_id
    gold["_processed_at"] = processed_at
    gold["_processing_year"] = np.int32(YEAR)
    gold["_processing_month"] = np.int32(month)

    gold["taxi_zone_id"] = gold["taxi_zone_id"].astype("int32")
    gold["hour"] = gold["hour"].astype("int32")

    gold = gold[
        [
            "date",
            "hour",
            "taxi_zone_id",
            "taxi_zone_name",
            "borough",
            "taxi_trips",
            "taxi_revenue",
            "average_fare",
            "average_trip_distance",
            "complaints_311",
            "temperature_c",
            "rain_mm",
            "snowfall_cm",
            "weather_condition",
            "_run_id",
            "_processed_at",
            "_processing_year",
            "_processing_month",
        ]
    ].sort_values(
        ["date", "hour", "taxi_zone_id"],
        kind="stable",
    ).reset_index(drop=True)

    metrics = {
        **taxi_metrics,
        **complaint_metrics,
        **weather_metrics,
        "gold_rows": len(gold),
        "expected_gold_rows": expected_rows,
        "gold_taxi_trips": taxi_trip_sum,
        "gold_taxi_revenue": taxi_revenue_sum,
        "gold_complaints_311": complaint_sum,
        "zero_taxi_zone_hours": int(
            gold["taxi_trips"].eq(0).sum()
        ),
        "zero_complaint_zone_hours": int(
            gold["complaints_311"].eq(0).sum()
        ),
        "weather_null_gold_rows": 0,
        "run_id": run_id,
    }

    return gold, metrics


def write_gold_month(
    gold: pd.DataFrame,
    month: int,
    run_id: str,
) -> tuple[Path, int]:
    output_dir = month_folder(OUTPUT_ROOT, month)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = (
        output_dir
        / f"part-00000-{run_id.replace('-', '')}.parquet"
    )

    table = pa.Table.from_pandas(
        gold,
        schema=GOLD_SCHEMA,
        preserve_index=False,
        safe=True,
    )

    pq.write_table(
        table,
        output_file,
        compression="snappy",
    )

    verified_rows = pq.ParquetFile(output_file).metadata.num_rows

    return output_file, verified_rows


def update_reconciliation(new_rows: list[dict]) -> pd.DataFrame:
    RECONCILIATION_REPORT.parent.mkdir(parents=True, exist_ok=True)

    new_df = pd.DataFrame(new_rows)

    if RECONCILIATION_REPORT.exists():
        existing = pd.read_csv(RECONCILIATION_REPORT)

        incoming_months = set(
            new_df["processing_month"].astype(str)
        )

        existing = existing[
            ~existing["processing_month"].astype(str).isin(
                incoming_months
            )
        ]

        combined = pd.concat(
            [existing, new_df],
            ignore_index=True,
        )
    else:
        combined = new_df

    combined = combined.sort_values(
        "processing_month"
    ).reset_index(drop=True)

    combined.to_csv(
        RECONCILIATION_REPORT,
        index=False,
    )

    return combined


def physical_gold_audit() -> tuple[int, int]:
    months_found = 0
    rows = 0

    for month in range(1, 13):
        folder = month_folder(OUTPUT_ROOT, month)
        files = sorted(folder.glob("*.parquet"))

        if files:
            months_found += 1

        rows += sum(
            pq.ParquetFile(f).metadata.num_rows
            for f in files
        )

    return months_found, rows


def maybe_write_full_year_summary(rec: pd.DataFrame) -> bool:
    if len(rec) != 12:
        return False

    if not (rec["status"] == "SUCCESS").all():
        return False

    months = set(rec["processing_month"].astype(str))
    expected_months = {
        f"{YEAR}-{month:02d}"
        for month in range(1, 13)
    }
    if months != expected_months:
        return False

    taxi_input = int(rec["taxi_input_rows"].sum())
    taxi_domain = int(rec["taxi_gold_domain_rows"].sum())
    taxi_special = int(rec["taxi_special_rows"].sum())
    taxi_264 = int(rec["taxi_special_264_rows"].sum())
    taxi_265 = int(rec["taxi_special_265_rows"].sum())
    taxi_special_revenue = float(
        rec["taxi_special_revenue"].sum()
    )
    taxi_cross_partition = int(
        rec["taxi_cross_partition_rows"].sum()
    )

    complaint_input = int(
        rec["complaints_input_rows"].sum()
    )
    complaints_mapped = int(
        rec["complaints_spatially_mapped_rows"].sum()
    )
    complaints_outside = int(
        rec["complaints_outside_polygon_rows"].sum()
    )

    weather_rows = int(rec["weather_rows"].sum())
    gold_rows = int(rec["gold_rows"].sum())

    gold_taxi_trips = int(rec["gold_taxi_trips"].sum())
    gold_complaints = int(
        rec["gold_complaints_311"].sum()
    )

    if taxi_input != EXPECTED_TAXI_SILVER_ROWS:
        raise RuntimeError(
            f"FULL_YEAR_TAXI_INPUT_FAILURE: {taxi_input:,}"
        )

    if taxi_domain != EXPECTED_TAXI_GOLD_DOMAIN_ROWS:
        raise RuntimeError(
            f"FULL_YEAR_TAXI_DOMAIN_FAILURE: {taxi_domain:,}"
        )

    if taxi_special != EXPECTED_TAXI_SPECIAL_ROWS:
        raise RuntimeError(
            f"FULL_YEAR_TAXI_SPECIAL_FAILURE: {taxi_special:,}"
        )

    if taxi_domain + taxi_special != taxi_input:
        raise RuntimeError(
            "FULL_YEAR_TAXI_RECONCILIATION_FAILURE"
        )

    if taxi_cross_partition != EXPECTED_TAXI_CROSS_PARTITION_ROWS:
        raise RuntimeError(
            "FULL_YEAR_TAXI_TEMPORAL_ROUTING_FAILURE: "
            f"expected {EXPECTED_TAXI_CROSS_PARTITION_ROWS:,}, "
            f"found {taxi_cross_partition:,}"
        )

    if complaint_input != EXPECTED_311_MAPPED_SILVER_ROWS:
        raise RuntimeError(
            f"FULL_YEAR_311_INPUT_FAILURE: {complaint_input:,}"
        )

    if complaints_mapped != EXPECTED_311_SPATIALLY_MAPPED_ROWS:
        raise RuntimeError(
            f"FULL_YEAR_311_MAPPED_FAILURE: {complaints_mapped:,}"
        )

    if complaints_outside != EXPECTED_311_OUTSIDE_ROWS:
        raise RuntimeError(
            f"FULL_YEAR_311_OUTSIDE_FAILURE: {complaints_outside:,}"
        )

    if complaints_mapped + complaints_outside != complaint_input:
        raise RuntimeError(
            "FULL_YEAR_311_RECONCILIATION_FAILURE"
        )

    if weather_rows != EXPECTED_WEATHER_HOURS:
        raise RuntimeError(
            f"FULL_YEAR_WEATHER_FAILURE: {weather_rows:,}"
        )

    if gold_rows != EXPECTED_FULL_YEAR_GOLD_ROWS:
        raise RuntimeError(
            f"FULL_YEAR_GOLD_ROW_FAILURE: {gold_rows:,}"
        )

    if gold_taxi_trips != taxi_domain:
        raise RuntimeError(
            "FULL_YEAR_GOLD_TAXI_RECONCILIATION_FAILURE"
        )

    if gold_complaints != complaints_mapped:
        raise RuntimeError(
            "FULL_YEAR_GOLD_311_RECONCILIATION_FAILURE"
        )

    months_found, physical_rows = physical_gold_audit()

    if months_found != 12:
        raise RuntimeError(
            f"FULL_YEAR_PHYSICAL_MONTH_FAILURE: {months_found}"
        )

    if physical_rows != EXPECTED_FULL_YEAR_GOLD_ROWS:
        raise RuntimeError(
            f"FULL_YEAR_PHYSICAL_ROW_FAILURE: {physical_rows:,}"
        )

    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)

    summary = {
        "phase": 13,
        "status": "SUCCESS",
        "gold_table": "zone_hourly",
        "year": YEAR,
        "grain": (
            "one NYC local calendar date + hour + "
            "authoritative TLC Taxi Zone polygon"
        ),
        "join_keys": [
            "date",
            "hour",
            "taxi_zone_id",
        ],
        "zone_domain": {
            "authoritative_location_ids": "1-263",
            "zone_count": EXPECTED_ZONE_COUNT,
            "taxi_location_id_264": "Unknown - excluded from spatial Gold",
            "taxi_location_id_265": "Outside of NYC - excluded from spatial Gold",
            "taxi_special_264_rows": taxi_264,
            "taxi_special_265_rows": taxi_265,
            "taxi_special_rows_total": taxi_special,
            "taxi_special_revenue_excluded_from_spatial_gold": round(
                taxi_special_revenue, 2
            ),
        },
        "aggregation_rules": {
            "taxi_trips": "COUNT(*) of Taxi Silver rows by pickup date/hour/PULocationID",
            "taxi_revenue": "SUM(total_amount)",
            "average_fare": "AVG(fare_amount); NULL when taxi_trips = 0",
            "average_trip_distance": "AVG(trip_distance); NULL when taxi_trips = 0",
            "complaints_311": "COUNT(*) of spatially mapped 311 complaints by created date/hour/taxi_zone_location_id",
            "temperature_c": "hourly Weather Silver observation repeated across all authoritative Taxi Zones",
            "rain_mm": "hourly Weather Silver observation repeated across all authoritative Taxi Zones",
            "snowfall_cm": "hourly Weather Silver observation repeated across all authoritative Taxi Zones",
            "weather_condition": "hourly Weather Silver WMO-derived condition repeated across all authoritative Taxi Zones",
        },
        "revenue_definition": (
            "Taxi revenue is SUM(total_amount) for Taxi Silver trips "
            "whose pickup LocationID is an authoritative polygon ID 1-263."
        ),
        "taxi_reconciliation": {
            "taxi_silver_rows": taxi_input,
            "authoritative_zone_rows": taxi_domain,
            "special_264_265_rows_excluded": taxi_special,
            "gold_taxi_trip_count": gold_taxi_trips,
            "cross_partition_rows_routed_by_pickup_date": taxi_cross_partition,
            "temporal_assignment_rule": (
                "Gold month is determined by pickup_date, not physical "
                "Taxi Silver partition."
            ),
            "status": "PASS",
        },
        "complaint_reconciliation": {
            "mapped_silver_input_rows": complaint_input,
            "spatially_mapped_rows": complaints_mapped,
            "outside_polygon_rows_excluded_from_zone_gold": complaints_outside,
            "gold_complaint_count": gold_complaints,
            "status": "PASS",
        },
        "weather_reconciliation": {
            "hourly_weather_rows": weather_rows,
            "expected_hourly_weather_rows": EXPECTED_WEATHER_HOURS,
            "missing_weather_hours": 0,
            "status": "PASS",
        },
        "gold_reconciliation": {
            "hours": EXPECTED_WEATHER_HOURS,
            "zones": EXPECTED_ZONE_COUNT,
            "expected_rows": EXPECTED_FULL_YEAR_GOLD_ROWS,
            "physical_rows": physical_rows,
            "months_found": months_found,
            "row_preservation": "PASS",
        },
    }

    with SUMMARY_JSON.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return True


def process_month(
    month: int,
    zones: pd.DataFrame,
) -> dict:
    mt = f"{month:02d}"
    started_at = datetime.now(timezone.utc)

    print("\n" + "=" * 78)
    print(f"PHASE 13 - GOLD ZONE-HOURLY BUILD - 2025-{mt}")
    print("=" * 78)

    try:
        gold, metrics = build_gold_month(month, zones)
        run_id = metrics["run_id"]

        output_file, verified_rows = write_gold_month(
            gold,
            month,
            run_id,
        )

        if verified_rows != metrics["expected_gold_rows"]:
            raise RuntimeError(
                f"GOLD_PARQUET_VERIFY_FAILURE 2025-{mt}: "
                f"verified={verified_rows:,}, "
                f"expected={metrics['expected_gold_rows']:,}"
            )

        result = {
            "processing_month": f"{YEAR}-{mt}",
            **metrics,
            "verified_gold_rows": verified_rows,
            "status": "SUCCESS",
        }

        write_run_log(
            {
                "phase": 13,
                "pipeline": "gold_zone_hourly",
                **result,
                "started_at": started_at.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "output_file": str(output_file),
            }
        )

        print(f"Gold rows               : {verified_rows:,}")
        print(
            f"Taxi trips in Gold      : "
            f"{metrics['gold_taxi_trips']:,}"
        )
        print(
            f"Taxi cross-partition    : "
            f"{metrics['taxi_cross_partition_rows']:,} routed by pickup_date"
        )
        print(
            f"Taxi special 264/265    : "
            f"{metrics['taxi_special_rows']:,} excluded"
        )
        print(
            f"311 complaints in Gold  : "
            f"{metrics['gold_complaints_311']:,}"
        )
        print(
            f"311 outside polygons    : "
            f"{metrics['complaints_outside_polygon_rows']:,} excluded"
        )
        print(
            f"Weather hours           : "
            f"{metrics['weather_rows']:,}"
        )
        print(
            f"Zero-trip zone-hours    : "
            f"{metrics['zero_taxi_zone_hours']:,}"
        )
        print(
            f"Zero-311 zone-hours     : "
            f"{metrics['zero_complaint_zone_hours']:,}"
        )
        print("Monthly reconciliation  : PASS")
        print(f"2025-{mt}: GOLD BUILD SUCCESS")

        return result

    except Exception as exc:
        write_run_log(
            {
                "phase": 13,
                "pipeline": "gold_zone_hourly",
                "processing_month": f"{YEAR}-{mt}",
                "started_at": started_at.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "status": "FAILED",
                "error_message": str(exc),
            }
        )
        print(f"2025-{mt}: GOLD BUILD FAILED")
        print(f"Error: {exc}")
        raise


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build Phase 13 combined zone-hourly Gold dataset."
    )
    parser.add_argument(
        "--months",
        nargs="+",
        type=int,
        default=list(range(1, 13)),
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if any(month < 1 or month > 12 for month in args.months):
        raise ValueError(f"Invalid months: {args.months}")

    zones = load_zone_dimension()
    temporal_audit = audit_taxi_temporal_routing()

    print("=" * 78)
    print("PHASE 13 - COMBINED GOLD ANALYTICAL DATASET")
    print("=" * 78)
    print("Grain: Date + Hour + authoritative Taxi Zone")
    print("Zone domain: TLC LocationID 1..263")
    print(
        f"Full-year dense Gold target: "
        f"{EXPECTED_FULL_YEAR_GOLD_ROWS:,} rows"
    )
    print("Taxi geography: pickup LocationID")
    print("Taxi month assignment: pickup_date (not physical file partition)")
    print(
        "Taxi cross-partition audit: "
        f"{temporal_audit['cross_partition_rows']:,} rows, PASS"
    )
    print("Revenue definition: SUM(total_amount)")
    print("Average fare: AVG(fare_amount)")
    print("Average trip distance: AVG(trip_distance)")
    print("311: COUNT(mapped complaints)")
    print("Weather: one hourly citywide observation repeated across zones")
    print("Taxi IDs 264/265: excluded + explicitly reconciled")
    print("311 outside polygons: excluded + explicitly reconciled")
    print("Missing Weather: publication failure; no imputation")

    results = [
        process_month(month, zones)
        for month in args.months
    ]

    rec = update_reconciliation(results)
    full_year_ready = maybe_write_full_year_summary(rec)

    result_df = pd.DataFrame(results)

    print("\n" + "=" * 78)
    print("PHASE 13 RUN SUMMARY")
    print("=" * 78)
    print(
        "Months processed:",
        ", ".join(f"{month:02d}" for month in args.months),
    )
    print(
        f"Gold rows                 : "
        f"{int(result_df['gold_rows'].sum()):,}"
    )
    print(
        f"Taxi trips in Gold        : "
        f"{int(result_df['gold_taxi_trips'].sum()):,}"
    )
    print(
        f"Taxi cross-partition routed: "
        f"{int(result_df['taxi_cross_partition_rows'].sum()):,}"
    )
    print(
        f"Taxi special rows excluded: "
        f"{int(result_df['taxi_special_rows'].sum()):,}"
    )
    print(
        f"311 complaints in Gold    : "
        f"{int(result_df['gold_complaints_311'].sum()):,}"
    )
    print(
        f"311 outside rows excluded : "
        f"{int(result_df['complaints_outside_polygon_rows'].sum()):,}"
    )
    print(
        f"Weather rows              : "
        f"{int(result_df['weather_rows'].sum()):,}"
    )
    print(f"Reconciliation report     : {RECONCILIATION_REPORT}")

    if full_year_ready:
        print("Full-year Gold audit      : PASS")
        print(f"Summary report            : {SUMMARY_JSON}")
    else:
        print(
            "Full-year Gold audit      : pending until reconciliation "
            "contains all 12 successful months"
        )

    print("\nPHASE 13 GOLD BUILD: SUCCESS")


if __name__ == "__main__":
    main()
