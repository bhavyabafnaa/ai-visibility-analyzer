FROM python:3.12-slim AS runtime

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic
COPY docker-entrypoint.sh /usr/local/bin/geolens-entrypoint

RUN python -m pip install --upgrade "pip==26.2" \
    && python -m pip install . \
    && useradd --create-home --uid 10001 appuser \
    && chmod 0555 /usr/local/bin/geolens-entrypoint
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3)"]

ENTRYPOINT ["/usr/local/bin/geolens-entrypoint"]
CMD ["uvicorn", "geolens_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
