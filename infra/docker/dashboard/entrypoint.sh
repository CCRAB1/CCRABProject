#!/bin/sh
set -eu

if [ "${DJANGO_WAIT_FOR_DB:-1}" = "1" ]; then
  echo "Waiting for database connection..."
  python - <<'PY'
import os
import time

import psycopg2

max_attempts = int(os.getenv("DJANGO_DB_WAIT_ATTEMPTS", "30"))
sleep_seconds = float(os.getenv("DJANGO_DB_WAIT_SLEEP", "2"))
attempt = 0

while attempt < max_attempts:
    attempt += 1
    try:
        dbname=os.getenv("DATABASE_NAME")
        user=os.getenv("DATABASE_USER")
        password=os.getenv("DATABASE_PASSWORD")
        host=os.getenv("DATABASE_HOST", "db")
        port=os.getenv("DATABASE_PORT", "5432")

        connection = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port,
        )
        connection.close()
        print("Database connection is ready.")
        break
    except Exception as exc:  # pragma: no cover - startup-only behavior
        print(f"Database {dbname} {host} {port} {user} not ready (attempt {attempt}/{max_attempts}): {exc}")
        time.sleep(sleep_seconds)
else:
    raise SystemExit("Database did not become ready in time.")
PY
fi

if [ "${DJANGO_RUN_MIGRATIONS:-1}" = "1" ]; then
  python manage.py migrate --noinput
fi

if [ "${DJANGO_COLLECTSTATIC:-1}" = "1" ]; then
  python manage.py collectstatic --noinput
fi

exec "$@"
