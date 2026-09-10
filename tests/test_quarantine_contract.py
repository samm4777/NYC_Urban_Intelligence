import csv
from pathlib import Path

import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REASON_CODES_FILE = PROJECT_ROOT / "data_quality" / "reason_codes.csv"
QUARANTINE_ROOT = PROJECT_ROOT / "data" / "quarantine"

REQUIRED_QUARANTINE_COLUMNS = {
    "source",
    "reason_code",
    "reason_description",
    "run_id",
    "rejected_at",
    "original_record",
}

REQUIRED_REASON_COLUMNS = {
    "rule_id",
    "reason_code",
    "source",
    "reason_description",
    "severity",
    "action",
    "record_level",
}


def load_reason_codes():
    with REASON_CODES_FILE.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as f:
        return list(csv.DictReader(f))


def test_reason_code_dictionary_exists():
    assert REASON_CODES_FILE.exists()
    assert load_reason_codes()


def test_reason_code_dictionary_has_required_columns():
    with REASON_CODES_FILE.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as f:
        reader = csv.DictReader(f)
        assert REQUIRED_REASON_COLUMNS.issubset(
            set(reader.fieldnames or [])
        )


def test_reason_codes_are_unique_and_nonempty():
    rows = load_reason_codes()

    codes = [row["reason_code"].strip() for row in rows]
    rule_ids = [row["rule_id"].strip() for row in rows]

    assert all(codes)
    assert all(rule_ids)
    assert len(codes) == len(set(codes))
    assert len(rule_ids) == len(set(rule_ids))


def test_required_example_reason_categories_are_covered():
    codes = {
        row["reason_code"]
        for row in load_reason_codes()
    }

    assert "INVALID_TRIP_DURATION" in codes
    assert "MISSING_TAXI_LOCATION" in codes
    assert "INVALID_PICKUP_DATE" in codes
    assert "DUPLICATE_TAXI_RECORD" in codes
    assert "MISSING_311_COORDINATES" in codes
    assert "TAXI_SCHEMA_MISMATCH" in codes


def test_existing_quarantine_files_follow_contract():
    parquet_files = sorted(
        QUARANTINE_ROOT.rglob("*.parquet")
    )

    for path in parquet_files:
        schema = pq.read_schema(path)
        assert REQUIRED_QUARANTINE_COLUMNS.issubset(
            set(schema.names)
        ), f"{path} missing required quarantine columns"
