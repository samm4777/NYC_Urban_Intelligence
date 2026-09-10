import csv
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[2]

LOOKUP_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "taxi_zones"
    / "taxi_zone_lookup.csv"
)

SHAPEFILE_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "taxi_zones"
    / "shapefile"
    / "taxi_zones"
)

REPORT_DIR = (
    PROJECT_ROOT
    / "reports"
    / "profiling"
)

EXPECTED_LOOKUP_ROWS = 265
EXPECTED_COLUMNS = [
    "LocationID",
    "Borough",
    "Zone",
    "service_zone",
]


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    print("=" * 78)
    print("PHASE 6 - TAXI ZONE DATA PROFILING")
    print("=" * 78)
    print(f"Run ID: {run_id}")

    if not LOOKUP_FILE.exists():
        raise FileNotFoundError(f"Lookup file not found: {LOOKUP_FILE}")

    df = pd.read_csv(
    LOOKUP_FILE,
    keep_default_na=False,
)

    print()
    print("1. LOOKUP ROW COUNT / SCHEMA")
    print("-" * 78)
    print(f"Rows: {len(df):,}")
    print(f"Expected rows: {EXPECTED_LOOKUP_ROWS:,}")
    print(f"Row-count match: {len(df) == EXPECTED_LOOKUP_ROWS}")
    print(f"Columns: {len(df.columns)}")
    print(f"Column list: {df.columns.tolist()}")

    schema_matches = list(df.columns) == EXPECTED_COLUMNS

    print(f"Expected schema match: {schema_matches}")

    schema_rows = [
        {
            "column_name": column,
            "data_type": str(df[column].dtype),
            "missing_count": int(df[column].isna().sum()),
            "distinct_count": int(df[column].nunique(dropna=True)),
        }
        for column in df.columns
    ]

    write_csv(
        REPORT_DIR / "taxi_zone_schema.csv",
        schema_rows,
        [
            "column_name",
            "data_type",
            "missing_count",
            "distinct_count",
        ],
    )

    print()
    print("2. MISSING VALUES / DUPLICATES")
    print("-" * 78)

    missing_location_id = int(df["LocationID"].isna().sum())
    missing_borough = int(df["Borough"].isna().sum())
    missing_zone = int(df["Zone"].isna().sum())
    missing_service_zone = int(df["service_zone"].isna().sum())

    duplicate_location_id_rows = int(
        df["LocationID"].duplicated(keep=False).sum()
    )

    exact_duplicate_rows = int(
        df.duplicated(keep=False).sum()
    )

    print(f"Missing LocationID: {missing_location_id:,}")
    print(f"Missing Borough: {missing_borough:,}")
    print(f"Missing Zone: {missing_zone:,}")
    print(f"Missing service_zone: {missing_service_zone:,}")
    print(f"Rows involved in duplicate LocationID: {duplicate_location_id_rows:,}")
    print(f"Rows involved in exact duplicates: {exact_duplicate_rows:,}")

    print()
    print("3. ID RANGE / CATEGORY DISTRIBUTIONS")
    print("-" * 78)

    location_ids = pd.to_numeric(
        df["LocationID"],
        errors="coerce",
    )

    print(f"LocationID min: {location_ids.min()}")
    print(f"LocationID max: {location_ids.max()}")
    print(f"Distinct LocationID: {location_ids.nunique(dropna=True)}")

    distribution_rows = []

    for column in ["Borough", "service_zone"]:
        counts = (
            df[column]
            .fillna("<NULL>")
            .astype(str)
            .value_counts(dropna=False)
        )

        print()
        print(f"{column} distribution:")

        for value, count in counts.items():
            print(f"  {value}: {count}")

            distribution_rows.append(
                {
                    "column_name": column,
                    "value": value,
                    "count": int(count),
                }
            )

    write_csv(
        REPORT_DIR / "taxi_zone_distributions.csv",
        distribution_rows,
        ["column_name", "value", "count"],
    )

    print()
    print("4. DEFINITELY INVALID / CANDIDATE ANOMALIES")
    print("-" * 78)

    definitely_invalid = [
        {
            "classification": "DEFINITELY_INVALID",
            "check_name": "MISSING_LOCATION_ID",
            "description": "Taxi Zone lookup row is missing LocationID.",
            "record_count": missing_location_id,
        },
        {
            "classification": "DEFINITELY_INVALID",
            "check_name": "DUPLICATE_LOCATION_ID_ROWS",
            "description": "Rows participate in a duplicate LocationID.",
            "record_count": duplicate_location_id_rows,
        },
        {
            "classification": "DEFINITELY_INVALID",
            "check_name": "MISSING_ZONE_NAME",
            "description": "Taxi Zone lookup row is missing Zone name.",
            "record_count": missing_zone,
        },
    ]

    placeholder_mask = (
        df["Borough"].fillna("").astype(str).str.strip().str.upper()
        .isin(["UNKNOWN", "N/A", "NA", ""])
        |
        df["Zone"].fillna("").astype(str).str.strip().str.upper()
        .isin(["UNKNOWN", "N/A", "NA", ""])
    )

    candidate_anomalies = [
        {
            "classification": "CANDIDATE_ANOMALY",
            "check_name": "MISSING_BOROUGH",
            "description": "Borough is missing; assess whether this is an intentional reference value.",
            "record_count": missing_borough,
        },
        {
            "classification": "CANDIDATE_ANOMALY",
            "check_name": "MISSING_SERVICE_ZONE",
            "description": "service_zone is missing; assess whether this is expected for special zones.",
            "record_count": missing_service_zone,
        },
        {
            "classification": "CANDIDATE_ANOMALY",
            "check_name": "PLACEHOLDER_BOROUGH_OR_ZONE",
            "description": "Borough or Zone contains a placeholder such as Unknown or N/A.",
            "record_count": int(placeholder_mask.sum()),
        },
    ]

    for row in definitely_invalid + candidate_anomalies:
        print(
            f"{row['classification']} - "
            f"{row['check_name']}: {row['record_count']:,}"
        )

    write_csv(
        REPORT_DIR / "taxi_zone_definitely_invalid.csv",
        definitely_invalid,
        [
            "classification",
            "check_name",
            "description",
            "record_count",
        ],
    )

    write_csv(
        REPORT_DIR / "taxi_zone_candidate_anomalies.csv",
        candidate_anomalies,
        [
            "classification",
            "check_name",
            "description",
            "record_count",
        ],
    )

    print()
    print("5. GEOGRAPHIC FILE PRESENCE")
    print("-" * 78)

    expected_geo_files = [
        "taxi_zones.shp",
        "taxi_zones.shx",
        "taxi_zones.dbf",
        "taxi_zones.prj",
        "taxi_zones.cpg",
    ]

    geo_rows = []

    for filename in expected_geo_files:
        path = SHAPEFILE_DIR / filename

        geo_rows.append(
            {
                "file_name": filename,
                "exists": path.exists(),
                "file_size_bytes": path.stat().st_size if path.exists() else 0,
            }
        )

        print(
            f"{filename}: exists={path.exists()}, "
            f"size={path.stat().st_size if path.exists() else 0}"
        )

    write_csv(
        REPORT_DIR / "taxi_zone_geographic_files.csv",
        geo_rows,
        [
            "file_name",
            "exists",
            "file_size_bytes",
        ],
    )

    missing_geo_files = [
        row["file_name"]
        for row in geo_rows
        if not row["exists"]
    ]

    print()
    print("6. FINAL SUMMARY")
    print("-" * 78)

    summary = {
        "run_id": run_id,
        "source": "tlc_taxi_zones",
        "profile_year": 2025,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "lookup_row_count": len(df),
        "expected_lookup_row_count": EXPECTED_LOOKUP_ROWS,
        "row_count_match": len(df) == EXPECTED_LOOKUP_ROWS,
        "column_count": len(df.columns),
        "columns": df.columns.tolist(),
        "expected_schema_match": schema_matches,
        "location_id_min": (
            None if location_ids.empty else float(location_ids.min())
        ),
        "location_id_max": (
            None if location_ids.empty else float(location_ids.max())
        ),
        "distinct_location_ids": int(
            location_ids.nunique(dropna=True)
        ),
        "duplicate_location_id_rows": duplicate_location_id_rows,
        "missing_geographic_files": missing_geo_files,
        "definitely_invalid": {
            row["check_name"]: row["record_count"]
            for row in definitely_invalid
        },
        "candidate_anomalies": {
            row["check_name"]: row["record_count"]
            for row in candidate_anomalies
        },
        "status": "SUCCESS",
    }

    with open(
        REPORT_DIR / "taxi_zone_profile_summary.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(summary, f, indent=2)

    print(f"Rows profiled: {len(df):,}")
    print(f"Distinct LocationID values: {summary['distinct_location_ids']:,}")
    print(f"Missing geographic files: {len(missing_geo_files)}")
    print(f"Reports: {REPORT_DIR}")
    print()
    print("TAXI ZONE DATA PROFILING SUCCESS")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print()
        print("TAXI ZONE DATA PROFILING FAILED")
        print(f"Error: {exc}")
        sys.exit(1)
