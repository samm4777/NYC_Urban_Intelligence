from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_required_project_directories_exist():
    required_directories = [
        "airflow",
        "python",
        "spark",
        "sql",
        "tests",
        "data_quality",
        "model",
        "reports",
        "documentation",
        "docker",
        "config",
        "data",
    ]

    for directory in required_directories:
        assert (PROJECT_ROOT / directory).exists(), (
            f"Missing required directory: {directory}"
        )