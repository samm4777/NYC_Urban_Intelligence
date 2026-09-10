import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
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
# Configuration
# ---------------------------------------------------------

YEAR = 2025

LATITUDE = 40.7128
LONGITUDE = -74.0060
TIMEZONE = "America/New_York"

BASE_URL = "https://archive-api.open-meteo.com/v1/archive"

HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "precipitation",
    "rain",
    "snowfall",
    "weather_code",
    "wind_speed_10m",
    "wind_gusts_10m",
]

RAW_ROOT = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "weather"
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
    / "weather_download_manifest.csv"
)


# ---------------------------------------------------------
# HTTP session
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
            year,
            12,
            31,
            tzinfo=timezone.utc,
        )
    else:
        next_month = datetime(
            year,
            month + 1,
            1,
            tzinfo=timezone.utc,
        )

        end = next_month - timedelta(days=1)

    return (
        start.strftime("%Y-%m-%d"),
        end.strftime("%Y-%m-%d"),
    )


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
        "latitude",
        "longitude",
        "timezone",
        "query_start",
        "query_end",
        "hourly_variables",
        "file_name",
        "file_size_bytes",
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
# Validate existing Raw weather file
# ---------------------------------------------------------

def validate_existing_file(file_path):

    try:

        with open(
            file_path,
            "rb",
        ) as file:
            raw_bytes = file.read()

        payload = json.loads(
            raw_bytes.decode("utf-8")
        )

        hourly = payload.get("hourly")

        if not hourly:
            raise ValueError(
                "Missing hourly section."
            )

        times = hourly.get("time")

        if not isinstance(times, list):
            raise ValueError(
                "Missing hourly time array."
            )

        row_count = len(times)

        if row_count == 0:
            raise ValueError(
                "Hourly time array is empty."
            )

        for variable in HOURLY_VARIABLES:

            values = hourly.get(variable)

            if not isinstance(values, list):
                raise ValueError(
                    f"Missing hourly variable: {variable}"
                )

            if len(values) != row_count:
                raise ValueError(
                    f"Hourly array length mismatch for {variable}"
                )

        return row_count

    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
        ValueError,
        TypeError,
    ):

        print(
            f"Existing weather file is invalid: "
            f"{file_path.name}"
        )

        print(
            "Removing invalid file so it can "
            "be downloaded again."
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

    query_start, query_end = month_range(
        YEAR,
        month,
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

    file_name = (
        f"weather_nyc_{YEAR}_{month_text}.json"
    )

    destination_file = (
        destination_dir
        / file_name
    )

    temporary_file = (
        destination_dir
        / f"{file_name}.part"
    )

    print()
    print("=" * 70)

    print(
        f"NYC Weather {YEAR}-{month_text}"
    )

    print(
        f"Date range: "
        f"{query_start} -> {query_end}"
    )

    print(
        f"Run ID: {run_id}"
    )

    print("=" * 70)

    try:

        # -------------------------------------------------
        # Resume support
        # -------------------------------------------------

        if destination_file.exists():

            existing_count = (
                validate_existing_file(
                    destination_file
                )
            )

            if existing_count is not None:

                finished_at = utc_now()

                print(
                    "Raw weather file already exists."
                )

                print(
                    f"Hourly rows: "
                    f"{existing_count:,}"
                )

                write_run_log(
                    run_id=run_id,
                    source="weather",
                    processing_month=(
                        f"{YEAR}-{month_text}"
                    ),
                    started_at=started_at,
                    finished_at=finished_at,
                    rows_read=existing_count,
                    rows_valid=existing_count,
                    rows_rejected=0,
                    status="SKIPPED_EXISTS",
                    error_message=None,
                )

                return

        if temporary_file.exists():
            temporary_file.unlink()

        # -------------------------------------------------
        # API request
        # -------------------------------------------------

        params = {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "start_date": query_start,
            "end_date": query_end,
            "hourly": ",".join(
                HOURLY_VARIABLES
            ),
            "timezone": TIMEZONE,
        }

        session = create_session()

        try:

            response = session.get(
                BASE_URL,
                params=params,
                timeout=(30, 180),
            )

            response.raise_for_status()

            # Exact HTTP response body bytes.
            raw_bytes = response.content

            try:
                payload = response.json()
            except ValueError as exc:
                raise ValueError(
                    "Open-Meteo returned invalid JSON."
                ) from exc

        finally:
            session.close()

        # -------------------------------------------------
        # Validate API payload
        # -------------------------------------------------

        hourly = payload.get("hourly")

        if not hourly:
            raise ValueError(
                "Open-Meteo response contains "
                "no hourly section."
            )

        times = hourly.get("time")

        if not isinstance(times, list):
            raise ValueError(
                "Open-Meteo response contains "
                "no valid hourly time array."
            )

        row_count = len(times)

        if row_count == 0:
            raise ValueError(
                "Weather API returned zero rows."
            )

        for variable in HOURLY_VARIABLES:

            values = hourly.get(variable)

            if not isinstance(values, list):
                raise ValueError(
                    f"Missing hourly variable: "
                    f"{variable}"
                )

            if len(values) != row_count:
                raise ValueError(
                    f"Hourly array length mismatch "
                    f"for {variable}"
                )

        # -------------------------------------------------
        # Preserve exact Raw HTTP response bytes
        # -------------------------------------------------

        with open(
            temporary_file,
            "wb",
        ) as file:

            file.write(raw_bytes)

        temporary_file.replace(
            destination_file
        )

        finished_at = utc_now()

        file_size = (
            destination_file.stat().st_size
        )

        # -------------------------------------------------
        # Manifest
        # -------------------------------------------------

        write_manifest(
            {
                "run_id": run_id,
                "source": "open_meteo",
                "year": YEAR,
                "month": month_text,
                "latitude": LATITUDE,
                "longitude": LONGITUDE,
                "timezone": TIMEZONE,
                "query_start": query_start,
                "query_end": query_end,
                "hourly_variables": (
                    "|".join(
                        HOURLY_VARIABLES
                    )
                ),
                "file_name": file_name,
                "file_size_bytes": file_size,
                "row_count": row_count,
                "retrieval_timestamp_utc": finished_at,
                "status": "SUCCESS",
                "error_message": "",
            }
        )

        # -------------------------------------------------
        # Pipeline log
        # -------------------------------------------------

        write_run_log(
            run_id=run_id,
            source="weather",
            processing_month=(
                f"{YEAR}-{month_text}"
            ),
            started_at=started_at,
            finished_at=finished_at,
            rows_read=row_count,
            rows_valid=row_count,
            rows_rejected=0,
            status="SUCCESS",
            error_message=None,
        )

        print(
            "Download complete."
        )

        print(
            f"Hourly rows: "
            f"{row_count:,}"
        )

        print(
            f"File size: "
            f"{file_size:,} bytes"
        )

    except Exception as exc:

        if temporary_file.exists():
            temporary_file.unlink()

        finished_at = utc_now()

        write_manifest(
            {
                "run_id": run_id,
                "source": "open_meteo",
                "year": YEAR,
                "month": month_text,
                "latitude": LATITUDE,
                "longitude": LONGITUDE,
                "timezone": TIMEZONE,
                "query_start": query_start,
                "query_end": query_end,
                "hourly_variables": (
                    "|".join(
                        HOURLY_VARIABLES
                    )
                ),
                "file_name": file_name,
                "file_size_bytes": 0,
                "row_count": 0,
                "retrieval_timestamp_utc": finished_at,
                "status": "FAILED",
                "error_message": str(exc),
            }
        )

        write_run_log(
            run_id=run_id,
            source="weather",
            processing_month=(
                f"{YEAR}-{month_text}"
            ),
            started_at=started_at,
            finished_at=finished_at,
            rows_read=0,
            rows_valid=0,
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
            "Download hourly historical "
            "NYC weather for 2025."
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
                f"Invalid month: {month}"
            )

        download_month(month)


if __name__ == "__main__":
    main()
