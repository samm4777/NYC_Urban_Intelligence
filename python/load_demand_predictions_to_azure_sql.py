from __future__ import annotations

import argparse
import getpass
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyodbc


PROJECT_ROOT = Path(__file__).resolve().parents[1]

PREDICTION_FILE = (
    PROJECT_ROOT
    / "data"
    / "gold"
    / "model_predictions"
    / "phase26_model_predictions.parquet"
)

EXPECTED_ROWS = 385_032
EXPECTED_ZONES = 263
EXPECTED_DATES = 61
EXPECTED_HOURS = 24

MODEL_NAME = "RandomForestRegressor"
MODEL_VERSION = "phase26_rf_v1"

TEST_START = pd.Timestamp(
    "2025-11-01 00:00:00"
)

TEST_END = pd.Timestamp(
    "2025-12-31 23:00:00"
)

RUN_ID_SEED = (
    "NYC_Urban_Intelligence|"
    "FactDemandPrediction|"
    f"{MODEL_NAME}|"
    f"{MODEL_VERSION}|"
    "2025-11-01T00:00:00|"
    "2025-12-31T23:00:00"
)

PREDICTION_RUN_ID = uuid.uuid5(
    uuid.NAMESPACE_URL,
    RUN_ID_SEED,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Load Phase 26 Random Forest predictions "
            "into Azure SQL FactDemandPrediction."
        )
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
        "--batch-size",
        type=int,
        default=5000,
        help="Rows per staging insert batch.",
    )

    parser.add_argument(
        "--check-connection",
        action="store_true",
        help=(
            "Check database connection and exit "
            "without loading predictions."
        ),
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


def validate_database_objects(conn) -> None:
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            DB_NAME(),
            OBJECT_ID(
                'dw.FactDemandPrediction'
            ),
            OBJECT_ID(
                'stage.DemandPrediction'
            ),
            OBJECT_ID(
                'etl.usp_UpsertDemandPrediction'
            ),
            OBJECT_ID(
                'dw.vw_DemandPredictionAnalysis'
            );
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
            "One or more Phase 30 SQL objects "
            "are missing."
        )

    print(
        "Phase 30 database objects: OK"
    )


def load_prediction_file() -> pd.DataFrame:
    if not PREDICTION_FILE.exists():
        raise FileNotFoundError(
            f"Prediction artifact missing: "
            f"{PREDICTION_FILE}"
        )

    df = pd.read_parquet(
        PREDICTION_FILE
    )

    required_columns = {
        "timestamp",
        "taxi_zone_id",
        "actual_demand",
        "random_forest_prediction",
    }

    missing = (
        required_columns
        - set(df.columns)
    )

    if missing:
        raise ValueError(
            f"Missing prediction columns: "
            f"{sorted(missing)}"
        )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"]
    )

    if len(df) != EXPECTED_ROWS:
        raise ValueError(
            f"Unexpected prediction rows: "
            f"{len(df):,}. "
            f"Expected {EXPECTED_ROWS:,}."
        )

    if (
        df["taxi_zone_id"].nunique()
        != EXPECTED_ZONES
    ):
        raise ValueError(
            "Unexpected taxi-zone count."
        )

    if (
        df["timestamp"].dt.date.nunique()
        != EXPECTED_DATES
    ):
        raise ValueError(
            "Unexpected prediction date count."
        )

    if (
        df["timestamp"].dt.hour.nunique()
        != EXPECTED_HOURS
    ):
        raise ValueError(
            "Unexpected prediction hour count."
        )

    if df["timestamp"].min() != TEST_START:
        raise ValueError(
            "Unexpected first prediction timestamp."
        )

    if df["timestamp"].max() != TEST_END:
        raise ValueError(
            "Unexpected last prediction timestamp."
        )

    duplicate_count = df.duplicated(
        subset=[
            "timestamp",
            "taxi_zone_id",
        ]
    ).sum()

    if duplicate_count:
        raise ValueError(
            f"Duplicate prediction grain: "
            f"{duplicate_count:,}"
        )

    if df[
        [
            "actual_demand",
            "random_forest_prediction",
        ]
    ].isna().any().any():
        raise ValueError(
            "Null actual/predicted demand found."
        )

    actual = df[
        "actual_demand"
    ].to_numpy(
        dtype=np.float64
    )

    if not np.allclose(
        actual,
        np.round(actual),
    ):
        raise ValueError(
            "actual_demand contains "
            "non-integer values."
        )

    df["actual_taxi_trips"] = (
        np.round(actual)
        .astype("int64")
    )

    df["predicted_taxi_demand"] = (
        df[
            "random_forest_prediction"
        ]
        .astype("float64")
        .round(4)
    )

    # Signed error:
    # positive = overprediction
    # negative = underprediction
    df["prediction_error"] = (
        df["predicted_taxi_demand"]
        - df["actual_taxi_trips"]
    ).round(4)

    return df


def get_dimension_maps(conn):
    date_map = pd.read_sql(
        """
        SELECT
            date_key,
            full_date
        FROM dw.DimDate
        WHERE full_date
            BETWEEN '2025-11-01'
            AND '2025-12-31';
        """,
        conn,
    )

    time_map = pd.read_sql(
        """
        SELECT
            time_key,
            hour_of_day
        FROM dw.DimTime
        WHERE hour_of_day
            BETWEEN 0 AND 23;
        """,
        conn,
    )

    zone_map = pd.read_sql(
        """
        SELECT
            zone_key,
            location_id
        FROM dw.DimZone
        WHERE
            location_id BETWEEN 1 AND 263
            AND is_authoritative_polygon = 1;
        """,
        conn,
    )

    if len(date_map) != EXPECTED_DATES:
        raise ValueError(
            f"Expected 61 DimDate rows, "
            f"found {len(date_map)}."
        )

    if (
        len(time_map) != EXPECTED_HOURS
        or time_map["hour_of_day"].nunique()
            != EXPECTED_HOURS
    ):
        raise ValueError(
            "DimTime does not contain exactly "
            "one member for each hour 0-23."
        )

    if (
        len(zone_map) != EXPECTED_ZONES
        or zone_map["location_id"].nunique()
            != EXPECTED_ZONES
    ):
        raise ValueError(
            "DimZone authoritative mapping "
            "is incomplete."
        )

    date_map["full_date"] = pd.to_datetime(
        date_map["full_date"]
    ).dt.date

    return date_map, time_map, zone_map


def map_surrogate_keys(
    df: pd.DataFrame,
    date_map: pd.DataFrame,
    time_map: pd.DataFrame,
    zone_map: pd.DataFrame,
) -> pd.DataFrame:

    result = df.copy()

    result["full_date"] = (
        result["timestamp"]
        .dt.date
    )

    result["hour_of_day"] = (
        result["timestamp"]
        .dt.hour
    )

    result = result.merge(
        date_map,
        on="full_date",
        how="left",
        validate="many_to_one",
    )

    result = result.merge(
        time_map,
        on="hour_of_day",
        how="left",
        validate="many_to_one",
    )

    result = result.merge(
        zone_map,
        left_on="taxi_zone_id",
        right_on="location_id",
        how="left",
        validate="many_to_one",
    )

    key_columns = [
        "date_key",
        "time_key",
        "zone_key",
    ]

    if result[
        key_columns
    ].isna().any().any():
        raise ValueError(
            "One or more warehouse "
            "surrogate keys could not be mapped."
        )

    if result.duplicated(
        subset=[
            "date_key",
            "time_key",
            "zone_key",
        ]
    ).any():
        raise ValueError(
            "Duplicate mapped warehouse grain."
        )

    return result


def clear_run_from_stage(
    conn,
    run_id: str,
) -> None:
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM stage.DemandPrediction
        WHERE prediction_run_id = ?;
        """,
        run_id,
    )

    conn.commit()


def stage_predictions(
    conn,
    df: pd.DataFrame,
    run_id: str,
    batch_size: int,
) -> None:

    generated_at = datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )

    sql = """
    INSERT INTO stage.DemandPrediction
    (
        prediction_run_id,
        date_key,
        time_key,
        zone_key,
        model_name,
        model_version,
        predicted_taxi_demand,
        actual_taxi_trips,
        prediction_error,
        generated_at
    )
    VALUES
    (
        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
    );
    """

    cursor = conn.cursor()
    cursor.fast_executemany = True

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
                run_id,
                int(row.date_key),
                int(row.time_key),
                int(row.zone_key),
                MODEL_NAME,
                MODEL_VERSION,
                float(
                    row.predicted_taxi_demand
                ),
                int(
                    row.actual_taxi_trips
                ),
                float(
                    row.prediction_error
                ),
                generated_at,
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


def execute_upsert(
    conn,
    run_id: str,
):
    cursor = conn.cursor()

    cursor.execute(
        """
        EXEC etl.usp_UpsertDemandPrediction
            @prediction_run_id = ?;
        """,
        run_id,
    )

    row = cursor.fetchone()

    conn.commit()

    return row


def validate_fact(
    conn,
    run_id: str,
) -> None:

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            COUNT_BIG(*) AS row_count,
            COUNT(DISTINCT date_key)
                AS date_count,
            COUNT(DISTINCT time_key)
                AS time_count,
            COUNT(DISTINCT zone_key)
                AS zone_count,
            SUM(
                CASE
                    WHEN actual_taxi_trips
                        IS NULL
                    THEN 1
                    ELSE 0
                END
            ) AS null_actual,
            SUM(
                CASE
                    WHEN predicted_taxi_demand
                        IS NULL
                    THEN 1
                    ELSE 0
                END
            ) AS null_prediction
        FROM dw.FactDemandPrediction
        WHERE prediction_run_id = ?;
        """,
        run_id,
    )

    row = cursor.fetchone()

    if row[0] != EXPECTED_ROWS:
        raise ValueError(
            f"Fact row count mismatch: "
            f"{row[0]:,}"
        )

    if row[1] != EXPECTED_DATES:
        raise ValueError(
            "Fact date reconciliation failed."
        )

    if row[2] != EXPECTED_HOURS:
        raise ValueError(
            "Fact time reconciliation failed."
        )

    if row[3] != EXPECTED_ZONES:
        raise ValueError(
            "Fact zone reconciliation failed."
        )

    if row[4] != 0 or row[5] != 0:
        raise ValueError(
            "Unexpected null actual or "
            "prediction values in fact."
        )

    print()
    print("===== FACT RECONCILIATION =====")
    print(
        f"Rows:  {row[0]:,}"
    )
    print(
        f"Dates: {row[1]}"
    )
    print(
        f"Hours: {row[2]}"
    )
    print(
        f"Zones: {row[3]}"
    )
    print(
        "Null actual demand: 0"
    )
    print(
        "Null predictions:   0"
    )


def main() -> None:
    args = parse_args()

    run_id = str(
        PREDICTION_RUN_ID
    )

    print(
        "Phase 30 prediction run ID:"
    )
    print(run_id)

    conn = connect(
        args.server,
        args.database,
        args.user,
    )

    try:
        validate_database_objects(
            conn
        )

        if args.check_connection:
            print()
            print(
                "Connection status: SUCCESS"
            )
            return

        print()
        print(
            "Loading local prediction artifact..."
        )

        df = load_prediction_file()

        print(
            f"Prediction rows: "
            f"{len(df):,}"
        )

        print()
        print(
            "Loading warehouse dimensions..."
        )

        (
            date_map,
            time_map,
            zone_map,
        ) = get_dimension_maps(conn)

        mapped = map_surrogate_keys(
            df,
            date_map,
            time_map,
            zone_map,
        )

        print(
            "Dimension mapping: SUCCESS"
        )

        print()
        print(
            "Clearing previous staging rows "
            "for this prediction run..."
        )

        clear_run_from_stage(
            conn,
            run_id,
        )

        print(
            "Loading prediction staging..."
        )

        stage_predictions(
            conn,
            mapped,
            run_id,
            args.batch_size,
        )

        print()
        print(
            "Executing idempotent warehouse upsert..."
        )

        result = execute_upsert(
            conn,
            run_id,
        )

        print()
        print("===== UPSERT RESULT =====")
        print(
            f"Prediction run ID: "
            f"{result[0]}"
        )
        print(
            f"Staged rows:  "
            f"{result[1]:,}"
        )
        print(
            f"Inserted rows: "
            f"{result[2]:,}"
        )
        print(
            f"Final fact rows: "
            f"{result[3]:,}"
        )

        validate_fact(
            conn,
            run_id,
        )

        print()
        print(
            "PHASE30_PREDICTION_LOAD_SUCCESS"
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()
