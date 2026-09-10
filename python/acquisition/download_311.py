import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv


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
# Environment
# ---------------------------------------------------------

load_dotenv(PROJECT_ROOT / ".env")

NYC311_API_TOKEN = os.getenv("NYC311_API_TOKEN")


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

YEAR = 2025
PAGE_SIZE = 50000

BASE_URL = (
    "https://data.cityofnewyork.us/"
    "resource/erm2-nwe9.json"
)

RAW_ROOT = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "complaints_311"
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
    / "complaints_311_manifest.csv"
)


# ---------------------------------------------------------
# Date helpers
# ---------------------------------------------------------

def month_range(year, month):

    start = datetime(
        year,
        month,
        1,
        tzinfo=timezone.utc,
    )

    if month == 12:
        end = datetime(
            year + 1,
            1,
            1,
            tzinfo=timezone.utc,
        )
    else:
        end = datetime(
            year,
            month + 1,
            1,
            tzinfo=timezone.utc,
        )

    return start, end


def socrata_timestamp(value):
    return value.strftime("%Y-%m-%dT%H:%M:%S.000")


# ---------------------------------------------------------
# Manifest
# ---------------------------------------------------------

def write_manifest(record):

    file_exists = MANIFEST_FILE.exists()

    fields = [
        "run_id",
        "source",
        "year",
        "month",
        "query_start",
        "query_end",
        "page_size",
        "offset",
        "page_number",
        "file_name",
        "row_count",
        "retrieval_timestamp_utc",
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
            fieldnames=fields,
        )

        if not file_exists:
            writer.writeheader()

        writer.writerow(record)


# ---------------------------------------------------------
# Download month
# ---------------------------------------------------------

def download_month(month):

    run_id = generate_run_id()
    started_at = utc_now()

    month_text = f"{month:02d}"

    start_date, end_date = month_range(
        YEAR,
        month,
    )

    query_start = socrata_timestamp(
        start_date
    )

    query_end = socrata_timestamp(
        end_date
    )

    destination_dir = (
        RAW_ROOT
        / f"year={YEAR}"
        / f"month={month_text}"
    )

    destination_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    headers = {}

    if NYC311_API_TOKEN:
        headers["X-App-Token"] = (
            NYC311_API_TOKEN
        )

    offset = 0
    page_number = 1
    total_rows = 0

    print()
    print("=" * 70)
    print(
        f"Downloading NYC 311 "
        f"{YEAR}-{month_text}"
    )
    print(
        f"Query range: "
        f"{query_start} -> {query_end}"
    )
    print(f"Run ID: {run_id}")
    print("=" * 70)

    try:

        while True:

            file_name = (
                f"311_{YEAR}_{month_text}_"
                f"page_{page_number:04d}.json"
            )

            destination_file = (
                destination_dir
                / file_name
            )

            params = {
                "$where": (
                    f"created_date >= "
                    f"'{query_start}' "
                    f"AND created_date < "
                    f"'{query_end}'"
                ),
                "$limit": PAGE_SIZE,
                "$offset": offset,
                "$order": "created_date,unique_key",
            }

            print(
                f"Page {page_number} | "
                f"Offset {offset:,}"
            )

            response = requests.get(
                BASE_URL,
                params=params,
                headers=headers,
                timeout=(30, 300),
            )

            response.raise_for_status()

            records = response.json()

            row_count = len(records)

            # ---------------------------------------------
            # No more records
            # ---------------------------------------------

            if row_count == 0:
                break

            # ---------------------------------------------
            # Preserve Raw API response
            # ---------------------------------------------

            with open(
                destination_file,
                "w",
                encoding="utf-8",
            ) as file:

                json.dump(
                    records,
                    file,
                    ensure_ascii=False,
                )

            retrieval_time = utc_now()

            total_rows += row_count

            write_manifest(
                {
                    "run_id": run_id,
                    "source": "nyc_311",
                    "year": YEAR,
                    "month": month_text,
                    "query_start": query_start,
                    "query_end": query_end,
                    "page_size": PAGE_SIZE,
                    "offset": offset,
                    "page_number": page_number,
                    "file_name": file_name,
                    "row_count": row_count,
                    "retrieval_timestamp_utc": retrieval_time,
                    "status": "SUCCESS",
                    "error_message": "",
                }
            )

            print(
                f"Retrieved: "
                f"{row_count:,} rows"
            )

            # Last page
            if row_count < PAGE_SIZE:
                break

            offset += PAGE_SIZE
            page_number += 1

        finished_at = utc_now()

        write_run_log(
            run_id=run_id,
            source="nyc_311",
            processing_month=(
                f"{YEAR}-{month_text}"
            ),
            started_at=started_at,
            finished_at=finished_at,
            rows_read=total_rows,
            rows_valid=total_rows,
            rows_rejected=0,
            status="SUCCESS",
            error_message=None,
        )

        print("-" * 70)
        print(
            f"Month complete."
        )
        print(
            f"Total rows: "
            f"{total_rows:,}"
        )
        print("-" * 70)

    except Exception as exc:

        finished_at = utc_now()

        write_run_log(
            run_id=run_id,
            source="nyc_311",
            processing_month=(
                f"{YEAR}-{month_text}"
            ),
            started_at=started_at,
            finished_at=finished_at,
            rows_read=total_rows,
            rows_valid=total_rows,
            rows_rejected=0,
            status="FAILED",
            error_message=str(exc),
        )

        print(
            f"FAILED: {exc}"
        )

        raise


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Download paginated NYC 311 "
            "Service Requests for 2025."
        )
    )

    parser.add_argument(
        "--months",
        nargs="+",
        type=int,
        default=list(range(1, 13)),
        help=(
            "Months to download. "
            "Example: --months 1 2"
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