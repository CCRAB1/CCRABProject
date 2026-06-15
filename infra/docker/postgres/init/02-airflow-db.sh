#!/bin/sh
set -eu

: "${AIRFLOW_DB_NAME:?Set AIRFLOW_DB_NAME in the selected env file}"
: "${AIRFLOW_DB_USER:?Set AIRFLOW_DB_USER in the selected env file}"
: "${AIRFLOW_DB_PASSWORD:?Set AIRFLOW_DB_PASSWORD in the selected env file}"

psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  -v airflow_db_name="$AIRFLOW_DB_NAME" \
  -v airflow_db_user="$AIRFLOW_DB_USER" \
  -v airflow_db_password="$AIRFLOW_DB_PASSWORD" <<'EOSQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'airflow_db_user', :'airflow_db_password')
WHERE NOT EXISTS (
  SELECT 1
  FROM pg_catalog.pg_roles
  WHERE rolname = :'airflow_db_user'
)\gexec

SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', :'airflow_db_user', :'airflow_db_password')\gexec

SELECT format('CREATE DATABASE %I OWNER %I', :'airflow_db_name', :'airflow_db_user')
WHERE NOT EXISTS (
  SELECT 1
  FROM pg_catalog.pg_database
  WHERE datname = :'airflow_db_name'
)\gexec

SELECT format('GRANT ALL PRIVILEGES ON DATABASE %I TO %I', :'airflow_db_name', :'airflow_db_user')\gexec
EOSQL
