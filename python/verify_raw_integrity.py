import csv
import hashlib
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_ROOT = (
    PROJECT_ROOT
    / "data"
    / "raw"
)

BASELINE_FILE = (
    PROJECT_ROOT
    / "reports"
    / "raw_integrity"
    / "raw_file_checksums.csv"
)


def sha256_file(file_path, chunk_size=1024 * 1024):

    digest = hashlib.sha256()

    with open(file_path, "rb") as file:

        while True:

            chunk = file.read(chunk_size)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def load_baseline():

    if not BASELINE_FILE.exists():

        raise FileNotFoundError(
            f"Checksum baseline not found: "
            f"{BASELINE_FILE}"
        )

    baseline = {}

    with open(
        BASELINE_FILE,
        "r",
        encoding="utf-8",
        newline="",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            baseline[
                row["relative_path"]
            ] = {
                "sha256": row["sha256"],
                "file_size_bytes": int(
                    row["file_size_bytes"]
                ),
            }

    return baseline


def get_current_files():

    current = {}

    files = sorted(
        path
        for path in RAW_ROOT.rglob("*")
        if path.is_file()
        and path.name != ".gitkeep"
    )

    for path in files:

        relative_path = str(
            path.relative_to(RAW_ROOT)
        ).replace("\\", "/")

        current[relative_path] = path

    return current


def main():

    print("=" * 70)
    print("RAW DATA INTEGRITY VERIFICATION")
    print("=" * 70)

    baseline = load_baseline()
    current = get_current_files()

    expected_paths = set(
        baseline.keys()
    )

    current_paths = set(
        current.keys()
    )

    missing = sorted(
        expected_paths - current_paths
    )

    unexpected = sorted(
        current_paths - expected_paths
    )

    common = sorted(
        expected_paths & current_paths
    )

    modified = []

    print(
        f"Expected files: {len(expected_paths)}"
    )

    print(
        f"Current files:  {len(current_paths)}"
    )

    print()
    print(
        "Checking SHA-256 hashes..."
    )
    print()

    for index, relative_path in enumerate(
        common,
        start=1,
    ):

        file_path = current[
            relative_path
        ]

        current_size = (
            file_path.stat().st_size
        )

        expected_size = (
            baseline[
                relative_path
            ]["file_size_bytes"]
        )

        expected_hash = (
            baseline[
                relative_path
            ]["sha256"]
        )

        print(
            f"[{index}/{len(common)}] "
            f"{relative_path}"
        )

        if current_size != expected_size:

            modified.append(
                {
                    "path": relative_path,
                    "reason": (
                        "FILE_SIZE_CHANGED"
                    ),
                }
            )

            continue

        current_hash = sha256_file(
            file_path
        )

        if current_hash != expected_hash:

            modified.append(
                {
                    "path": relative_path,
                    "reason": (
                        "SHA256_CHANGED"
                    ),
                }
            )

    print()
    print("=" * 70)
    print("VERIFICATION RESULT")
    print("=" * 70)

    print(
        f"Expected files: {len(expected_paths)}"
    )

    print(
        f"Current files:  {len(current_paths)}"
    )

    print(
        f"Modified:       {len(modified)}"
    )

    print(
        f"Missing:        {len(missing)}"
    )

    print(
        f"Unexpected:     {len(unexpected)}"
    )

    if modified:

        print()
        print("Modified files:")

        for item in modified:

            print(
                f"- {item['path']} "
                f"[{item['reason']}]"
            )

    if missing:

        print()
        print("Missing files:")

        for path in missing:
            print(f"- {path}")

    if unexpected:

        print()
        print("Unexpected files:")

        for path in unexpected:
            print(f"- {path}")

    print()

    if (
        len(expected_paths) == 111
        and len(current_paths) == 111
        and not modified
        and not missing
        and not unexpected
    ):

        print(
            "RAW INTEGRITY VERIFICATION SUCCESS"
        )

        sys.exit(0)

    else:

        print(
            "RAW INTEGRITY VERIFICATION FAILED"
        )

        sys.exit(1)


if __name__ == "__main__":
    main()