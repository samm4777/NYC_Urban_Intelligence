from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

REPORT_ROOT = (
    PROJECT_ROOT
    / "reports"
    / "feature_importance"
)

IMPURITY_FILE = (
    REPORT_ROOT
    / "random_forest_impurity.csv"
)

PERMUTATION_FILE = (
    REPORT_ROOT
    / "random_forest_permutation.csv"
)

GROUPED_FILE = (
    REPORT_ROOT
    / "grouped_permutation.csv"
)

EXPECTED_FEATURES = 15
EXPECTED_GROUPS = 5


def main() -> None:

    for file in [
        IMPURITY_FILE,
        PERMUTATION_FILE,
        GROUPED_FILE,
    ]:
        if not file.exists():
            raise FileNotFoundError(
                f"Missing Phase 29 artifact: {file}"
            )

    impurity = pd.read_csv(
        IMPURITY_FILE
    )

    permutation = pd.read_csv(
        PERMUTATION_FILE
    )

    grouped = pd.read_csv(
        GROUPED_FILE
    )

    if len(impurity) != EXPECTED_FEATURES:
        raise ValueError(
            f"Expected {EXPECTED_FEATURES} "
            "impurity features."
        )

    if len(permutation) != EXPECTED_FEATURES:
        raise ValueError(
            f"Expected {EXPECTED_FEATURES} "
            "permutation features."
        )

    if len(grouped) != EXPECTED_GROUPS:
        raise ValueError(
            f"Expected {EXPECTED_GROUPS} "
            "feature groups."
        )

    if impurity["feature"].nunique() != EXPECTED_FEATURES:
        raise ValueError(
            "Duplicate impurity features."
        )

    if permutation["feature"].nunique() != EXPECTED_FEATURES:
        raise ValueError(
            "Duplicate permutation features."
        )

    top_permutation = (
        permutation.sort_values(
            "mae_increase_mean",
            ascending=False,
        )
        .iloc[0]
    )

    if top_permutation["feature"] != "lag_1h":
        raise ValueError(
            "Unexpected top permutation feature."
        )

    top_impurity = (
        impurity.sort_values(
            "impurity_importance",
            ascending=False,
        )
        .iloc[0]
    )

    if top_impurity["feature"] != "lag_168h":
        raise ValueError(
            "Unexpected top impurity feature."
        )

    top_group = (
        grouped.sort_values(
            "mae_increase_mean",
            ascending=False,
        )
        .iloc[0]
    )

    if (
        top_group["feature_group"]
        != "historical_demand"
    ):
        raise ValueError(
            "Unexpected top feature group."
        )

    historical = grouped.loc[
        grouped["feature_group"]
        == "historical_demand"
    ].iloc[0]

    weather = grouped.loc[
        grouped["feature_group"]
        == "weather"
    ].iloc[0]

    activity_311 = grouped.loc[
        grouped["feature_group"]
        == "311_activity"
    ].iloc[0]

    if historical["mae_increase_mean"] <= 0:
        raise ValueError(
            "Historical demand should have "
            "positive measured importance."
        )

    if activity_311["mae_increase_mean"] <= 0:
        raise ValueError(
            "311 activity should have "
            "positive measured importance."
        )

    impurity_sum = float(
        impurity[
            "impurity_importance"
        ].sum()
    )

    if abs(impurity_sum - 1.0) > 1e-6:
        raise ValueError(
            f"Impurity importance does not "
            f"sum to 1: {impurity_sum}"
        )

    print(
        f"Individual features validated: "
        f"{len(permutation)}"
    )

    print(
        f"Feature groups validated: "
        f"{len(grouped)}"
    )

    print()
    print(
        "Top permutation feature: "
        f"{top_permutation['feature']}"
    )

    print(
        "Permutation MAE increase: "
        f"{top_permutation['mae_increase_mean']:.6f}"
    )

    print()
    print(
        "Top impurity feature: "
        f"{top_impurity['feature']}"
    )

    print(
        "Impurity importance: "
        f"{top_impurity['impurity_importance']:.6f}"
    )

    print()
    print(
        "Top feature group: "
        f"{top_group['feature_group']}"
    )

    print(
        "Grouped MAE increase: "
        f"{top_group['mae_increase_mean']:.6f}"
    )

    print()
    print(
        "311 grouped MAE increase: "
        f"{activity_311['mae_increase_mean']:.6f}"
    )

    print(
        "Weather grouped MAE increase: "
        f"{weather['mae_increase_mean']:.6f}"
    )

    print()
    print(
        "Tree impurity sum: "
        f"{impurity_sum:.6f}"
    )

    print()
    print(
        "PHASE29_FEATURE_IMPORTANCE_VALIDATION_SUCCESS"
    )


if __name__ == "__main__":
    main()
