import os
from pathlib import Path

from dotenv import load_dotenv


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)


# ---------------------------------------------------------
# Environment variables
# ---------------------------------------------------------

SQL_SERVER_HOST = os.getenv("SQL_SERVER_HOST")
SQL_SERVER_DATABASE = os.getenv("SQL_SERVER_DATABASE")
SQL_USER = os.getenv("SQL_USER")
SQL_PASSWORD = os.getenv("SQL_PASSWORD")
NYC311_API_TOKEN = os.getenv("NYC311_API_TOKEN")


# ---------------------------------------------------------
# Data lake paths
# ---------------------------------------------------------

DATA_DIR = PROJECT_ROOT / "data"

RAW_DIR = DATA_DIR / "raw"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"
QUARANTINE_DIR = DATA_DIR / "quarantine"


# ---------------------------------------------------------
# Other project directories
# ---------------------------------------------------------

REPORTS_DIR = PROJECT_ROOT / "reports"
SQL_DIR = PROJECT_ROOT / "sql"
MODEL_DIR = PROJECT_ROOT / "model"
DOCUMENTATION_DIR = PROJECT_ROOT / "documentation"