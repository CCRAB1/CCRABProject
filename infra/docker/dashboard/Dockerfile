FROM python:3.11-slim

ARG APP_UID=10001
ARG APP_GID=10001

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/tmp \
    XDG_CACHE_HOME=/tmp/.cache

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gdal-bin \
        libgdal-dev \
        libgeos-dev \
        libproj-dev \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY apps/CCRABDashBoard/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /app/requirements.txt

RUN groupadd --gid "${APP_GID}" django \
    && useradd --uid "${APP_UID}" --gid django --home-dir /app --shell /usr/sbin/nologin --no-create-home --no-log-init django

COPY infra/docker/dashboard/entrypoint.sh /usr/local/bin/entrypoint
RUN chmod +x /usr/local/bin/entrypoint

COPY --chown=django:django apps/CCRABDashBoard /app
RUN mkdir -p /app/staticfiles /app/media \
    && chown django:django /app/staticfiles /app/media

USER 10001:10001

ENTRYPOINT ["entrypoint"]
CMD ["gunicorn", "--workers", "3", "--worker-tmp-dir", "/tmp", "--bind", "0.0.0.0:8000", "CCRABDashboard.wsgi:application"]
