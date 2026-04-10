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

# Copy application code
COPY api/ /app/api/

# Copy crm_db.py into api/ so db.py can import it without sys.path hacks.
# In production the Docker image ships with the module alongside the app code.
# The original sys.path.insert in db.py adds ~/.openclaw/workspace/scripts which
# won't exist in the container, so placing crm_db.py directly in api/ makes it
# importable from the working directory.
COPY workspace/scripts/crm_db.py /app/api/crm_db.py

WORKDIR /app/api

EXPOSE 8001

# Health check — hits the /api/health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8001/api/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
