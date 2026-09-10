import csv
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

REPORT_DIR = PROJECT_ROOT / "reports" / "reconciliation"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

RECONCILIATION_FILE = REPORT_DIR / "reconciliation_log.csv"


def record_reconciliation(
    run_id,
    source,
    processing_month,
    stage,
    row_count,
):
    """Record row counts at each pipeline stage."""

    file_exists = RECONCILIATION_FILE.exists()

    with open(
        RECONCILIATION_FILE,
        "a",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.writer(file)

        if not file_exists:
            writer.writerow(
                [
                    "run_id",
                    "source",
                    "processing_month",
                    "stage",
                    "row_count",
                    "recorded_at",
                ]
            )

        writer.writerow(
            [
                run_id,
                source,
                processing_month,
                stage,
                row_count,
                datetime.now(timezone.utc).isoformat(),
            ]
        )