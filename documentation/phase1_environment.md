# Phase 1 — Environment Setup

## Status

PARTIALLY COMPLETE / ENVIRONMENT CONSTRAINT DOCUMENTED

## Python Environment

- Python version: 3.13.14
- Virtual environment: `.venv`
- Package management: pip
- Project dependencies stored in `requirements.txt`

Validated Python packages include:

- Pandas 2.3.3
- PySpark 4.2.0
- Scikit-learn 1.9.0
- Requests
- python-dotenv
- pyodbc
- SQLAlchemy
- pytest
- PyArrow

The project uses Pandas `<3.0` to maintain compatibility with the current PySpark environment.

## Java / PySpark

- Java: Eclipse Adoptium Temurin OpenJDK 17
- Java runtime successfully detected
- `JAVA_HOME` configured
- PySpark JVM runtime test completed successfully
- Spark version: 4.2.0

A test Spark DataFrame was created, displayed, and counted successfully.

Non-blocking Windows Hadoop warnings related to `winutils.exe` and native Hadoop libraries were observed. These do not prevent the current local PySpark workload from running.

## Testing

Pytest is installed.

Due to corporate workstation execution policy, the standalone `pytest` executable may be blocked.

Tests are therefore executed using:

`python -m pytest`

The initial project structure test passed successfully.

## SQL Server

- SQL Server Express installed
- Instance: `SQLEXPRESS`
- SQL Server service running
- SQL Server Management Studio 22 installed
- `sqlcmd` installed
- ODBC Driver 18 for SQL Server available
- Windows Authentication successfully tested
- Python `pyodbc` connection successfully tested

The local development connection requires trusting the SQL Server certificate.

## Power BI

Power BI Desktop is installed and available for later dashboard development.

## Git and GitHub

- Git installed
- Git repository initialized
- Main branch configured
- GitHub remote configured
- Push/pull connectivity validated

Repository:

`https://github.com/samm4777/NYC_Urban_Intelligence`

## Docker / WSL / Airflow Constraint

WSL 2 is installed on the corporate workstation.

However, hardware virtualization is disabled in firmware on the office laptop, and company policy does not permit BIOS/UEFI configuration changes.

As a result, the following components cannot currently be validated on the corporate workstation:

- Docker Desktop
- Docker Compose
- Linux-based Apache Airflow runtime

These components are intentionally deferred to an authorized home computer where virtualization can be enabled and Docker/Airflow can be fully validated.

This limitation does not block:

- Python development
- Pandas processing
- PySpark processing
- SQL Server development
- Machine learning
- Power BI development
- Git/GitHub
- Data acquisition

## Phase 1 Result

The local development environment required for the core data engineering, analytics, SQL, machine learning, and Power BI workflow is operational.

Docker, Docker Compose, and Airflow remain pending and will be completed on an authorized machine.