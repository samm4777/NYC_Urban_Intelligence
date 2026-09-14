from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

REPORT_ROOT = (
    PROJECT_ROOT
    / "reports"
    / "model_evaluation"
)

OVERALL_FILE = REPORT_ROOT / "overall_metrics.csv"
ZONE_FILE = REPORT_ROOT / "by_zone.csv"
HOUR_FILE = REPORT_ROOT / "by_hour.csv"
DAY_FILE = REPORT_ROOT / "by_day_of_week.csv"
DEMAND_FILE = REPORT_ROOT / "by_demand_level.csv"

EXPECTED_ROWS = 385_032
EXPECTED_ZONES = 263
EXPECTED_HOURS = 24
EXPECTED_DAYS = 7
EXPECTED_DEMAND_LEVELS = 6

EXPECTED_MAE = 4.1399042740009175
EXPECTED_RMSE = 12.079198949644113
EXPECTED_R2 = 0.9618364077221317

TOLERANCE = 1e-6


def check_close(
    name: str,
    actual: float,
    expected: float,
) -> None:

    if abs(actual - expected) > TOLERANCE:
        raise ValueError(
            f"{name} mismatch: "
            f"{actual} vs {expected}"
        )


def main() -> None:

    files = [
        OVERALL_FILE,
        ZONE_FILE,
        HOUR_FILE,
        DAY_FILE,
        DEMAND_FILE,
    ]

    for file in files:
        if not file.exists():
            raise FileNotFoundError(
                f"Missing evaluation artifact: {file}"
            )

    overall = pd.read_csv(
        OVERALL_FILE
    )

    by_zone = pd.read_csv(
        ZONE_FILE
    )

    by_hour = pd.read_csv(
        HOUR_FILE
    )

    by_day = pd.read_csv(
        DAY_FILE
    )

    by_demand = pd.read_csv(
        DEMAND_FILE
    )

    if len(overall) != 1:
        raise ValueError(
            "Expected one overall metrics row."
        )

    row = overall.iloc[0]

    if int(row["observations"]) != EXPECTED_ROWS:
        raise ValueError(
            "Overall observation count mismatch."
        )

    check_close(
        "MAE",
        float(row["mae"]),
        EXPECTED_MAE,
    )

    check_close(
        "RMSE",
        float(row["rmse"]),
        EXPECTED_RMSE,
    )

    check_close(
        "R2",
        float(row["r2"]),
        EXPECTED_R2,
    )

    if len(by_zone) != EXPECTED_ZONES:
        raise ValueError(
            f"Expected {EXPECTED_ZONES} zone rows, "
            f"found {len(by_zone)}."
        )

    if len(by_hour) != EXPECTED_HOURS:
        raise ValueError(
            f"Expected {EXPECTED_HOURS} hourly rows, "
            f"found {len(by_hour)}."
        )

    if len(by_day) != EXPECTED_DAYS:
        raise ValueError(
            f"Expected {EXPECTED_DAYS} day rows, "
            f"found {len(by_day)}."
        )

    if len(by_demand) != EXPECTED_DEMAND_LEVELS:
        raise ValueError(
            f"Expected {EXPECTED_DEMAND_LEVELS} "
            f"demand-level rows, "
            f"found {len(by_demand)}."
        )

    if int(by_hour["observations"].sum()) != EXPECTED_ROWS:
        raise ValueError(
            "Hourly observation reconciliation failed."
        )

    if int(by_day["observations"].sum()) != EXPECTED_ROWS:
        raise ValueError(
            "Day observation reconciliation failed."
        )

    if int(by_demand["observations"].sum()) != EXPECTED_ROWS:
        raise ValueError(
            "Demand-level observation reconciliation failed."
        )

    expected_zone_rows = 61 * 24

    if not (
        by_zone["observations"]
        == expected_zone_rows
    ).all():
        raise ValueError(
            "Unexpected per-zone observation count."
        )

    expected_hour_rows = 61 * EXPECTED_ZONES

    if not (
        by_hour["observations"]
        == expected_hour_rows
    ).all():
        raise ValueError(
            "Unexpected per-hour observation count."
        )

    if by_zone["taxi_zone_id"].nunique() != EXPECTED_ZONES:
        raise ValueError(
            "Duplicate or missing taxi zones."
        )

    if set(by_hour["hour"]) != set(range(24)):
        raise ValueError(
            "Hourly evaluation does not cover 0-23."
        )

    if set(by_day["day_of_week_number"]) != set(range(7)):
        raise ValueError(
            "Day-of-week evaluation does not cover 0-6."
        )

    best_day = (
        by_day.sort_values(
            ["mae", "rmse"]
        )
        .iloc[0]
    )

    worst_day = (
        by_day.sort_values(
            ["mae", "rmse"],
            ascending=False,
        )
        .iloc[0]
    )

    best_hour = (
        by_hour.sort_values(
            ["mae", "rmse"]
        )
        .iloc[0]
    )

    worst_hour = (
        by_hour.sort_values(
            ["mae", "rmse"],
            ascending=False,
        )
        .iloc[0]
    )

    highest_zone = (
        by_zone.sort_values(
            ["mae", "rmse"],
            ascending=False,
        )
        .iloc[0]
    )

    positive_demand = by_demand.loc[
        by_demand[
            "mape_positive_pct"
        ].notna()
    ]

    if not np.isfinite(
        positive_demand[
            "mape_positive_pct"
        ]
    ).all():
        raise ValueError(
            "Invalid positive-demand MAPE values."
        )

    zero_row = by_demand.loc[
        by_demand["demand_level"]
        == "Zero (0)"
    ]

    if len(zero_row) != 1:
        raise ValueError(
            "Zero-demand band missing."
        )

    if not pd.isna(
        zero_row.iloc[0][
            "mape_positive_pct"
        ]
    ):
        raise ValueError(
            "MAPE should not be calculated "
            "for zero actual demand."
        )

    print(
        f"Overall rows: "
        f"{int(row['observations']):,}"
    )

    print(
        f"Zones evaluated: "
        f"{len(by_zone)}"
    )

    print(
        f"Hours evaluated: "
        f"{len(by_hour)}"
    )

    print(
        f"Days evaluated: "
        f"{len(by_day)}"
    )

    print(
        f"Demand levels evaluated: "
        f"{len(by_demand)}"
    )

    print()
    print(
        f"Validated MAE:  "
        f"{float(row['mae']):.4f}"
    )
    print(
        f"Validated RMSE: "
        f"{float(row['rmse']):.4f}"
    )
    print(
        f"Validated R2:   "
        f"{float(row['r2']):.4f}"
    )

    print()
    print(
        "Best day by MAE: "
        f"{best_day['day_of_week']} "
        f"({best_day['mae']:.4f})"
    )

    print(
        "Worst day by MAE: "
        f"{worst_day['day_of_week']} "
        f"({worst_day['mae']:.4f})"
    )

    print(
        "Best hour by MAE: "
        f"{int(best_hour['hour']):02d}:00 "
        f"({best_hour['mae']:.4f})"
    )

    print(
        "Worst hour by MAE: "
        f"{int(worst_hour['hour']):02d}:00 "
        f"({worst_hour['mae']:.4f})"
    )

    print(
        "Highest-error zone: "
        f"{highest_zone['taxi_zone_name']} "
        f"(MAE {highest_zone['mae']:.4f})"
    )

    print()
    print(
        "MAPE zero-demand handling: PASS"
    )

    print(
        "All grouped observation counts reconcile."
    )

    print()
    print(
        "PHASE28_MODEL_EVALUATION_VALIDATION_SUCCESS"
    )


if __name__ == "__main__":
    main()
