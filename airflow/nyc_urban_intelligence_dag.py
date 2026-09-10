"""
NYC Urban Intelligence Platform
Initial Airflow DAG Skeleton

Final pipeline:
Ingestion -> Bronze -> Validation -> Silver -> Gold -> SQL Warehouse
"""

from datetime import datetime

try:
    from airflow import DAG
    from airflow.operators.empty import EmptyOperator
except ImportError:
    DAG = None


if DAG is not None:

    with DAG(
        dag_id="nyc_urban_intelligence_pipeline",
        description="End-to-end NYC Urban Intelligence data pipeline",
        start_date=datetime(2026, 9, 1),
        schedule=None,
        catchup=False,
        tags=["nyc", "data-engineering", "urban-intelligence"],
    ) as dag:

        ingest_sources = EmptyOperator(
            task_id="ingest_sources"
        )

        build_bronze = EmptyOperator(
            task_id="build_bronze"
        )

        validate_bronze = EmptyOperator(
            task_id="validate_bronze"
        )

        build_silver = EmptyOperator(
            task_id="build_silver"
        )

        build_gold = EmptyOperator(
            task_id="build_gold"
        )

        load_sql_warehouse = EmptyOperator(
            task_id="load_sql_warehouse"
        )

        run_post_load_tests = EmptyOperator(
            task_id="run_post_load_tests"
        )

        (
            ingest_sources
            >> build_bronze
            >> validate_bronze
            >> build_silver
            >> build_gold
            >> load_sql_warehouse
            >> run_post_load_tests
        )