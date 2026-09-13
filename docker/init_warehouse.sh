#!/usr/bin/env bash
set -euo pipefail

SQLCMD=/opt/mssql-tools18/bin/sqlcmd
SERVER=sqlserver
DB=NYC_Urban_Intelligence_DW

echo "Creating database if required..."

$SQLCMD \
  -S "$SERVER" \
  -U sa \
  -P "$MSSQL_SA_PASSWORD" \
  -C \
  -I \
  -b \
  -Q "IF DB_ID(N'$DB') IS NULL CREATE DATABASE [$DB];"

echo "Applying warehouse objects..."

for script in \
  /workspace/sql/phase15/01_create_schemas.sql \
  /workspace/sql/phase15/02_create_dimensions.sql \
  /workspace/sql/phase15/03_create_fact_tables.sql \
  /workspace/sql/phase15/04_add_foreign_keys.sql \
  /workspace/sql/phase15/05_create_etl_audit_tables.sql \
  /workspace/sql/phase15/06_seed_core_dimensions.sql \
  /workspace/sql/phase15/07_load_reference_dimensions.sql \
  /workspace/sql/phase15/08_create_gold_load_objects.sql \
  /workspace/sql/phase16/01_create_incremental_controls.sql \
  /workspace/sql/phase18/01_create_etl_logging.sql
do
  echo "Running: $script"

  $SQLCMD \
    -S "$SERVER" \
    -U sa \
    -P "$MSSQL_SA_PASSWORD" \
    -C \
    -I \
    -b \
    -d "$DB" \
    -i "$script"
done

echo "WAREHOUSE_INIT_COMPLETE"
