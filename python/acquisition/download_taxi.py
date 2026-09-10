import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlunparse

import pyarrow.parquet as pq
import requests


# ---------------------------------------------------------
# Project imports
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from python.logging_utils import (
    generate_run_id,
    utc_now,
    write_run_log,
)


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

YEAR = 2025

RAW_TAXI_ROOT = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "taxi"
)

REPORT_DIR = (
    PROJECT_ROOT
    / "reports"
    / "acquisition"
)

REPORT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

MANIFEST_FILE = (
    REPORT_DIR
    / "taxi_download_manifest.csv"
)


# ---------------------------------------------------------
# Source URL
# ---------------------------------------------------------

def build_source_url(filename):
    return urlunparse(
        (
            "https",
            "d37ci6vzurychx.cloudfront.net",
            f"/trip-data/{filename}",
            "",
            "",
            "",
        )
    )


# ---------------------------------------------------------
# Manifest
# ---------------------------------------------------------

def write_manifest(record):

    file_exists = MANIFEST_FILE.exists()

    fieldnames = [
        "run_id",
        "source",
        "year",
        "month",
        "file_name",
        "source_url",
        "download_timestamp_utc",
        "file_size_bytes",
        "row_count",
        "status",
        "error_message",
    ]

    with open(
        MANIFEST_FILE,
        "a",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        if not file_exists:
            writer.writeheader()

        writer.writerow(record)


# ---------------------------------------------------------
# Download one month
# ---------------------------------------------------------

def download_month(month):

    run_id = generate_run_id()
    started_at = utc_now()

    month_text = f"{month:02d}"

    filename = (
        f"yellow_tripdata_"
        f"{YEAR}-{month_text}.parquet"
    )

    source_url = build_source_url(filename)

    destination_dir = (
        RAW_TAXI_ROOT
        / f"year={YEAR}"
        / f"month={month_text}"
    )

    destination_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination_file = (
        destination_dir
        / filename
    )

    temporary_file = destination_file.with_suffix(
        ".parquet.part"
    )

    print()
    print("=" * 60)
    print(f"Downloading Yellow Taxi {YEAR}-{month_text}")
    print(f"Target: {destination_file}")
    print(f"Run ID: {run_id}")
    print("=" * 60)

    try:

        # -------------------------------------------------
        # Preserve immutable Raw data
        # -------------------------------------------------

        if destination_file.exists():

            file_size = destination_file.stat().st_size

            parquet_file = pq.ParquetFile(
                destination_file
            )

            row_count = (
                parquet_file.metadata.num_rows
            )

            print(
                f"File already exists. "
                f"Skipping download."
            )

            status = "SKIPPED_EXISTS"

            write_manifest(
                {
                    "run_id": run_id,
                    "source": "yellow_taxi",
                    "year": YEAR,
                    "month": month_text,
                    "file_name": filename,
                    "source_url": source_url,
                    "download_timestamp_utc": utc_now(),
                    "file_size_bytes": file_size,
                    "row_count": row_count,
                    "status": status,
                    "error_message": "",
                }
            )

            write_run_log(
                run_id=run_id,
                source="yellow_taxi",
                processing_month=f"{YEAR}-{month_text}",
                started_at=started_at,
                finished_at=utc_now(),
                rows_read=row_count,
                rows_valid=row_count,
                rows_rejected=0,
                status=status,
                error_message=None,
            )

            return

        # -------------------------------------------------
        # Download using streaming
        # -------------------------------------------------

        with requests.get(
            source_url,
            stream=True,
            timeout=(30, 300),
        ) as response:

            response.raise_for_status()

            with open(
                temporary_file,
                "wb",
            ) as file:

                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):

                    if chunk:
                        file.write(chunk)

        # Rename only after complete download
        temporary_file.replace(
            destination_file
        )

        # -------------------------------------------------
        # Collect acquisition metadata
        # -------------------------------------------------

        file_size = (
            destination_file.stat().st_size
        )

        parquet_file = pq.ParquetFile(
            destination_file
        )

        row_count = (
            parquet_file.metadata.num_rows
        )

        finished_at = utc_now()

        print(
            f"Download complete."
        )

        print(
            f"Rows: {row_count:,}"
        )

        print(
            f"Size: "
            f"{file_size / (1024 * 1024):.2f} MB"
        )

        # -------------------------------------------------
        # Acquisition manifest
        # -------------------------------------------------

        write_manifest(
            {
                "run_id": run_id,
                "source": "yellow_taxi",
                "year": YEAR,
                "month": month_text,
                "file_name": filename,
                "source_url": source_url,
                "download_timestamp_utc": finished_at,
                "file_size_bytes": file_size,
                "row_count": row_count,
                "status": "SUCCESS",
                "error_message": "",
            }
        )

        # -------------------------------------------------
        # Pipeline logging
        # -------------------------------------------------

        write_run_log(
            run_id=run_id,
            source="yellow_taxi",
            processing_month=f"{YEAR}-{month_text}",
            started_at=started_at,
            finished_at=finished_at,
            rows_read=row_count,
            rows_valid=row_count,
            rows_rejected=0,
            status="SUCCESS",
            error_message=None,
        )

    except Exception as exc:

        if temporary_file.exists():
            temporary_file.unlink()

        finished_at = utc_now()

        print(
            f"FAILED: {exc}"
        )

        write_manifest(
            {
                "run_id": run_id,
                "source": "yellow_taxi",
                "year": YEAR,
                "month": month_text,
                "file_name": filename,
                "source_url": source_url,
                "download_timestamp_utc": finished_at,
                "file_size_bytes": 0,
                "row_count": 0,
                "status": "FAILED",
                "error_message": str(exc),
            }
        )

        write_run_log(
            run_id=run_id,
            source="yellow_taxi",
            processing_month=f"{YEAR}-{month_text}",
            started_at=started_at,
            finished_at=finished_at,
            rows_read=0,
            rows_valid=0,
            rows_rejected=0,
            status="FAILED",
            error_message=str(exc),
        )

        raise


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Download NYC Yellow Taxi "
            "2025 monthly Parquet files."
        )
    )

    parser.add_argument(
        "--months",
        type=int,
        nargs="+",
        default=list(range(1, 13)),
        help=(
            "Months to download. "
            "Example: --months 1 2 3"
        ),
    )

    args = parser.parse_args()

    for month in args.months:

        if month < 1 or month > 12:
            raise ValueError(
                f"Invalid month: {month}"
            )

        download_month(month)


if __name__ == "__main__":
    main()