# ── BD Go Backend ──
# Multi-stage build for FastAPI + SQLite CRM API

FROM python:3.11-slim AS base

# Switch apt to Tencent Cloud mirror (VM is in mainland China, default Debian repo < 20 kB/s)
RUN sed -i \
    's|http://deb.debian.org/debian|http://mirrors.cloud.tencent.com/debian|g; \
     s|http://security.debian.org/debian-security|http://mirrors.cloud.tencent.com/debian-security|g' \
    /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    (echo "deb http://mirrors.cloud.tencent.com/debian bookworm main contrib non-free" > /etc/apt/sources.list && \
     echo "deb http://mirrors.cloud.tencent.com/debian-security bookworm-security main" >> /etc/apt/sources.list && \
     echo "deb http://mirrors.cloud.tencent.com/debian bookworm-updates main" >> /etc/apt/sources.list)

# System deps: psycopg2 + Tesseract OCR (chi_sim+eng for scanned PDF extraction)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq-dev gcc curl \
        tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://mirrors.cloud.tencent.com/pypi/simple/ \
    --trusted-host mirrors.cloud.tencent.com

# Copy application code (includes api/crm_db.py which is bundled into the repo)
COPY api/ /app/api/

WORKDIR /app/api

EXPOSE 8001

# Health check — hits the /api/health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8001/api/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
