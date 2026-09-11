from __future__ import annotations

import argparse
import calendar
import getpass
import hashlib
import math
import sys
import uuid
from pathlib import Path

import pandas as pd
import pyodbc
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLD_ROOT = PROJECT_ROOT / "data" / "gold" / "zone_hourly"

PIPELINE_NAME = "gold_zone_hourly_to_azure_sql"
TARGET_SCHEMA = "dw"
TARGET_TABLE = "FactZoneHourlyActivity"

STAGE_INSERT_SQL = """
INSERT INTO etl.StageZoneHourlyActivity
(
    load_batch_id,
    activity_date,
    hour_of_day,
    taxi_zone_id,
    taxi_trips,
    taxi_revenue,
    average_fare,
    average_trip_distance,
    complaints_311,
    temperature_c,
    rain_mm,
    snowfall_cm,
    weather_condition,
    source_run_id,
    source_processed_at,
    processing_year,
    processing_month,
    source_file
)
VALUES
(
    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
);
"""


def parse_args():
    parser = argparse.ArgumentParser(
        description="Load Gold zone-hourly Parquet data into Azure SQL."
    )

    parser.add_argument(
        "--server",
        required=True,
        help="Azure SQL logical server hostname.",
    )

    parser.add_argument(
        "--database",
        required=True,
        help="Azure SQL database name.",
    )

    parser.add_argument(
        "--user",
        required=True,
        help="Azure SQL login username.",
    )

    parser.add_argument(
        "--year",
        type=int,
        default=2025,
    )

    parser.add_argument(
        "--month",
        type=int,
        choices=range(1, 13),
        default=None,
        help="Load one month only. Omit later to load all 12 months.",
    )

    parser.add_argument(
        "--check-connection",
        action="store_true",
        help="Test Azure SQL connectivity only. No data is loaded.",
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=5000,
        help="Rows per pyodbc staging batch.",
    )

    parser.add_argument(
        "--load-type",
        choices=["FULL", "INCREMENTAL", "BACKFILL"],
        default="BACKFILL",
    )

    return parser.parse_args()


def connect(server: str, database: str, user: str):
    password = getpass.getpass(
        f"Azure SQL password for {user}: "
    )

    conn_string = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER=tcp:{server},1433;"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )

    return pyodbc.connect(
        conn_string,
        autocommit=False,
    )


def test_connection(conn):
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            DB_NAME() AS database_name,
            CAST(SERVERPROPERTY('Edition') AS NVARCHAR(100))
                AS edition;
        """
    )

    row = cursor.fetchone()

    print("\n===== AZURE SQL CONNECTION =====")
    print("Database :", row.database_name)
    print("Edition  :", row.edition)

    cursor.execute(
        """
        SELECT
            COUNT(*)
        FROM sys.tables t
        JOIN sys.schemas s
            ON t.schema_id = s.schema_id
        WHERE
            s.name = 'dw';
        """
    )

    print("DW tables:", cursor.fetchone()[0])

    cursor.execute(
        """
        SELECT
            CASE
                WHEN OBJECT_ID(
                    N'etl.StageZoneHourlyActivity',
                    N'U'
                ) IS NOT NULL
                THEN 1 ELSE 0
            END,
            CASE
                WHEN OBJECT_ID(
                    N'etl.usp_UpsertZoneHourlyActivity',
                    N'P'
                ) IS NOT NULL
                THEN 1 ELSE 0
            END;
        """
    )

    stage_exists, proc_exists = cursor.fetchone()

    print(
        "Stage table:",
        "OK" if stage_exists else "MISSING",
    )

    print(
        "Upsert proc:",
        "OK" if proc_exists else "MISSING",
    )

    if not stage_exists or not proc_exists:
        raise RuntimeError(
            "Required Phase 15 Gold load objects are missing."
        )

    print("Connection status: SUCCESS")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as fh:
        while True:
            block = fh.read(1024 * 1024)

            if not block:
                break

            digest.update(block)

    return digest.hexdigest()


def find_month_file(year: int, month: int) -> Path:
    month_dir = (
        GOLD_ROOT
        / f"year={year}"
        / f"month={month:02d}"
    )

    files = sorted(month_dir.glob("*.parquet"))

    if len(files) != 1:
        raise RuntimeError(
            f"Expected exactly one Parquet file in "
            f"{month_dir}, found {len(files)}."
        )

    return files[0]


def expected_month_rows(year: int, month: int) -> int:
    days = calendar.monthrange(year, month)[1]

    return days * 24 * 263


def validate_dataframe(
    df: pd.DataFrame,
    year: int,
    month: int,
):
    required_columns = {
        "date",
        "hour",
        "taxi_zone_id",
        "taxi_trips",
        "taxi_revenue",
        "average_fare",
        "average_trip_distance",
        "complaints_311",
        "temperature_c",
        "rain_mm",
        "snowfall_cm",
        "weather_condition",
        "_run_id",
        "_processed_at",
        "_processing_year",
        "_processing_month",
    }

    missing = sorted(
        required_columns.difference(df.columns)
    )

    if missing:
        raise RuntimeError(
            f"Missing required Gold columns: {missing}"
        )

    expected = expected_month_rows(year, month)

    if len(df) != expected:
        raise RuntimeError(
            f"Row-count validation failed for "
            f"{year}-{month:02d}. "
            f"Expected {expected:,}; found {len(df):,}."
        )

    grain_duplicates = df.duplicated(
        subset=[
            "date",
            "hour",
            "taxi_zone_id",
        ]
    ).sum()

    if grain_duplicates:
        raise RuntimeError(
            f"Duplicate Gold grain rows found: "
            f"{grain_duplicates:,}"
        )

    if not df["hour"].between(0, 23).all():
        raise RuntimeError(
            "Invalid hour outside 0-23."
        )

    if not df["taxi_zone_id"].between(1, 263).all():
        raise RuntimeError(
            "Gold contains Taxi Zone outside 1-263."
        )

    dates = pd.to_datetime(df["date"])

    if not (
        (dates.dt.year == year)
        & (dates.dt.month == month)
    ).all():
        raise RuntimeError(
            "Gold contains rows outside expected year/month."
        )

    required_non_null = [
        "date",
        "hour",
        "taxi_zone_id",
        "taxi_trips",
        "taxi_revenue",
        "complaints_311",
        "temperature_c",
        "rain_mm",
        "snowfall_cm",
        "weather_condition",
    ]

    null_counts = (
        df[required_non_null]
        .isna()
        .sum()
    )

    bad_nulls = null_counts[
        null_counts > 0
    ]

    if not bad_nulls.empty:
        raise RuntimeError(
            "Unexpected NULLs in required Gold fields:\n"
            + bad_nulls.to_string()
        )

    if (df["taxi_trips"] < 0).any():
        raise RuntimeError(
            "Negative taxi_trips found."
        )

    if (df["complaints_311"] < 0).any():
        raise RuntimeError(
            "Negative complaints_311 found."
        )

    print(
        f"Pre-load validation: PASS "
        f"({len(df):,} rows)"
    )


def prepare_dataframe(
    path: Path,
    year: int,
    month: int,
):
    print("\nReading:", path)

    table = pq.read_table(path)

    df = table.to_pandas()

    validate_dataframe(
        df,
        year,
        month,
    )

    return df


def get_or_prepare_batch(
    conn,
    *,
    year: int,
    month: int,
    source_file: Path,
    source_hash: str,
    load_type: str,
):
    relative_source = str(
        source_file.relative_to(PROJECT_ROOT)
    ).replace("\\", "/")

    source_partition = (
        f"year={year}/month={month:02d}"
    )

    idempotency_key = (
        f"gold_zone_hourly|"
        f"{source_partition}|"
        f"sha256={source_hash}"
    )

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            load_batch_id,
            status
        FROM audit.LoadBatch
        WHERE idempotency_key = ?;
        """,
        idempotency_key,
    )

    existing = cursor.fetchone()

    if existing:
        batch_id = str(existing.load_batch_id)
        status = existing.status

        if status == "SUCCESS":
            print(
                f"Batch already SUCCESS for "
                f"{year}-{month:02d}; skipping."
            )

            return batch_id, True

        print(
            f"Recovering existing {status} batch: "
            f"{batch_id}"
        )

        cursor.execute(
            """
            DELETE FROM etl.StageZoneHourlyActivity
            WHERE load_batch_id = ?;
            """,
            batch_id,
        )

        cursor.execute(
            """
            UPDATE audit.LoadBatch
            SET
                status = 'STARTED',
                started_at = SYSUTCDATETIME(),
                completed_at = NULL,
                rows_read = NULL,
                rows_inserted = NULL,
                rows_updated = NULL,
                rows_rejected = NULL,
                error_message = NULL
            WHERE load_batch_id = ?;
            """,
            batch_id,
        )

        conn.commit()

        return batch_id, False

    batch_id = str(uuid.uuid4())

    cursor.execute(
        """
        INSERT INTO audit.LoadBatch
        (
            load_batch_id,
            pipeline_name,
            source_system,
            source_object,
            source_partition,
            target_schema,
            target_table,
            idempotency_key,
            load_type,
            status
        )
        VALUES
        (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, 'STARTED'
        );
        """,
        batch_id,
        PIPELINE_NAME,
        "local_gold_parquet",
        relative_source,
        source_partition,
        TARGET_SCHEMA,
        TARGET_TABLE,
        idempotency_key,
        load_type,
    )

    conn.commit()

    return batch_id, False


def native_value(value):
    if value is None:
        return None

    if isinstance(value, float) and math.isnan(value):
        return None

    if pd.isna(value):
        return None

    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    return value


def stage_dataframe(
    conn,
    df: pd.DataFrame,
    batch_id: str,
    source_file: Path,
    chunk_size: int,
):
    relative_source = str(
        source_file.relative_to(PROJECT_ROOT)
    ).replace("\\", "/")

    stage_columns = [
        "date",
        "hour",
        "taxi_zone_id",
        "taxi_trips",
        "taxi_revenue",
        "average_fare",
        "average_trip_distance",
        "complaints_311",
        "temperature_c",
        "rain_mm",
        "snowfall_cm",
        "weather_condition",
        "_run_id",
        "_processed_at",
        "_processing_year",
        "_processing_month",
    ]

    work = df[stage_columns].copy()

    work["date"] = pd.to_datetime(
        work["date"]
    ).dt.date

    work["_processed_at"] = pd.to_datetime(
        work["_processed_at"],
        errors="coerce",
    )

    cursor = conn.cursor()
    cursor.fast_executemany = True

    total = len(work)
    staged = 0

    print(
        f"Staging {total:,} rows "
        f"in chunks of {chunk_size:,}..."
    )

    for start in range(
        0,
        total,
        chunk_size,
    ):
        end = min(
            start + chunk_size,
            total,
        )

        chunk = work.iloc[start:end]

        rows = []

        for row in chunk.itertuples(
            index=False,
            name=None,
        ):
            values = [
                native_value(v)
                for v in row
            ]

            rows.append(
                (
                    batch_id,
                    values[0],
                    int(values[1]),
                    int(values[2]),
                    int(values[3]),
                    float(values[4]),
                    (
                        None
                        if values[5] is None
                        else float(values[5])
                    ),
                    (
                        None
                        if values[6] is None
                        else float(values[6])
                    ),
                    int(values[7]),
                    float(values[8]),
                    float(values[9]),
                    float(values[10]),
                    str(values[11]),
                    (
                        None
                        if values[12] is None
                        else str(values[12])
                    ),
                    values[13],
                    int(values[14]),
                    int(values[15]),
                    relative_source,
                )
            )

        cursor.executemany(
            STAGE_INSERT_SQL,
            rows,
        )

        conn.commit()

        staged += len(rows)

        print(
            f"  staged "
            f"{staged:,}/{total:,}"
        )

    cursor.execute(
        """
        SELECT COUNT_BIG(*)
        FROM etl.StageZoneHourlyActivity
        WHERE load_batch_id = ?;
        """,
        batch_id,
    )

    sql_count = cursor.fetchone()[0]

    if sql_count != total:
        raise RuntimeError(
            f"Staging reconciliation failed. "
            f"Expected {total:,}; "
            f"SQL contains {sql_count:,}."
        )

    print(
        f"Staging reconciliation: PASS "
        f"({sql_count:,})"
    )


def execute_upsert(
    conn,
    batch_id: str,
):
    cursor = conn.cursor()

    print(
        "Executing "
        "etl.usp_UpsertZoneHourlyActivity..."
    )

    cursor.execute(
        """
        EXEC etl.usp_UpsertZoneHourlyActivity
            @load_batch_id = ?;
        """,
        batch_id,
    )

    result = cursor.fetchone()

    while cursor.nextset():
        if cursor.description:
            result = cursor.fetchone()
            if result:
                break

    conn.commit()

    if result:
        print("\n===== UPSERT RESULT =====")
        print("Batch ID     :", result[0])
        print("Rows staged  :", f"{result[1]:,}")
        print("Rows inserted:", f"{result[2]:,}")
        print("Rows updated :", f"{result[3]:,}")
        print("Rows affected:", f"{result[4]:,}")
        print("Status       :", result[5])


def verify_month(
    conn,
    year: int,
    month: int,
):
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            COUNT_BIG(*) AS row_count,
            SUM(f.taxi_trips) AS taxi_trips,
            CAST(
                SUM(f.taxi_revenue)
                AS DECIMAL(28,2)
            ) AS taxi_revenue,
            SUM(
                CONVERT(BIGINT, f.complaints_311)
            ) AS complaints_311
        FROM dw.FactZoneHourlyActivity f
        JOIN dw.DimDate d
            ON f.date_key = d.date_key
        WHERE
            YEAR(d.full_date) = ?
            AND MONTH(d.full_date) = ?;
        """,
        year,
        month,
    )

    row = cursor.fetchone()

    expected = expected_month_rows(
        year,
        month,
    )

    print("\n===== MONTH TARGET CHECK =====")
    print(
        "Month        :",
        f"{year}-{month:02d}",
    )
    print(
        "Target rows  :",
        f"{row.row_count:,}",
    )
    print(
        "Expected rows:",
        f"{expected:,}",
    )
    print(
        "Taxi trips   :",
        f"{row.taxi_trips:,}",
    )
    print(
        "Taxi revenue :",
        row.taxi_revenue,
    )
    print(
        "311 complaints:",
        f"{row.complaints_311:,}",
    )

    if row.row_count != expected:
        raise RuntimeError(
            "Final month row-count "
            "reconciliation failed."
        )

    print("Month reconciliation: PASS")


def load_month(
    conn,
    *,
    year: int,
    month: int,
    chunk_size: int,
    load_type: str,
):
    print(
        "\n"
        + "=" * 64
    )

    print(
        f"LOADING GOLD MONTH "
        f"{year}-{month:02d}"
    )

    print(
        "=" * 64
    )

    source_file = find_month_file(
        year,
        month,
    )

    print(
        "Computing source SHA-256..."
    )

    source_hash = sha256_file(
        source_file
    )

    print(
        "SHA-256:",
        source_hash,
    )

    batch_id, skip = get_or_prepare_batch(
        conn,
        year=year,
        month=month,
        source_file=source_file,
        source_hash=source_hash,
        load_type=load_type,
    )

    if skip:
        verify_month(
            conn,
            year,
            month,
        )
        return

    try:
        df = prepare_dataframe(
            source_file,
            year,
            month,
        )

        stage_dataframe(
            conn,
            df,
            batch_id,
            source_file,
            chunk_size,
        )

        execute_upsert(
            conn,
            batch_id,
        )

        verify_month(
            conn,
            year,
            month,
        )

    except Exception as exc:
        conn.rollback()

        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE audit.LoadBatch
            SET
                status = 'FAILED',
                completed_at = SYSUTCDATETIME(),
                error_message = ?
            WHERE
                load_batch_id = ?
                AND status <> 'SUCCESS';
            """,
            str(exc)[:4000],
            batch_id,
        )

        conn.commit()

        raise


def main():
    args = parse_args()

    print(
        "Project root:",
        PROJECT_ROOT,
    )

    conn = None

    try:
        conn = connect(
            args.server,
            args.database,
            args.user,
        )

        test_connection(conn)

        if args.check_connection:
            return 0

        if args.month is not None:
            months = [args.month]
        else:
            months = list(range(1, 13))

        for month in months:
            load_month(
                conn,
                year=args.year,
                month=month,
                chunk_size=args.chunk_size,
                load_type=args.load_type,
            )

        print(
            "\n"
            + "=" * 64
        )
        print("GOLD AZURE SQL LOAD: SUCCESS")
        print("=" * 64)

        return 0

    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    try:
        sys.exit(main())

    except KeyboardInterrupt:
        print(
            "\nLoad cancelled by user.",
            file=sys.stderr,
        )
        sys.exit(130)

    except Exception as exc:
        print(
            f"\nERROR: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
