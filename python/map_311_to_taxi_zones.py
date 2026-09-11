#!/usr/bin/env python
"""
Phase 12 - Map valid NYC 311 Silver complaints to TLC Taxi Zones.

Authoritative method:
    311 longitude/latitude (EPSG:4326)
    -> point geometry
    -> reproject to Taxi Zone CRS (EPSG:2263)
    -> point-in-polygon spatial join
    -> Taxi Zone LocationID

Contracts:
- Borough is NEVER used to assign a Taxi Zone.
- All valid Phase 10 Silver 311 rows are retained.
- Spatially unmapped valid records remain in output with a null Taxi Zone ID
  and an explicit mapping status.
- No nearest-polygon fallback is used.
- No Taxi Zone ID is fabricated.
- Taxi Zone special IDs 264/265 are not polygon IDs and cannot be assigned by
  this spatial join.
"""

from __future__ import annotations

import argparse
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_ROOT = (
    PROJECT_ROOT / "data" / "silver" / "complaints_311" / "year=2025"
)
OUTPUT_ROOT = (
    PROJECT_ROOT / "data" / "silver" / "complaints_311_mapped" / "year=2025"
)

ZONE_SHP = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "taxi_zones"
    / "shapefile"
    / "taxi_zones"
    / "taxi_zones.shp"
)

PROFILE_SUMMARY = (
    PROJECT_ROOT / "reports" / "profiling" / "311_profile_summary.json"
)

PHASE10_RECONCILIATION = (
    PROJECT_ROOT
    / "reports"
    / "reconciliation"
    / "311_silver_reconciliation.csv"
)

MAPPING_RECONCILIATION = (
    PROJECT_ROOT
    / "reports"
    / "reconciliation"
    / "311_taxi_zone_mapping_reconciliation.csv"
)

SUMMARY_JSON = (
    PROJECT_ROOT
    / "reports"
    / "geospatial"
    / "phase12_311_taxi_zone_mapping_summary.json"
)

RUN_LOG = PROJECT_ROOT / "logs" / "pipeline_runs.jsonl"

EXPECTED_RAW_ROWS = 3_655_040
EXPECTED_VALID_SILVER_ROWS = 3_604_061
EXPECTED_MISSING_COORDINATES = 50_148
EXPECTED_ZONE_POLYGONS = 263
POINT_CRS = "EPSG:4326"
EXPECTED_ZONE_CRS = "EPSG:2263"

MAPPED_STATUS = "MAPPED"
OUTSIDE_STATUS = "OUTSIDE_TAXI_ZONE_POLYGONS"


def write_run_log(record: dict) -> None:
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RUN_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


def load_source_contracts() -> tuple[dict, pd.DataFrame]:
    if not PROFILE_SUMMARY.exists():
        raise FileNotFoundError(f"311 profile summary not found: {PROFILE_SUMMARY}")
    if not PHASE10_RECONCILIATION.exists():
        raise FileNotFoundError(
            f"Phase 10 reconciliation not found: {PHASE10_RECONCILIATION}"
        )

    with PROFILE_SUMMARY.open("r", encoding="utf-8") as f:
        profile = json.load(f)

    if profile.get("row_count") != EXPECTED_RAW_ROWS:
        raise RuntimeError(
            f"SOURCE_CONTRACT_FAILURE: expected {EXPECTED_RAW_ROWS:,} Raw 311 rows, "
            f"found {profile.get('row_count')!r}"
        )

    missing_coordinates = (
        profile.get("candidate_anomalies", {}).get("MISSING_COORDINATES")
    )
    if missing_coordinates != EXPECTED_MISSING_COORDINATES:
        raise RuntimeError(
            "SOURCE_CONTRACT_FAILURE: expected "
            f"{EXPECTED_MISSING_COORDINATES:,} missing-coordinate source rows, "
            f"found {missing_coordinates!r}"
        )

    rec = pd.read_csv(PHASE10_RECONCILIATION)
    if len(rec) != 12:
        raise RuntimeError(
            f"PHASE10_CONTRACT_FAILURE: expected 12 reconciliation rows, found {len(rec)}"
        )

    silver_total = int(rec["silver_rows"].sum())
    if silver_total != EXPECTED_VALID_SILVER_ROWS:
        raise RuntimeError(
            f"PHASE10_CONTRACT_FAILURE: expected {EXPECTED_VALID_SILVER_ROWS:,} "
            f"Silver rows, found {silver_total:,}"
        )

    return profile, rec


def load_zones() -> gpd.GeoDataFrame:
    if not ZONE_SHP.exists():
        raise FileNotFoundError(f"Taxi Zone shapefile not found: {ZONE_SHP}")

    zones = gpd.read_file(ZONE_SHP)

    required = {"LocationID", "zone", "borough", "geometry"}
    missing = required - set(zones.columns)
    if missing:
        raise RuntimeError(
            f"TAXI_ZONE_SCHEMA_FAILURE: missing columns {sorted(missing)}"
        )

    if len(zones) != EXPECTED_ZONE_POLYGONS:
        raise RuntimeError(
            f"TAXI_ZONE_COUNT_FAILURE: expected {EXPECTED_ZONE_POLYGONS} polygons, "
            f"found {len(zones)}"
        )

    if zones.crs is None or zones.crs.to_string().upper() != EXPECTED_ZONE_CRS:
        raise RuntimeError(
            f"TAXI_ZONE_CRS_FAILURE: expected {EXPECTED_ZONE_CRS}, found {zones.crs}"
        )

    if zones["LocationID"].isna().any():
        raise RuntimeError("TAXI_ZONE_ID_FAILURE: null LocationID found")

    if zones["LocationID"].duplicated().any():
        raise RuntimeError("TAXI_ZONE_ID_FAILURE: duplicate LocationID found")

    if zones.geometry.isna().any():
        raise RuntimeError("TAXI_ZONE_GEOMETRY_FAILURE: null geometry found")

    if not zones.geometry.is_valid.all():
        raise RuntimeError("TAXI_ZONE_GEOMETRY_FAILURE: invalid geometry found")

    zone_ids = set(zones["LocationID"].astype(int).tolist())
    if 264 in zone_ids or 265 in zone_ids:
        raise RuntimeError(
            "TAXI_ZONE_SPECIAL_ID_FAILURE: 264/265 unexpectedly present as polygons"
        )

    return zones[["LocationID", "zone", "borough", "geometry"]].copy()


def read_silver_month(month: int) -> pd.DataFrame:
    mt = f"{month:02d}"
    folder = INPUT_ROOT / f"month={mt}"

    if not folder.exists():
        raise FileNotFoundError(f"311 Silver month not found: {folder}")

    dataset = ds.dataset(str(folder), format="parquet")
    table = dataset.to_table()
    df = table.to_pandas()

    required = {"unique_key", "latitude", "longitude"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(
            f"311_SILVER_SCHEMA_FAILURE: missing columns {sorted(missing)}"
        )

    if df["unique_key"].duplicated().any():
        raise RuntimeError(
            f"311_SILVER_KEY_FAILURE: duplicate unique_key in 2025-{mt}"
        )

    if df["latitude"].isna().any() or df["longitude"].isna().any():
        raise RuntimeError(
            f"311_SILVER_COORDINATE_FAILURE: null coordinates in 2025-{mt}"
        )

    return df


def spatial_map(
    silver: pd.DataFrame,
    zones: gpd.GeoDataFrame,
    month: int,
) -> pd.DataFrame:
    mt = f"{month:02d}"

    # Stable row identifier protects original row order and makes multi-match
    # detection explicit.
    work = silver.copy()
    work["_geo_row_id"] = range(len(work))

    points = gpd.GeoDataFrame(
        work[["_geo_row_id", "unique_key", "latitude", "longitude"]].copy(),
        geometry=gpd.points_from_xy(
            work["longitude"],
            work["latitude"],
        ),
        crs=POINT_CRS,
    )

    points = points.to_crs(zones.crs)

    joined = gpd.sjoin(
        points,
        zones,
        how="left",
        predicate="within",
    )

    # A valid point must never silently receive multiple authoritative zones.
    duplicate_matches = joined["_geo_row_id"].duplicated(keep=False)
    if duplicate_matches.any():
        ambiguous = joined.loc[
            duplicate_matches,
            ["_geo_row_id", "unique_key", "LocationID"],
        ]
        sample = ambiguous.head(20).to_dict("records")
        raise RuntimeError(
            f"AMBIGUOUS_SPATIAL_JOIN: {ambiguous['_geo_row_id'].nunique()} "
            f"311 points matched multiple Taxi Zone polygons in 2025-{mt}. "
            f"Sample: {sample}"
        )

    mapping = joined[
        ["_geo_row_id", "LocationID", "zone", "borough"]
    ].copy()

    mapping = mapping.rename(
        columns={
            "LocationID": "taxi_zone_location_id",
            "zone": "taxi_zone_name",
            "borough": "taxi_zone_borough",
        }
    )

    enriched = work.merge(
        mapping,
        how="left",
        on="_geo_row_id",
        validate="one_to_one",
    )

    enriched["spatial_mapping_status"] = (
        enriched["taxi_zone_location_id"]
        .notna()
        .map({True: MAPPED_STATUS, False: OUTSIDE_STATUS})
    )

    # Nullable integer; outside-polygon records remain null by design.
    enriched["taxi_zone_location_id"] = (
        enriched["taxi_zone_location_id"].astype("Int64")
    )

    if len(enriched) != len(silver):
        raise RuntimeError(
            f"ROW_PRESERVATION_FAILURE: input={len(silver):,}, "
            f"output={len(enriched):,}"
        )

    if enriched["unique_key"].duplicated().any():
        raise RuntimeError(
            f"ROW_PRESERVATION_FAILURE: duplicate unique_key after mapping 2025-{mt}"
        )

    assigned_special = enriched["taxi_zone_location_id"].isin([264, 265]).sum()
    if assigned_special:
        raise RuntimeError(
            f"INVALID_SPATIAL_ASSIGNMENT: {assigned_special} records received "
            "special non-polygon Taxi Zone IDs 264/265"
        )

    return enriched.drop(columns=["_geo_row_id"])


def write_month_output(
    df: pd.DataFrame,
    month: int,
    run_id: str,
) -> tuple[Path, int]:
    mt = f"{month:02d}"
    output_dir = OUTPUT_ROOT / f"month={mt}"

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = (
        output_dir
        / f"part-00000-{run_id.replace('-', '')}.parquet"
    )

    # Preserve all Phase 10 fields and append mapping fields.
    table = pa.Table.from_pandas(
        df,
        preserve_index=False,
    )

    pq.write_table(
        table,
        output_file,
        compression="snappy",
    )

    verified = pq.ParquetFile(output_file).metadata.num_rows
    return output_file, verified


def update_mapping_reconciliation(rows: list[dict]) -> None:
    MAPPING_RECONCILIATION.parent.mkdir(parents=True, exist_ok=True)

    new_df = pd.DataFrame(rows)

    if MAPPING_RECONCILIATION.exists():
        existing = pd.read_csv(MAPPING_RECONCILIATION)
        incoming = set(new_df["processing_month"].astype(str))
        existing = existing[
            ~existing["processing_month"].astype(str).isin(incoming)
        ]
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df

    combined = combined.sort_values("processing_month").reset_index(drop=True)
    combined.to_csv(MAPPING_RECONCILIATION, index=False)


def process_month(
    month: int,
    zones: gpd.GeoDataFrame,
    phase10_rec: pd.DataFrame,
) -> dict:
    mt = f"{month:02d}"
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    print("\n" + "=" * 78)
    print(f"PHASE 12 - 311 -> TAXI ZONE SPATIAL MAPPING - 2025-{mt}")
    print("=" * 78)
    print(f"Run ID: {run_id}")
    print(f"Point CRS: {POINT_CRS}")
    print(f"Polygon CRS: {zones.crs}")
    print("Predicate: within")
    print("Fallback assignment: NONE")

    try:
        silver = read_silver_month(month)

        rec_row = phase10_rec.loc[
            phase10_rec["processing_month"].astype(str) == f"2025-{mt}"
        ]
        if len(rec_row) != 1:
            raise RuntimeError(
                f"PHASE10_MONTH_RECONCILIATION_FAILURE: 2025-{mt}"
            )

        expected_silver = int(rec_row.iloc[0]["silver_rows"])
        if len(silver) != expected_silver:
            raise RuntimeError(
                f"PHASE10_MONTH_ROW_FAILURE: expected {expected_silver:,}, "
                f"found {len(silver):,}"
            )

        enriched = spatial_map(silver, zones, month)

        mapped_rows = int(
            (enriched["spatial_mapping_status"] == MAPPED_STATUS).sum()
        )
        outside_rows = int(
            (enriched["spatial_mapping_status"] == OUTSIDE_STATUS).sum()
        )

        if mapped_rows + outside_rows != len(enriched):
            raise RuntimeError(
                "MAPPING_RECONCILIATION_FAILURE: mapped + outside != input"
            )

        mapping_success_pct = (
            100.0 * mapped_rows / len(enriched)
            if len(enriched)
            else 0.0
        )

        output_file, verified_rows = write_month_output(
            enriched,
            month,
            run_id,
        )

        if verified_rows != len(enriched):
            raise RuntimeError(
                f"PARQUET_RECONCILIATION_FAILURE: expected {len(enriched):,}, "
                f"verified {verified_rows:,}"
            )

        result = {
            "run_id": run_id,
            "processing_month": f"2025-{mt}",
            "valid_311_rows": len(enriched),
            "successfully_mapped": mapped_rows,
            "unmapped_outside_taxi_polygons": outside_rows,
            "mapping_success_pct": round(mapping_success_pct, 6),
            "status": "SUCCESS",
        }

        write_run_log(
            {
                "phase": 12,
                "pipeline": "311_taxi_zone_mapping",
                **result,
                "started_at": started_at.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "output_file": str(output_file),
                "point_crs": POINT_CRS,
                "polygon_crs": str(zones.crs),
                "spatial_predicate": "within",
            }
        )

        print(f"Valid Silver rows: {len(enriched):,}")
        print(f"Successfully mapped: {mapped_rows:,}")
        print(f"Outside Taxi polygons: {outside_rows:,}")
        print(f"Mapping success: {mapping_success_pct:.4f}%")
        print(f"Verified output rows: {verified_rows:,}")
        print("Row preservation: PASS")
        print(f"2025-{mt}: SPATIAL MAPPING SUCCESS")

        return result

    except Exception as exc:
        write_run_log(
            {
                "phase": 12,
                "pipeline": "311_taxi_zone_mapping",
                "run_id": run_id,
                "processing_month": f"2025-{mt}",
                "started_at": started_at.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "status": "FAILED",
                "error_message": str(exc),
            }
        )
        print(f"2025-{mt}: SPATIAL MAPPING FAILED")
        print(f"Error: {exc}")
        raise


def write_full_year_summary(
    profile: dict,
    phase10_rec: pd.DataFrame,
    mapping_rows: pd.DataFrame,
) -> None:
    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)

    total_raw = int(profile["row_count"])
    missing_coords = int(
        profile["candidate_anomalies"]["MISSING_COORDINATES"]
    )
    valid_silver = int(phase10_rec["silver_rows"].sum())
    total_distinct_dq_rejected = total_raw - valid_silver

    # This reconciles source-level exclusions without double-counting the
    # 83 complaints that failed both missing-coordinate and duration rules.
    other_dq_only = total_distinct_dq_rejected - missing_coords

    mapped = int(mapping_rows["successfully_mapped"].sum())
    outside = int(
        mapping_rows["unmapped_outside_taxi_polygons"].sum()
    )

    if mapped + outside != valid_silver:
        raise RuntimeError(
            "FULL_YEAR_MAPPING_RECONCILIATION_FAILURE: "
            f"mapped {mapped:,} + outside {outside:,} != "
            f"valid Silver {valid_silver:,}"
        )

    eligible_success_pct = (
        100.0 * mapped / valid_silver if valid_silver else 0.0
    )
    raw_coverage_pct = (
        100.0 * mapped / total_raw if total_raw else 0.0
    )

    summary = {
        "phase": 12,
        "status": "SUCCESS",
        "mapping_method": (
            "311 longitude/latitude -> EPSG:4326 point geometry -> "
            "reproject to EPSG:2263 -> point-in-polygon predicate=within "
            "-> TLC Taxi Zone LocationID"
        ),
        "authoritative_assignment_field": "taxi_zone_location_id",
        "borough_used_for_assignment": False,
        "nearest_polygon_fallback_used": False,
        "source_level_metrics": {
            "total_311_raw_records": total_raw,
            "unmapped_missing_coordinates": missing_coords,
            "other_distinct_dq_exclusions_only": other_dq_only,
            "total_distinct_dq_rejected": total_distinct_dq_rejected,
            "valid_311_silver_mapping_base": valid_silver,
        },
        "spatial_mapping_metrics": {
            "successfully_mapped": mapped,
            "unmapped_outside_taxi_polygons": outside,
            "mapping_success_pct_of_valid_silver": round(
                eligible_success_pct, 6
            ),
            "mapped_pct_of_total_raw_311": round(raw_coverage_pct, 6),
        },
        "taxi_zone_polygon_contract": {
            "polygon_count": EXPECTED_ZONE_POLYGONS,
            "location_id_min": 1,
            "location_id_max": 263,
            "special_non_polygon_ids_not_assignable": [264, 265],
            "polygon_crs": EXPECTED_ZONE_CRS,
        },
    }

    with SUMMARY_JSON.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Map Phase 10 NYC 311 Silver records to TLC Taxi Zones."
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

    profile, phase10_rec = load_source_contracts()
    zones = load_zones()

    print("=" * 78)
    print("PHASE 12 - GEOSPATIAL MAPPING")
    print("=" * 78)
    print(f"Raw 311 records: {profile['row_count']:,}")
    print(
        "Source rows missing coordinates:",
        f"{profile['candidate_anomalies']['MISSING_COORDINATES']:,}",
    )
    print(
        "Valid Phase 10 Silver mapping base:",
        f"{int(phase10_rec['silver_rows'].sum()):,}",
    )
    print(f"Taxi Zone polygons: {len(zones)}")
    print(f"Point CRS: {POINT_CRS}")
    print(f"Taxi Zone CRS: {zones.crs}")
    print("Authoritative join: point-in-polygon")
    print("Borough assignment: NOT USED")
    print("Nearest-zone fallback: NOT USED")

    results = [
        process_month(month, zones, phase10_rec)
        for month in args.months
    ]
    update_mapping_reconciliation(results)

    print("\n" + "=" * 78)
    print("PHASE 12 RUN SUMMARY")
    print("=" * 78)

    result_df = pd.DataFrame(results)

    print(
        "Months processed:",
        ", ".join(f"{month:02d}" for month in args.months),
    )
    print(
        f"Valid 311 rows: {int(result_df['valid_311_rows'].sum()):,}"
    )
    print(
        "Successfully mapped:",
        f"{int(result_df['successfully_mapped'].sum()):,}",
    )
    print(
        "Outside Taxi polygons:",
        f"{int(result_df['unmapped_outside_taxi_polygons'].sum()):,}",
    )

    valid_total = int(result_df["valid_311_rows"].sum())
    mapped_total = int(result_df["successfully_mapped"].sum())
    pct = 100.0 * mapped_total / valid_total if valid_total else 0.0

    print(f"Mapping success: {pct:.4f}%")
    print(f"Reconciliation report: {MAPPING_RECONCILIATION}")

    if sorted(set(args.months)) == list(range(1, 13)):
        all_mapping = pd.read_csv(MAPPING_RECONCILIATION)

        if len(all_mapping) != 12:
            raise RuntimeError(
                f"FULL_YEAR_MAPPING_REPORT_FAILURE: expected 12 months, "
                f"found {len(all_mapping)}"
            )

        if int(all_mapping["valid_311_rows"].sum()) != EXPECTED_VALID_SILVER_ROWS:
            raise RuntimeError(
                "FULL_YEAR_MAPPING_ROW_FAILURE: valid mapping input does not "
                "equal Phase 10 full-year Silver rows"
            )

        write_full_year_summary(
            profile,
            phase10_rec,
            all_mapping,
        )

        print("Full-year row preservation: PASS")
        print(f"Summary report: {SUMMARY_JSON}")

    print("\nPHASE 12 GEOSPATIAL MAPPING: SUCCESS")


if __name__ == "__main__":
    main()
