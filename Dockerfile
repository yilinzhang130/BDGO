# ── BD Go Backend ──
# Multi-stage build for FastAPI + SQLite CRM API

FROM python:3.11-slim AS base

# System deps for psycopg2 (Postgres driver)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev gcc curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (includes api/crm_db.py which is bundled into the repo)
COPY api/ /app/api/

WORKDIR /app/api

EXPOSE 8001

# Health check — hits the /api/health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8001/api/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
