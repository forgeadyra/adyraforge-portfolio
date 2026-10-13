# syntax=docker/dockerfile:1
# Build context is the repo root (the backend imports /ml as a package).

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/ml
RUN groupadd --system app && useradd --system --gid app --home-dir /app app
WORKDIR /app/backend
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=3)"]
EXPOSE 8000

# --- local development (docker compose) ---------------------------------------
FROM base AS dev
COPY backend/requirements/dev.txt /tmp/requirements.txt
RUN pip install --require-hashes -r /tmp/requirements.txt && rm /tmp/requirements.txt
COPY --chown=app:app ml /app/ml
COPY --chown=app:app backend /app/backend
USER app
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# --- production ----------------------------------------------------------------
FROM base AS prod
COPY backend/requirements/base.txt /tmp/requirements.txt
RUN pip install --require-hashes -r /tmp/requirements.txt && rm /tmp/requirements.txt
# Code stays root-owned (read-only to the runtime user); only collected static
# files are writable.
COPY ml /app/ml
COPY backend /app/backend
RUN mkdir -p /app/backend/staticfiles && chown app:app /app/backend/staticfiles
USER app
# Static files are collected at start because production settings refuse to load
# without real secrets, which never exist at image build time.
CMD ["sh", "-c", "python manage.py collectstatic --noinput && exec gunicorn config.wsgi:application --no-control-socket --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-3} --access-logfile -"]
