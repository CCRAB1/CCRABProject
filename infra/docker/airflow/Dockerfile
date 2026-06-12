FROM apache/airflow:3.1.3-python3.11

ARG AIRFLOW_VERSION=3.1.3
ARG PYTHON_VERSION=3.11

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        gdal-bin \
        git \
        libgdal-dev \
        libgeos-dev \
        libpq-dev \
        libproj-dev \
    && rm -rf /var/lib/apt/lists/*

COPY infra/docker/airflow/entrypoint.sh /usr/local/bin/ccrab-airflow-entrypoint
RUN chmod +x /usr/local/bin/ccrab-airflow-entrypoint

USER airflow

ENV AIRFLOW_HOME=/opt/airflow \
    PYTHONPATH=/opt/airflow/dags:/opt/ccrab/dashboard \
    CCRAB_DJANGO_PROJECT_PATH=/opt/ccrab/dashboard

WORKDIR /opt/airflow

COPY --chown=airflow:0 packages/DataUtilities /opt/ccrab/DataUtilities
COPY --chown=airflow:0 packages/ObservationsDatabase /opt/ccrab/ObservationsDatabase
COPY --chown=airflow:0 apps/CCRABDashBoard /opt/ccrab/dashboard
COPY --chown=airflow:0 apps/DataIngestion/airflow/dags /opt/airflow/dags
COPY --chown=airflow:0 infra/docker/scripts/requirements_from_pyproject.py /tmp/requirements_from_pyproject.py
COPY --chown=airflow:0 apps/DataIngestion/pyproject.toml /tmp/dataingestion-pyproject.toml
COPY --chown=airflow:0 apps/CCRABDashBoard/pyproject.toml /tmp/ccrabdashboard-pyproject.toml

RUN python /tmp/requirements_from_pyproject.py \
      --exclude apache-airflow \
      --exclude datautilities \
      --exclude observationsdatabase \
      --exclude djangorestframework-stubs \
      --exclude rest-framework-simplejwt \
      --exclude ruff \
      --exclude nodeenv \
      /tmp/dataingestion-pyproject.toml \
      /tmp/ccrabdashboard-pyproject.toml \
      > /tmp/ccrab-airflow-requirements.txt \
    && pip install --no-cache-dir \
      --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt" \
      "apache-airflow==${AIRFLOW_VERSION}" \
      -r /tmp/ccrab-airflow-requirements.txt \
    && pip install --no-cache-dir --no-deps \
      /opt/ccrab/DataUtilities \
      /opt/ccrab/ObservationsDatabase
