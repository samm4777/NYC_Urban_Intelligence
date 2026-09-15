"""
NYC Urban Intelligence Platform

Phase 19 — Airflow Orchestration
Phase 40 — Automated Testing integration

Implemented architecture:

Ingestion
    -> Bronze
    -> Validation
    -> Silver
    -> Gold
    -> SQL Warehouse
    -> Post-load Tests
    -> Phase 40 Pytest Gate

Gold remains the business-ready analytical layer.
Azure SQL is the serving warehouse loaded from Gold.

Airflow orchestrates the existing ETL components rather than
reimplementing transformation logic inside the DAG.

The DAG defaults to one month only for controlled incremental execution.
"""

from datetime import timedelta
import os
import sys
from pathlib import Path

import pendulum

from airflow.sdk import DAG, Param
from airflow.providers.standard.operators.bash import BashOperator


PROJECT_ROOT = Path(
    os.getenv(
        "NYC_PROJECT_ROOT",
        str(Path(__file__).resolve().parents[1]),
    )
).resolve()

ETL_PYTHON = os.getenv(
    "NYC_ETL_PYTHON",
    sys.executable,
)


def month_shell_setup() -> str:
    return r"""
set -euo pipefail

START_MONTH="{{ params.start_month }}"
END_MONTH="{{ params.end_month }}"

if [ "$START_MONTH" -gt "$END_MONTH" ]; then
    echo "ERROR: start_month cannot exceed end_month"
    exit 1
fi

MONTHS=$(seq "$START_MONTH" "$END_MONTH" | tr '\n' ' ')
echo "Processing 2025 month(s): $MONTHS"
"""


SQL_ENV = {
    "NYC_AZURE_SQL_PASSWORD": "{{ conn.nyc_azure_sql.password }}",
    "NYC_AZURE_SQL_SERVER": "{{ conn.nyc_azure_sql.host }}",
    "NYC_AZURE_SQL_DATABASE": "{{ conn.nyc_azure_sql.schema }}",
    "NYC_AZURE_SQL_USER": "{{ conn.nyc_azure_sql.login }}",
}


with DAG(
    dag_id="nyc_urban_intelligence_pipeline",
    description="End-to-end NYC Urban Intelligence monthly data pipeline",
    start_date=pendulum.datetime(2026, 9, 1, tz="UTC"),
    schedule=None,
    catchup=False,
    params={
        "start_month": Param(
            1,
            type="integer",
            minimum=1,
            maximum=12,
            description="First 2025 month to process.",
        ),
        "end_month": Param(
            1,
            type="integer",
            minimum=1,
            maximum=12,
            description="Last 2025 month to process.",
        ),
    },
    tags=[
        "nyc",
        "data-engineering",
        "urban-intelligence",
        "phase19",
        "phase40",
    ],
) as dag:

    ingest_sources = BashOperator(
        task_id="ingest_sources",
        cwd=str(PROJECT_ROOT),
        bash_command=month_shell_setup()
        + f"""
{ETL_PYTHON} python/acquisition/download_taxi.py --months $MONTHS
{ETL_PYTHON} python/acquisition/download_311.py --months $MONTHS
{ETL_PYTHON} python/acquisition/download_weather.py --months $MONTHS
{ETL_PYTHON} python/acquisition/download_taxi_zones.py
""",
    )

    build_bronze = BashOperator(
        task_id="build_bronze",
        cwd=str(PROJECT_ROOT),
        bash_command=month_shell_setup()
        + f"""
{ETL_PYTHON} spark/build_taxi_bronze.py --months $MONTHS
""",
    )

    validate_bronze = BashOperator(
        task_id="validate_bronze",
        cwd=str(PROJECT_ROOT),
        bash_command=month_shell_setup()
        + f"""
{ETL_PYTHON} spark/validate_taxi_bronze.py --months $MONTHS
""",
    )

    build_silver = BashOperator(
        task_id="build_silver",
        cwd=str(PROJECT_ROOT),
        bash_command=month_shell_setup()
        + f"""
{ETL_PYTHON} spark/build_taxi_silver.py --months $MONTHS
{ETL_PYTHON} python/prepare_311_silver.py --months $MONTHS
{ETL_PYTHON} python/prepare_weather_silver.py --months $MONTHS
{ETL_PYTHON} python/map_311_to_taxi_zones.py --months $MONTHS
""",
    )

    build_gold = BashOperator(
        task_id="build_gold",
        cwd=str(PROJECT_ROOT),
        bash_command=month_shell_setup()
        + f"""
{ETL_PYTHON} python/build_gold_zone_hourly.py --months $MONTHS
""",
    )

    load_sql_warehouse = BashOperator(
        retries=2,
        retry_delay=timedelta(minutes=1),
        task_id="load_sql_warehouse",
        cwd=str(PROJECT_ROOT),
        env=SQL_ENV,
        append_env=True,
        bash_command=month_shell_setup()
        + f"""
{ETL_PYTHON} python/load_gold_incremental_logged.py \
  --server "$NYC_AZURE_SQL_SERVER" \
  --database "$NYC_AZURE_SQL_DATABASE" \
  --user "$NYC_AZURE_SQL_USER" \
  --year 2025 \
  --start-month "$START_MONTH" \
  --end-month "$END_MONTH"
""",
    )

    run_post_load_tests = BashOperator(
        retries=2,
        retry_delay=timedelta(minutes=1),
        task_id="run_post_load_tests",
        cwd=str(PROJECT_ROOT),
        env=SQL_ENV,
        append_env=True,
        bash_command=month_shell_setup()
        + f"""
{ETL_PYTHON} python/validate_phase19_warehouse.py \
  --server "$NYC_AZURE_SQL_SERVER" \
  --database "$NYC_AZURE_SQL_DATABASE" \
  --user "$NYC_AZURE_SQL_USER" \
  --year 2025 \
  --start-month "$START_MONTH" \
  --end-month "$END_MONTH"
""",
    )

    run_phase40_pytest = BashOperator(
        retries=2,
        retry_delay=timedelta(minutes=1),
        task_id="run_phase40_pytest",
        cwd=str(PROJECT_ROOT),
        env=SQL_ENV,
        append_env=True,
        bash_command=f"""
set -euo pipefail

{ETL_PYTHON} -m pytest tests/test_warehouse_quality.py -q
""",
    )

    (
        ingest_sources
        >> build_bronze
        >> validate_bronze
        >> build_silver
        >> build_gold
        >> load_sql_warehouse
        >> run_post_load_tests
        >> run_phase40_pytest
    )
