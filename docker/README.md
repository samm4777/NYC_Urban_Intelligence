# NYC Urban Intelligence - Docker

Phase 21 provides the reproducible local development environment.

## Services

- PostgreSQL 16 - Airflow metadata
- Airflow 3.3.1 API Server
- Airflow Scheduler
- Airflow DAG Processor
- Spark 4.2.0 Master
- Spark 4.2.0 Worker
- SQL Server 2022 Developer
- Airflow and warehouse one-shot initialization services

## Setup

From the repository root:

    Copy-Item docker\.env.example docker\.env

Edit docker\.env and replace the SQL Server password placeholder.

Never commit docker\.env.

## Start

    docker compose --env-file docker\.env -f docker\docker-compose.yml up --build -d

## Status

    docker compose --env-file docker\.env -f docker\docker-compose.yml ps -a

## Local endpoints

Airflow:
http://localhost:8081

Spark Master:
http://localhost:8082

Spark Worker:
http://localhost:8083

SQL Server:
localhost,1433

Database:
NYC_Urban_Intelligence_DW

## Stop

    docker compose --env-file docker\.env -f docker\docker-compose.yml down

## Full reset

WARNING: this deletes local PostgreSQL and SQL Server Docker volumes.

    docker compose --env-file docker\.env -f docker\docker-compose.yml down -v

Azure SQL remains the cloud warehouse target. Docker SQL Server is the local development warehouse.
