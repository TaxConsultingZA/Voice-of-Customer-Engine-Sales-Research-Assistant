# ── Stage 1: base — install deps ────────────────────────────────────────────
FROM python:3.11-slim AS base

WORKDIR /app

COPY services/ingestion/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 2: production ─────────────────────────────────────────────────────
FROM base AS production

COPY services/ingestion/app/ ./app/
COPY schemas/ ./schemas/

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
