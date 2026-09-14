from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path

import pandas as pd
import pyarrow.dataset as ds
import pyodbc


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SOURCE_ROOT = (
    PROJECT_ROOT
    / "data"
    / "gold"
    / "dropoff_zone_daily"
)

EXPECTED_ROWS = 92_195
EXPECTED_TRIPS = 48_719_563
EXPECTED_DATES = 365
EXPECTED_ZONE_IDS = 263


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Load Taxi drop-off daily aggregate "
            "into Azure SQL."
        )
    )

    parser.add_argument(
        "--server",
        required=True,
    )

    parser.add_argument(
        "--database",
        required=True,
    )

    parser.add_argument(
        "--user",
        required=True,
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
    )

    parser.add_argument(
        "--check-connection",
        action="store_true",
    )

    return parser.parse_args()


def connect(
    server: str,
    database: str,
    user: str,
):
    password = os.getenv(
        "NYC_AZURE_SQL_PASSWORD"
    )

    if not password:
        password = getpass.getpass(
            f"Azure SQL password for {user}: "
        )

    connection_string = (
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
        connection_string,
        autocommit=False,
    )


def validate_objects(conn) -> None:
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            DB_NAME(),
            OBJECT_ID('dw.AggTaxiDropoffZoneDaily'),
            OBJECT_ID('stage.TaxiDropoffZoneDaily'),
            OBJECT_ID('etl.usp_LoadTaxiDropoffZoneDaily'),
            OBJECT_ID('dw.vw_TaxiDropoffZoneDaily');
        """
    )

    row = cursor.fetchone()

    print()
    print("===== AZURE SQL CONNECTION =====")
    print(f"Database: {row[0]}")

    if any(
        value is None
        for value in row[1:]
    ):
        raise ValueError(
            "One or more drop-off Power BI "
            "objects are missing."
        )

    print(
        "Drop-off warehouse objects: OK"
    )


def load_local_aggregate() -> pd.DataFrame:

    dataset = ds.dataset(
        SOURCE_ROOT,
        format="parquet",
        partitioning="hive",
    )

    table = dataset.to_table(
        columns=[
            "full_date",
            "dropoff_zone_id",
            "dropoff_trips",
        ]
    )

    df = table.to_pandas()

    df["full_date"] = pd.to_datetime(
        df["full_date"]
    ).dt.date

    if len(df) != EXPECTED_ROWS:
        raise ValueError(
            f"Unexpected local rows: "
            f"{len(df):,}"
        )

    trip_sum = int(
        df["dropoff_trips"].sum()
    )

    if trip_sum != EXPECTED_TRIPS:
        raise ValueError(
            f"Unexpected trip sum: "
            f"{trip_sum:,}"
        )

    if (
        df["full_date"].nunique()
        != EXPECTED_DATES
    ):
        raise ValueError(
            "Unexpected date count."
        )

    if (
        df["dropoff_zone_id"].nunique()
        != EXPECTED_ZONE_IDS
    ):
        raise ValueError(
            "Unexpected drop-off zone count."
        )

    if df.duplicated(
        subset=[
            "full_date",
            "dropoff_zone_id",
        ]
    ).any():
        raise ValueError(
            "Duplicate local drop-off grain."
        )

    return df


def get_dimension_maps(conn):

    date_map = pd.read_sql(
        """
        SELECT
            date_key,
            full_date
        FROM dw.DimDate
        WHERE year = 2025;
        """,
        conn,
    )

    zone_map = pd.read_sql(
        """
        SELECT
            zone_key,
            location_id
        FROM dw.DimZone
        WHERE location_id BETWEEN 0 AND 265;
        """,
        conn,
    )

    date_map["full_date"] = (
        pd.to_datetime(
            date_map["full_date"]
        )
        .dt.date
    )

    if len(date_map) != 365:
        raise ValueError(
            f"Expected 365 DimDate rows, "
            f"found {len(date_map)}."
        )

    return date_map, zone_map


def map_keys(
    df: pd.DataFrame,
    date_map: pd.DataFrame,
    zone_map: pd.DataFrame,
) -> pd.DataFrame:

    result = df.merge(
        date_map,
        on="full_date",
        how="left",
        validate="many_to_one",
    )

    result = result.merge(
        zone_map,
        left_on="dropoff_zone_id",
        right_on="location_id",
        how="left",
        validate="many_to_one",
    )

    if result[
        [
            "date_key",
            "zone_key",
        ]
    ].isna().any().any():
        missing = result.loc[
            result[
                [
                    "date_key",
                    "zone_key",
                ]
            ].isna().any(axis=1),
            [
                "full_date",
                "dropoff_zone_id",
            ],
        ]

        raise ValueError(
            "Warehouse key mapping failed. "
            f"Examples:\n{missing.head()}"
        )

    if result.duplicated(
        subset=[
            "date_key",
            "zone_key",
        ]
    ).any():
        raise ValueError(
            "Duplicate mapped aggregate grain."
        )

    return result


def clear_stage(conn):
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM stage.TaxiDropoffZoneDaily;"
    )

    conn.commit()


def stage_data(
    conn,
    df: pd.DataFrame,
    batch_size: int,
):
    cursor = conn.cursor()
    cursor.fast_executemany = True

    sql = """
    INSERT INTO stage.TaxiDropoffZoneDaily
    (
        date_key,
        zone_key,
        dropoff_trips
    )
    VALUES (?, ?, ?);
    """

    total = len(df)

    for start in range(
        0,
        total,
        batch_size,
    ):
        end = min(
            start + batch_size,
            total,
        )

        batch = df.iloc[
            start:end
        ]

        rows = [
            (
                int(row.date_key),
                int(row.zone_key),
                int(row.dropoff_trips),
            )
            for row in batch.itertuples(
                index=False
            )
        ]

        cursor.executemany(
            sql,
            rows,
        )

        conn.commit()

        print(
            f"Staged {end:,} / "
            f"{total:,}"
        )


def execute_load(conn):
    cursor = conn.cursor()

    cursor.execute(
        """
        EXEC etl.usp_LoadTaxiDropoffZoneDaily;
        """
    )

    row = cursor.fetchone()

    conn.commit()

    return row


def validate_final(conn):
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            COUNT_BIG(*) AS row_count,
            SUM(dropoff_trips) AS trip_sum,
            COUNT(DISTINCT full_date)
                AS date_count,
            COUNT(DISTINCT dropoff_zone_id)
                AS zone_count,
            SUM(
                CASE
                    WHEN dropoff_zone_id = 264
                    THEN dropoff_trips
                    ELSE 0
                END
            ) AS zone_264_trips,
            SUM(
                CASE
                    WHEN dropoff_zone_id = 265
                    THEN dropoff_trips
                    ELSE 0
                END
            ) AS zone_265_trips
        FROM dw.vw_TaxiDropoffZoneDaily
        WHERE year = 2025;
        """
    )

    row = cursor.fetchone()

    if row[0] != EXPECTED_ROWS:
        raise ValueError(
            f"Final row mismatch: "
            f"{row[0]:,}"
        )

    if row[1] != EXPECTED_TRIPS:
        raise ValueError(
            f"Final trip mismatch: "
            f"{row[1]:,}"
        )

    if row[2] != EXPECTED_DATES:
        raise ValueError(
            "Final date count mismatch."
        )

    if row[3] != EXPECTED_ZONE_IDS:
        raise ValueError(
            "Final zone count mismatch."
        )

    if row[4] != 105_182:
        raise ValueError(
            "Zone 264 trip reconciliation failed."
        )

    if row[5] != 219_048:
        raise ValueError(
            "Zone 265 trip reconciliation failed."
        )

    cursor.execute(
        """
        SELECT COUNT_BIG(*)
        FROM stage.TaxiDropoffZoneDaily;
        """
    )

    stage_rows = cursor.fetchone()[0]

    if stage_rows != 0:
        raise ValueError(
            f"Drop-off staging is not clean: "
            f"{stage_rows:,}"
        )

    print()
    print(
        "===== DROPOFF WAREHOUSE "
        "RECONCILIATION ====="
    )

    print(
        f"Aggregate rows: "
        f"{row[0]:,}"
    )

    print(
        f"Drop-off trips: "
        f"{row[1]:,}"
    )

    print(
        f"Dates: "
        f"{row[2]}"
    )

    print(
        f"Distinct zone IDs: "
        f"{row[3]}"
    )

    print(
        f"Zone 264 trips: "
        f"{row[4]:,}"
    )

    print(
        f"Zone 265 trips: "
        f"{row[5]:,}"
    )

    print(
        f"Remaining staging rows: "
        f"{stage_rows}"
    )


def main():
    args = parse_args()

    conn = connect(
        args.server,
        args.database,
        args.user,
    )

    try:
        validate_objects(conn)

        if args.check_connection:
            print()
            print(
                "Connection status: SUCCESS"
            )
            return

        print()
        print(
            "Loading local drop-off aggregate..."
        )

        df = load_local_aggregate()

        print(
            f"Local rows: "
            f"{len(df):,}"
        )

        print(
            f"Local trip sum: "
            f"{int(df['dropoff_trips'].sum()):,}"
        )

        print()
        print(
            "Loading dimension mappings..."
        )

        (
            date_map,
            zone_map,
        ) = get_dimension_maps(conn)

        mapped = map_keys(
            df,
            date_map,
            zone_map,
        )

        print(
            "Dimension mapping: SUCCESS"
        )

        print()
        print(
            "Clearing staging..."
        )

        clear_stage(conn)

        print(
            "Loading staging..."
        )

        stage_data(
            conn,
            mapped,
            args.batch_size,
        )

        print()
        print(
            "Executing warehouse load..."
        )

        result = execute_load(conn)

        print()
        print("===== LOAD RESULT =====")
        print(
            f"Staged rows: "
            f"{result[0]:,}"
        )
        print(
            f"Staged trips: "
            f"{result[1]:,}"
        )
        print(
            f"Final rows: "
            f"{result[2]:,}"
        )
        print(
            f"Final trips: "
            f"{result[3]:,}"
        )

        validate_final(conn)

        print()
        print(
            "POWERBI_DROPOFF_AZURE_LOAD_SUCCESS"
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()
