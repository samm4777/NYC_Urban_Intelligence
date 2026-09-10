import csv
import sys
import zipfile
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from python.logging_utils import (
    generate_run_id,
    utc_now,
    write_run_log,
)


RAW_ZONE_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "taxi_zones"
)

REPORT_DIR = (
    PROJECT_ROOT
    / "reports"
    / "acquisition"
)

RAW_ZONE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

REPORT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

MANIFEST_FILE = (
    REPORT_DIR
    / "taxi_zone_download_manifest.csv"
)


ASSETS = [
    {
        "name": "taxi_zone_lookup.csv",
        "url": (
            "https://d37ci6vzurychx.cloudfront.net/"
            "misc/taxi_zone_lookup.csv"
        ),
        "extract": False,
    },
    {
        "name": "taxi_zones.zip",
        "url": (
            "https://d37ci6vzurychx.cloudfront.net/"
            "misc/taxi_zones.zip"
        ),
        "extract": True,
    },
]


def write_manifest(record):
    file_exists = MANIFEST_FILE.exists()

    fields = [
        "run_id",
        "source",
        "file_name",
        "source_url",
        "download_timestamp_utc",
        "file_size_bytes",
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


def download_asset(asset):

    run_id = generate_run_id()
    started_at = utc_now()

    file_name = asset["name"]
    source_url = asset["url"]

    destination = (
        RAW_ZONE_DIR
        / file_name
    )

    temporary_file = destination.with_suffix(
        destination.suffix + ".part"
    )

    print()
    print("=" * 60)
    print(f"Downloading: {file_name}")
    print(f"Target: {destination}")
    print(f"Run ID: {run_id}")
    print("=" * 60)

    try:

        if destination.exists():

            size = destination.stat().st_size

            print("File already exists. Skipping.")

            status = "SKIPPED_EXISTS"

            write_manifest(
                {
                    "run_id": run_id,
                    "source": "taxi_zones",
                    "file_name": file_name,
                    "source_url": source_url,
                    "download_timestamp_utc": utc_now(),
                    "file_size_bytes": size,
                    "status": status,
                    "error_message": "",
                }
            )

            write_run_log(
                run_id=run_id,
                source="taxi_zones",
                processing_month="reference",
                started_at=started_at,
                finished_at=utc_now(),
                rows_read=0,
                rows_valid=0,
                rows_rejected=0,
                status=status,
                error_message=None,
            )

            return

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

        temporary_file.replace(destination)

        size = destination.stat().st_size

        if asset["extract"]:

            extract_dir = (
                RAW_ZONE_DIR
                / "shapefile"
            )

            extract_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            with zipfile.ZipFile(
                destination,
                "r",
            ) as archive:

                archive.extractall(
                    extract_dir
                )

        finished_at = utc_now()

        print(
            f"Download complete: "
            f"{size / 1024:.2f} KB"
        )

        write_manifest(
            {
                "run_id": run_id,
                "source": "taxi_zones",
                "file_name": file_name,
                "source_url": source_url,
                "download_timestamp_utc": finished_at,
                "file_size_bytes": size,
                "status": "SUCCESS",
                "error_message": "",
            }
        )

        write_run_log(
            run_id=run_id,
            source="taxi_zones",
            processing_month="reference",
            started_at=started_at,
            finished_at=finished_at,
            rows_read=0,
            rows_valid=0,
            rows_rejected=0,
            status="SUCCESS",
            error_message=None,
        )

    except Exception as exc:

        if temporary_file.exists():
            temporary_file.unlink()

        finished_at = utc_now()

        print(f"FAILED: {exc}")

        write_manifest(
            {
                "run_id": run_id,
                "source": "taxi_zones",
                "file_name": file_name,
                "source_url": source_url,
                "download_timestamp_utc": finished_at,
                "file_size_bytes": 0,
                "status": "FAILED",
                "error_message": str(exc),
            }
        )

        write_run_log(
            run_id=run_id,
            source="taxi_zones",
            processing_month="reference",
            started_at=started_at,
            finished_at=finished_at,
            rows_read=0,
            rows_valid=0,
            rows_rejected=0,
            status="FAILED",
            error_message=str(exc),
        )

        raise


def main():

    for asset in ASSETS:
        download_asset(asset)


if __name__ == "__main__":
    main()