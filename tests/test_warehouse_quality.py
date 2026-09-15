"""
Phase 40 — Automated Warehouse Tests
NYC Urban Intelligence Platform
"""

import os
import time

import pyodbc
import pytest


SERVER = os.getenv(
    "NYC_AZURE_SQL_SERVER",
    "retailanalytics-sameer-484848.database.windows.net",
)
DATABASE = os.getenv(
    "NYC_AZURE_SQL_DATABASE",
    "NYC_Urban_Intelligence_DW",
)
USER = os.getenv(
    "NYC_AZURE_SQL_USER",
    "retailadmin",
)
PASSWORD = os.getenv("NYC_AZURE_SQL_PASSWORD")
DRIVER = os.getenv("NYC_SQL_DRIVER", "ODBC Driver 18 for SQL Server")


@pytest.fixture(scope="session")
def db():
    """Create one Azure SQL connection for the test session."""

    if not PASSWORD:
        pytest.fail(
            "NYC_AZURE_SQL_PASSWORD environment variable is not set."
        )

    connection_string = (
        f"DRIVER={{{DRIVER}}};"
        f"SERVER=tcp:{SERVER},1433;"
        f"DATABASE={DATABASE};"
        f"UID={USER};"
        f"PWD={PASSWORD};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
    )

    max_attempts = 5
    retry_delay_seconds = 15
    conn = None

    for attempt in range(1, max_attempts + 1):
        try:
            print(
                f"\nConnecting to Azure SQL "
                f"(attempt {attempt}/{max_attempts})..."
            )
            conn = pyodbc.connect(
                connection_string,
                autocommit=True,
                timeout=60,
            )
            break

        except pyodbc.Error as exc:
            if attempt == max_attempts:
                pytest.fail(
                    f"Azure SQL connection failed after "
                    f"{max_attempts} attempts: {exc}"
                )

            print(
                f"Connection attempt failed. "
                f"Retrying in {retry_delay_seconds} seconds..."
            )
            time.sleep(retry_delay_seconds)

    yield conn

    if conn is not None:
        conn.close()


def scalar(db, query):
    """Return the first column from the first SQL result row."""
    cursor = db.cursor()
    try:
        row = cursor.execute(query).fetchone()
        return row[0]
    finally:
        cursor.close()


def test_no_duplicate_zone_hourly_business_keys(db):
    duplicate_groups = scalar(
        db,
        """
        SELECT COUNT_BIG(*)
        FROM
        (
            SELECT date_key, time_key, zone_key
            FROM dw.FactZoneHourlyActivity
            GROUP BY date_key, time_key, zone_key
            HAVING COUNT_BIG(*) > 1
        ) AS duplicates;
        """,
    )
    assert duplicate_groups == 0


def test_no_duplicate_zone_hourly_surrogate_keys(db):
    duplicate_keys = scalar(
        db,
        """
        SELECT COUNT_BIG(*)
        FROM
        (
            SELECT zone_hourly_key
            FROM dw.FactZoneHourlyActivity
            GROUP BY zone_hourly_key
            HAVING COUNT_BIG(*) > 1
        ) AS duplicates;
        """,
    )
    assert duplicate_keys == 0


def test_zone_hourly_required_fields_not_null(db):
    null_rows = scalar(
        db,
        """
        SELECT COUNT_BIG(*)
        FROM dw.FactZoneHourlyActivity
        WHERE date_key IS NULL
           OR time_key IS NULL
           OR zone_key IS NULL
           OR weather_condition_key IS NULL
           OR taxi_trips IS NULL
           OR taxi_revenue IS NULL
           OR complaints_311 IS NULL
           OR temperature_c IS NULL
           OR rain_mm IS NULL
           OR snowfall_cm IS NULL;
        """,
    )
    assert null_rows == 0


def test_zone_hourly_dates_are_in_2025(db):
    invalid_dates = scalar(
        db,
        """
        SELECT COUNT_BIG(*)
        FROM dw.FactZoneHourlyActivity AS f
        INNER JOIN dw.DimDate AS d
            ON f.date_key = d.date_key
        WHERE d.full_date < '2025-01-01'
           OR d.full_date >= '2026-01-01';
        """,
    )
    assert invalid_dates == 0


def test_zone_hourly_dimension_relationships_complete(db):
    missing_relationships = scalar(
        db,
        """
        SELECT COUNT_BIG(*)
        FROM dw.FactZoneHourlyActivity AS f
        LEFT JOIN dw.DimDate AS d
            ON f.date_key = d.date_key
        LEFT JOIN dw.DimTime AS t
            ON f.time_key = t.time_key
        LEFT JOIN dw.DimZone AS z
            ON f.zone_key = z.zone_key
        LEFT JOIN dw.DimWeatherCondition AS w
            ON f.weather_condition_key = w.weather_condition_key
        WHERE d.date_key IS NULL
           OR t.time_key IS NULL
           OR z.zone_key IS NULL
           OR w.weather_condition_key IS NULL;
        """,
    )
    assert missing_relationships == 0


def test_full_year_gold_row_count(db):
    actual_rows = scalar(
        db,
        """
        SELECT COUNT_BIG(*)
        FROM dw.FactZoneHourlyActivity;
        """,
    )
    assert actual_rows == 263 * 8760


def test_full_year_taxi_trip_control_total(db):
    actual_trips = scalar(
        db,
        """
        SELECT SUM(CAST(taxi_trips AS BIGINT))
        FROM dw.FactZoneHourlyActivity;
        """,
    )
    assert actual_trips == 48_617_295


def test_full_year_complaint_control_total(db):
    actual_complaints = scalar(
        db,
        """
        SELECT SUM(CAST(complaints_311 AS BIGINT))
        FROM dw.FactZoneHourlyActivity;
        """,
    )
    assert actual_complaints == 3_603_396


def test_no_invalid_gold_measure_values(db):
    invalid_rows = scalar(
        db,
        """
        SELECT COUNT_BIG(*)
        FROM dw.FactZoneHourlyActivity
        WHERE taxi_trips < 0
           OR complaints_311 < 0
           OR rain_mm < 0
           OR snowfall_cm < 0
           OR (
                average_trip_distance IS NOT NULL
                AND average_trip_distance < 0
           );
        """,
    )

    assert invalid_rows == 0, (
        f"Found {invalid_rows} Gold rows containing "
        "structurally invalid measure values."
    )

def test_prediction_dimension_referential_integrity(db):
    orphan_rows = scalar(
        db,
        """
        SELECT COUNT_BIG(*)
        FROM dw.FactDemandPrediction AS p
        LEFT JOIN dw.DimDate AS d
            ON p.date_key = d.date_key
        LEFT JOIN dw.DimTime AS t
            ON p.time_key = t.time_key
        LEFT JOIN dw.DimZone AS z
            ON p.zone_key = z.zone_key
        WHERE d.date_key IS NULL
           OR t.time_key IS NULL
           OR z.zone_key IS NULL;
        """,
    )
    assert orphan_rows == 0


def test_prediction_row_count(db):
    actual_rows = scalar(
        db,
        """
        SELECT COUNT_BIG(*)
        FROM dw.FactDemandPrediction;
        """,
    )
    assert actual_rows == 385_032
