from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SOURCE_ROOT = (
    PROJECT_ROOT
    / "data"
    / "silver"
    / "taxi"
    / "year=2025"
)

OUTPUT_ROOT = (
    PROJECT_ROOT
    / "data"
    / "gold"
    / "dropoff_zone_daily"
)

EXPECTED_SOURCE_ROWS = 48_720_337

VALID_MIN_ZONE = 1
VALID_MAX_ZONE = 265
UNKNOWN_ZONE = 0


def read_month(month: int) -> pd.DataFrame:

    month_root = (
        SOURCE_ROOT
        / f"month={month:02d}"
    )

    if not month_root.exists():
        raise FileNotFoundError(
            f"Missing Taxi Silver partition: "
            f"{month_root}"
        )

    dataset = ds.dataset(
        month_root,
        format="parquet",
    )

    table = dataset.to_table(
        columns=[
            "tpep_dropoff_datetime",
            "DOLocationID",
        ]
    )

    return table.to_pandas()


def build_month_aggregate(
    df: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    dict[str, int],
]:

    source_rows = len(df)

    df = df.copy()

    df["dropoff_timestamp"] = pd.to_datetime(
        df["tpep_dropoff_datetime"]
    )

    null_timestamp = int(
        df["dropoff_timestamp"]
        .isna()
        .sum()
    )

    in_2025 = (
        df["dropoff_timestamp"]
        .dt.year
        == 2025
    )

    outside_2025 = int(
        (
            df["dropoff_timestamp"].notna()
            & ~in_2025
        ).sum()
    )

    included = df.loc[
        in_2025
    ].copy()

    null_zone = int(
        included["DOLocationID"]
        .isna()
        .sum()
    )

    invalid_zone = int(
        (
            included["DOLocationID"].notna()
            & (
                (
                    included["DOLocationID"]
                    < VALID_MIN_ZONE
                )
                |
                (
                    included["DOLocationID"]
                    > VALID_MAX_ZONE
                )
            )
        ).sum()
    )

    valid_zone = (
        included["DOLocationID"].notna()
        & included["DOLocationID"].between(
            VALID_MIN_ZONE,
            VALID_MAX_ZONE,
        )
    )

    included["dropoff_zone_id"] = (
        included["DOLocationID"]
        .where(
            valid_zone,
            UNKNOWN_ZONE,
        )
        .astype("int32")
    )

    included["full_date"] = (
        included["dropoff_timestamp"]
        .dt.date
    )

    aggregate = (
        included.groupby(
            [
                "full_date",
                "dropoff_zone_id",
            ],
            observed=True,
            as_index=False,
        )
        .size()
        .rename(
            columns={
                "size": "dropoff_trips",
            }
        )
    )

    aggregate["dropoff_trips"] = (
        aggregate["dropoff_trips"]
        .astype("int64")
    )

    stats = {
        "source_rows": source_rows,
        "included_rows": len(included),
        "outside_2025": outside_2025,
        "null_timestamp": null_timestamp,
        "null_zone": null_zone,
        "invalid_zone": invalid_zone,
    }

    return aggregate, stats


def write_output(
    aggregate: pd.DataFrame,
) -> None:

    if OUTPUT_ROOT.exists():
        import shutil

        shutil.rmtree(
            OUTPUT_ROOT
        )

    aggregate = aggregate.copy()

    aggregate["full_date"] = pd.to_datetime(
        aggregate["full_date"]
    )

    aggregate["year"] = (
        aggregate["full_date"]
        .dt.year
        .astype("int32")
    )

    aggregate["month"] = (
        aggregate["full_date"]
        .dt.month
        .astype("int32")
    )

    aggregate["full_date"] = (
        aggregate["full_date"]
        .dt.date
    )

    for month in range(1, 13):

        month_df = aggregate.loc[
            aggregate["month"] == month,
            [
                "full_date",
                "dropoff_zone_id",
                "dropoff_trips",
            ],
        ].copy()

        output_dir = (
            OUTPUT_ROOT
            / "year=2025"
            / f"month={month:02d}"
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        table = pa.Table.from_pandas(
            month_df,
            preserve_index=False,
        )

        pq.write_table(
            table,
            output_dir
            / "dropoff_zone_daily.parquet",
            compression="snappy",
        )


def main() -> None:

    monthly_aggregates = []

    total_source_rows = 0
    total_included_rows = 0
    total_outside_2025 = 0
    total_null_timestamp = 0
    total_null_zone = 0
    total_invalid_zone = 0

    for month in range(1, 13):

        print(
            f"Processing Taxi Silver "
            f"month {month:02d}..."
        )

        df = read_month(month)

        aggregate, stats = (
            build_month_aggregate(df)
        )

        monthly_aggregates.append(
            aggregate
        )

        total_source_rows += (
            stats["source_rows"]
        )

        total_included_rows += (
            stats["included_rows"]
        )

        total_outside_2025 += (
            stats["outside_2025"]
        )

        total_null_timestamp += (
            stats["null_timestamp"]
        )

        total_null_zone += (
            stats["null_zone"]
        )

        total_invalid_zone += (
            stats["invalid_zone"]
        )

        print(
            f"  Source rows: "
            f"{stats['source_rows']:,}"
        )

    if (
        total_source_rows
        != EXPECTED_SOURCE_ROWS
    ):
        raise ValueError(
            f"Taxi Silver source count "
            f"mismatch: "
            f"{total_source_rows:,} "
            f"vs expected "
            f"{EXPECTED_SOURCE_ROWS:,}"
        )

    combined = pd.concat(
        monthly_aggregates,
        ignore_index=True,
    )

    final = (
        combined.groupby(
            [
                "full_date",
                "dropoff_zone_id",
            ],
            observed=True,
            as_index=False,
        )["dropoff_trips"]
        .sum()
    )

    represented_rows = int(
        final["dropoff_trips"].sum()
    )

    if (
        represented_rows
        != total_included_rows
    ):
        raise ValueError(
            "Drop-off aggregate reconciliation "
            "failed."
        )

    if final.duplicated(
        subset=[
            "full_date",
            "dropoff_zone_id",
        ]
    ).any():
        raise ValueError(
            "Duplicate Date x Drop-off Zone "
            "grain detected."
        )

    dates = pd.to_datetime(
        final["full_date"]
    )

    if dates.min() != pd.Timestamp(
        "2025-01-01"
    ):
        raise ValueError(
            f"Unexpected first drop-off date: "
            f"{dates.min()}"
        )

    if dates.max() != pd.Timestamp(
        "2025-12-31"
    ):
        raise ValueError(
            f"Unexpected last drop-off date: "
            f"{dates.max()}"
        )

    write_output(final)

    print()
    print(
        "===== DROPOFF AGGREGATE "
        "RECONCILIATION ====="
    )

    print(
        f"Taxi Silver rows: "
        f"{total_source_rows:,}"
    )

    print(
        f"2025 drop-off rows represented: "
        f"{total_included_rows:,}"
    )

    print(
        f"Drop-offs outside calendar 2025: "
        f"{total_outside_2025:,}"
    )

    print(
        f"Null drop-off timestamps: "
        f"{total_null_timestamp:,}"
    )

    print(
        f"Null drop-off zone IDs mapped "
        f"to DW unknown: "
        f"{total_null_zone:,}"
    )

    print(
        f"Invalid drop-off zone IDs mapped "
        f"to DW unknown: "
        f"{total_invalid_zone:,}"
    )

    print(
        f"Aggregate rows: "
        f"{len(final):,}"
    )

    print(
        f"Aggregate trip sum: "
        f"{represented_rows:,}"
    )

    print(
        f"Distinct dates: "
        f"{dates.dt.date.nunique()}"
    )

    print(
        f"Distinct drop-off zone IDs: "
        f"{final['dropoff_zone_id'].nunique()}"
    )

    print()
    print(
        "POWERBI_DROPOFF_AGGREGATE_SUCCESS"
    )


if __name__ == "__main__":
    main()
