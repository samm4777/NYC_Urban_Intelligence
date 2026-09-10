import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_ROOT = (
    PROJECT_ROOT
    / "data"
    / "raw"
)

REPORT_DIR = (
    PROJECT_ROOT
    / "reports"
    / "raw_integrity"
)

REPORT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT_FILE = (
    REPORT_DIR
    / "raw_file_checksums.csv"
)


def sha256_file(file_path, chunk_size=1024 * 1024):

    digest = hashlib.sha256()

    with open(file_path, "rb") as file:

        while True:

            chunk = file.read(chunk_size)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def detect_source(relative_path):

    parts = relative_path.parts

    if not parts:
        return "unknown"

    return parts[0]


def extract_partition(relative_path):

    year = ""
    month = ""

    for part in relative_path.parts:

        if part.startswith("year="):
            year = part.split("=", 1)[1]

        if part.startswith("month="):
            month = part.split("=", 1)[1]

    return year, month


def main():

    files = sorted(
        path
        for path in RAW_ROOT.rglob("*")
        if path.is_file()
        and path.name != ".gitkeep"
    )

    generated_at = datetime.now(
        timezone.utc
    ).isoformat()

    rows = []

    print("=" * 70)
    print("RAW DATA INTEGRITY CHECKSUM GENERATION")
    print("=" * 70)

    for index, file_path in enumerate(
        files,
        start=1,
    ):

        relative_path = (
            file_path.relative_to(RAW_ROOT)
        )

        source = detect_source(
            relative_path
        )

        year, month = extract_partition(
            relative_path
        )

        size_bytes = (
            file_path.stat().st_size
        )

        print(
            f"[{index}/{len(files)}] "
            f"{relative_path}"
        )

        checksum = sha256_file(
            file_path
        )

        rows.append(
            {
                "source": source,
                "year": year,
                "month": month,
                "relative_path": str(
                    relative_path
                ).replace("\\", "/"),
                "file_size_bytes": size_bytes,
                "sha256": checksum,
                "baseline_generated_at_utc": (
                    generated_at
                ),
            }
        )

    fields = [
        "source",
        "year",
        "month",
        "relative_path",
        "file_size_bytes",
        "sha256",
        "baseline_generated_at_utc",
    ]

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields,
        )

        writer.writeheader()
        writer.writerows(rows)

    print()
    print("=" * 70)
    print(f"Files hashed: {len(rows)}")
    print(f"Manifest: {OUTPUT_FILE}")
    print("RAW CHECKSUM BASELINE CREATED")
    print("=" * 70)


if __name__ == "__main__":
    main()