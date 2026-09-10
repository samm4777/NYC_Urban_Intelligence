import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


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
# HTTP session with retry support
# ---------------------------------------------------------

def create_session():

    session = requests.Session()

    retry_strategy = Retry(
        total=5,
        connect=5,
        read=5,
        status=5,
        backoff_factor=2,
        status_forcelist=[
            429,
            500,
            502,
            503,
            504,
        ],
        allowed_methods=["GET"],
        raise_on_status=False,
    )

    adapter = HTTPAdapter(
        max_retries=retry_strategy
    )

    session.mount(
        "https://",
        adapter,
    )

    session.mount(
        "http://",
        adapter,
    )

    return session


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

    return value.strftime(
        "%Y-%m-%dT%H:%M:%S.000"
    )


# ---------------------------------------------------------
# Manifest writer
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
# Validate existing Raw page
# ---------------------------------------------------------

def read_existing_page(file_path):

    try:

        with open(
            file_path,
            "r",
            encoding="utf-8",
        ) as file:

            records = json.load(file)

        if not isinstance(records, list):
            raise ValueError(
                "Existing Raw file does not "
                "contain a JSON array."
            )

        return len(records)

    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
        ValueError,
    ):

        print(
            f"Existing page is invalid: "
            f"{file_path.name}"
        )

        print(
            "Removing invalid page so it "
            "can be downloaded again."
        )

        file_path.unlink()

        return None


# ---------------------------------------------------------
# Download one month
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

    headers = {
        "Accept": "application/json"
    }

    if NYC311_API_TOKEN:

        headers["X-App-Token"] = (
            NYC311_API_TOKEN
        )

    session = create_session()

    offset = 0
    page_number = 1
    total_rows = 0
    resumed_pages = 0
    downloaded_pages = 0

    current_file_name = ""
    current_offset = 0
    current_page_number = 1

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

    print(
        f"Page size: {PAGE_SIZE:,}"
    )

    print(
        f"Run ID: {run_id}"
    )

    print("=" * 70)

    try:

        while True:

            # -------------------------------------------------
            # Build Raw page filename
            # -------------------------------------------------

            file_name = (
                f"311_{YEAR}_{month_text}_"
                f"page_{page_number:04d}.json"
            )

            destination_file = (
                destination_dir
                / file_name
            )

            temporary_file = (
                destination_dir
                / f"{file_name}.part"
            )

            current_file_name = file_name
            current_offset = offset
            current_page_number = page_number

            # -------------------------------------------------
            # Resume support
            # -------------------------------------------------

            if destination_file.exists():

                existing_count = (
                    read_existing_page(
                        destination_file
                    )
                )

                if existing_count is not None:

                    print(
                        f"Page already exists | "
                        f"Page {page_number} | "
                        f"Offset {offset:,} | "
                        f"Rows {existing_count:,}"
                    )

                    total_rows += existing_count
                    resumed_pages += 1

                    # Existing final page
                    if existing_count < PAGE_SIZE:
                        break

                    offset += PAGE_SIZE
                    page_number += 1

                    continue

            # Remove an abandoned partial file
            if temporary_file.exists():

                print(
                    f"Removing incomplete temporary file: "
                    f"{temporary_file.name}"
                )

                temporary_file.unlink()

            # -------------------------------------------------
            # API query
            # -------------------------------------------------

            params = {

                "$where": (
                    f"created_date >= "
                    f"'{query_start}' "
                    f"AND created_date < "
                    f"'{query_end}'"
                ),

                "$limit": PAGE_SIZE,

                "$offset": offset,

                "$order": (
                    "created_date ASC,"
                    "unique_key ASC"
                ),
            }

            print(
                f"Requesting page "
                f"{page_number} | "
                f"Offset {offset:,}"
            )

            response = session.get(
                BASE_URL,
                params=params,
                headers=headers,
                timeout=(30, 300),
            )

            response.raise_for_status()

            # Preserve the response payload exactly as returned by the API.
            # We still parse the JSON in memory only to validate the payload
            # and count records; the parsed object is never written to Raw.
            raw_bytes = response.content

            try:
                records = response.json()
            except ValueError as exc:
                raise ValueError(
                    "NYC 311 API returned invalid JSON."
                ) from exc

            if not isinstance(records, list):

                raise ValueError(
                    "NYC 311 API response "
                    "was not a JSON array."
                )

            row_count = len(records)

            # -------------------------------------------------
            # No additional records
            # -------------------------------------------------

            if row_count == 0:

                print(
                    "No additional records returned."
                )

                break

            # -------------------------------------------------
            # Preserve exact Raw API response bytes
            # -------------------------------------------------

            with open(
                temporary_file,
                "wb",
            ) as file:

                file.write(raw_bytes)

            # Only make it a real Raw page after
            # the write completes successfully.
            temporary_file.replace(
                destination_file
            )

            retrieval_time = utc_now()

            total_rows += row_count
            downloaded_pages += 1

            # -------------------------------------------------
            # Acquisition manifest
            # -------------------------------------------------

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

            # -------------------------------------------------
            # Final page
            # -------------------------------------------------

            if row_count < PAGE_SIZE:
                break

            offset += PAGE_SIZE
            page_number += 1

        # -----------------------------------------------------
        # Successful monthly run
        # -----------------------------------------------------

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
            "Month complete."
        )

        print(
            f"Total rows: "
            f"{total_rows:,}"
        )

        print(
            f"Existing pages reused: "
            f"{resumed_pages}"
        )

        print(
            f"New pages downloaded: "
            f"{downloaded_pages}"
        )

        print("-" * 70)

    except Exception as exc:

        finished_at = utc_now()

        error_message = str(exc)

        # -----------------------------------------------------
        # Record failed page in acquisition manifest
        # -----------------------------------------------------

        write_manifest(
            {
                "run_id": run_id,
                "source": "nyc_311",
                "year": YEAR,
                "month": month_text,
                "query_start": query_start,
                "query_end": query_end,
                "page_size": PAGE_SIZE,
                "offset": current_offset,
                "page_number": current_page_number,
                "file_name": current_file_name,
                "row_count": 0,
                "retrieval_timestamp_utc": utc_now(),
                "status": "FAILED",
                "error_message": error_message,
            }
        )

        # -----------------------------------------------------
        # Run-level failure log
        # -----------------------------------------------------

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
            error_message=error_message,
        )

        print(
            f"FAILED: {error_message}"
        )

        raise

    finally:

        session.close()


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
        default=list(
            range(1, 13)
        ),
        help=(
            "Months to download. "
            "Example: --months 1 2 3"
        ),
    )

    args = parser.parse_args()

    for month in args.months:

        if month < 1 or month > 12:

            raise ValueError(
                f"Invalid month: {month}. "
                f"Month must be between "
                f"1 and 12."
            )

        download_month(month)


if __name__ == "__main__":
    main()