import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_ROOT / "logs"

LOG_DIR.mkdir(parents=True, exist_ok=True)


def generate_run_id():
    """Generate a unique ID for each pipeline execution."""
    return str(uuid.uuid4())


def setup_logger(name="nyc_urban_intelligence"):
    """Create a standard project logger."""

    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(logging.INFO)

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)

    return logger


def write_run_log(
    run_id,
    source,
    processing_month,
    started_at,
    finished_at,
    rows_read,
    rows_valid,
    rows_rejected,
    status,
    error_message=None,
):
    """Write structured pipeline execution information to JSON Lines."""

    log_record = {
        "run_id": run_id,
        "source": source,
        "processing_month": processing_month,
        "started_at": started_at,
        "finished_at": finished_at,
        "rows_read": rows_read,
        "rows_valid": rows_valid,
        "rows_rejected": rows_rejected,
        "status": status,
        "error_message": error_message,
    }

    log_file = LOG_DIR / "pipeline_runs.jsonl"

    with open(log_file, "a", encoding="utf-8") as file:
        file.write(json.dumps(log_record) + "\n")


def utc_now():
    """Return the current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()
    