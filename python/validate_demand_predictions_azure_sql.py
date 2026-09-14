from __future__ import annotations

import argparse
import getpass
import os

import pyodbc


RUN_ID = "25571B64-B788-530A-93F1-4B8B9473F8D0"

EXPECTED_ROWS = 385_032
EXPECTED_DATES = 61
EXPECTED_HOURS = 24
EXPECTED_ZONES = 263
EXPECTED_ZERO_ROWS = 141_563

EXPECTED_MAE = 4.1399
EXPECTED_RMSE = 12.0792

METRIC_TOLERANCE = 0.001


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Validate Phase 30 demand predictions "
            "stored in Azure SQL."
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
        connection_string
    )


def main() -> None:
    args = parse_args()

    conn = connect(
        args.server,
        args.database,
        args.user,
    )

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                COUNT_BIG(*),
                COUNT(DISTINCT full_date),
                COUNT(DISTINCT hour_of_day),
                COUNT(DISTINCT taxi_zone_id),
                MIN(full_date),
                MAX(full_date),
                MIN(model_name),
                MIN(model_version)
            FROM dw.vw_DemandPredictionAnalysis
            WHERE prediction_run_id = ?;
            """,
            RUN_ID,
        )

        row = cursor.fetchone()

        (
            fact_rows,
            dates,
            hours,
            zones,
            first_date,
            last_date,
            model_name,
            model_version,
        ) = row

        if fact_rows != EXPECTED_ROWS:
            raise ValueError(
                f"Fact row mismatch: {fact_rows:,}"
            )

        if dates != EXPECTED_DATES:
            raise ValueError(
                f"Date mismatch: {dates}"
            )

        if hours != EXPECTED_HOURS:
            raise ValueError(
                f"Hour mismatch: {hours}"
            )

        if zones != EXPECTED_ZONES:
            raise ValueError(
                f"Zone mismatch: {zones}"
            )

        if model_name != "RandomForestRegressor":
            raise ValueError(
                f"Unexpected model: {model_name}"
            )

        if model_version != "phase26_rf_v1":
            raise ValueError(
                f"Unexpected model version: "
                f"{model_version}"
            )

        cursor.execute(
            """
            SELECT COUNT_BIG(*)
            FROM
            (
                SELECT
                    full_date,
                    hour_of_day,
                    taxi_zone_id
                FROM dw.vw_DemandPredictionAnalysis
                WHERE prediction_run_id = ?
                GROUP BY
                    full_date,
                    hour_of_day,
                    taxi_zone_id
                HAVING COUNT_BIG(*) > 1
            ) AS d;
            """,
            RUN_ID,
        )

        duplicate_groups = (
            cursor.fetchone()[0]
        )

        if duplicate_groups != 0:
            raise ValueError(
                f"Duplicate groups: "
                f"{duplicate_groups}"
            )

        cursor.execute(
            """
            SELECT COUNT_BIG(*)
            FROM stage.DemandPrediction
            WHERE prediction_run_id = ?;
            """,
            RUN_ID,
        )

        stage_rows = cursor.fetchone()[0]

        if stage_rows != 0:
            raise ValueError(
                f"Staging is not clean: "
                f"{stage_rows:,} rows"
            )

        cursor.execute(
            """
            SELECT
                AVG(
                    ABS(
                        CAST(
                            predicted_taxi_demand
                            AS FLOAT
                        )
                        -
                        CAST(
                            actual_taxi_trips
                            AS FLOAT
                        )
                    )
                ),
                SQRT(
                    AVG(
                        POWER(
                            CAST(
                                predicted_taxi_demand
                                AS FLOAT
                            )
                            -
                            CAST(
                                actual_taxi_trips
                                AS FLOAT
                            ),
                            2
                        )
                    )
                ),
                AVG(
                    CAST(
                        signed_error
                        AS FLOAT
                    )
                ),
                SUM(
                    CASE
                        WHEN actual_taxi_trips = 0
                        THEN 1
                        ELSE 0
                    END
                ),
                SUM(
                    CASE
                        WHEN actual_taxi_trips = 0
                             AND percentage_error
                                 IS NULL
                        THEN 1
                        ELSE 0
                    END
                )
            FROM dw.vw_DemandPredictionAnalysis
            WHERE prediction_run_id = ?;
            """,
            RUN_ID,
        )

        metric_row = cursor.fetchone()

        mae = float(metric_row[0])
        rmse = float(metric_row[1])
        bias = float(metric_row[2])
        zero_rows = int(metric_row[3])
        zero_pct_null = int(metric_row[4])

        if abs(
            mae - EXPECTED_MAE
        ) > METRIC_TOLERANCE:
            raise ValueError(
                f"MAE mismatch: {mae:.4f}"
            )

        if abs(
            rmse - EXPECTED_RMSE
        ) > METRIC_TOLERANCE:
            raise ValueError(
                f"RMSE mismatch: {rmse:.4f}"
            )

        if zero_rows != EXPECTED_ZERO_ROWS:
            raise ValueError(
                f"Zero-demand row mismatch: "
                f"{zero_rows:,}"
            )

        if zero_pct_null != EXPECTED_ZERO_ROWS:
            raise ValueError(
                "Zero-demand percentage-error "
                "handling failed."
            )

        print(
            f"Prediction rows: "
            f"{fact_rows:,}"
        )
        print(
            f"Dates: {dates}"
        )
        print(
            f"Hours: {hours}"
        )
        print(
            f"Zones: {zones}"
        )
        print(
            f"First date: {first_date}"
        )
        print(
            f"Last date: {last_date}"
        )

        print()
        print(
            f"Model: {model_name}"
        )
        print(
            f"Version: {model_version}"
        )

        print()
        print(
            f"MAE:       {mae:.4f}"
        )
        print(
            f"RMSE:      {rmse:.4f}"
        )
        print(
            f"Mean bias: {bias:.4f}"
        )

        print()
        print(
            f"Zero-demand rows: "
            f"{zero_rows:,}"
        )
        print(
            "Zero-demand percentage NULL: "
            f"{zero_pct_null:,}"
        )

        print()
        print(
            f"Duplicate groups: "
            f"{duplicate_groups}"
        )
        print(
            f"Remaining stage rows: "
            f"{stage_rows}"
        )

        print()
        print(
            "PHASE30_STORE_PREDICTIONS_"
            "VALIDATION_SUCCESS"
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()
