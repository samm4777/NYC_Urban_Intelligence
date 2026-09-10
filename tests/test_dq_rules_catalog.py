import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RULE_FILE = PROJECT_ROOT / "data_quality" / "dq_rules.csv"

REQUIRED_COLUMNS = {
    "rule_id",
    "rule_name",
    "description",
    "severity",
    "action",
}

ALLOWED_SEVERITIES = {
    "Critical",
    "High",
    "Medium",
    "Warning",
    "Info",
}


def load_rules():
    with RULE_FILE.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_dq_rule_catalog_exists_and_is_populated():
    assert RULE_FILE.exists()
    rules = load_rules()
    assert len(rules) >= 20


def test_dq_rule_catalog_has_required_columns():
    with RULE_FILE.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        assert REQUIRED_COLUMNS.issubset(set(reader.fieldnames or []))


def test_dq_rule_ids_are_unique_and_nonempty():
    rules = load_rules()
    rule_ids = [row["rule_id"].strip() for row in rules]

    assert all(rule_ids)
    assert len(rule_ids) == len(set(rule_ids))


def test_required_fields_are_nonempty():
    rules = load_rules()

    for row in rules:
        for field in REQUIRED_COLUMNS:
            assert row[field].strip(), f"{row.get('rule_id')} missing {field}"


def test_severity_values_are_controlled():
    rules = load_rules()

    invalid = {
        row["severity"]
        for row in rules
        if row["severity"] not in ALLOWED_SEVERITIES
    }

    assert not invalid, f"Unexpected severity values: {sorted(invalid)}"
