#!/usr/bin/env bash
set -euo pipefail

: "${AIRFLOW__CORE__FERNET_KEY:?Set AIRFLOW__CORE__FERNET_KEY in prod.env}"
: "${AIRFLOW__API__SECRET_KEY:?Set AIRFLOW__API__SECRET_KEY in prod.env}"
: "${AIRFLOW__API_AUTH__JWT_SECRET:?Set AIRFLOW__API_AUTH__JWT_SECRET in prod.env}"

if [ -z "${AIRFLOW__DATABASE__SQL_ALCHEMY_CONN:-}" ]; then
  : "${AIRFLOW_DB_USER:?Set AIRFLOW_DB_USER in prod.env}"
  : "${AIRFLOW_DB_PASSWORD:?Set AIRFLOW_DB_PASSWORD in prod.env}"
  : "${AIRFLOW_DB_NAME:?Set AIRFLOW_DB_NAME in prod.env}"

  airflow_db_host="${AIRFLOW_DB_HOST:-db}"
  airflow_db_port="${AIRFLOW_DB_PORT:-5432}"

  export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="postgresql+psycopg2://${AIRFLOW_DB_USER}:${AIRFLOW_DB_PASSWORD}@${airflow_db_host}:${airflow_db_port}/${AIRFLOW_DB_NAME}"
fi

if [ -z "${AIRFLOW__DATABASE__SQL_ALCHEMY_CONN_ASYNC:-}" ]; then
  : "${AIRFLOW_DB_USER:?Set AIRFLOW_DB_USER in prod.env}"
  : "${AIRFLOW_DB_PASSWORD:?Set AIRFLOW_DB_PASSWORD in prod.env}"
  : "${AIRFLOW_DB_NAME:?Set AIRFLOW_DB_NAME in prod.env}"

  airflow_db_host="${AIRFLOW_DB_HOST:-db}"
  airflow_db_port="${AIRFLOW_DB_PORT:-5432}"

  export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN_ASYNC="postgresql+asyncpg://${AIRFLOW_DB_USER}:${AIRFLOW_DB_PASSWORD}@${airflow_db_host}:${airflow_db_port}/${AIRFLOW_DB_NAME}"
fi

exec /entrypoint "$@"
