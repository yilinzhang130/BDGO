#!/usr/bin/env bash
# ── BD Go — Deploy backend to VM ──────────────────────────────
# Usage (from repo root):
#   ./scripts/deploy.sh
#
# Defaults to ubuntu@146.56.247.221. Override with:
#   VM_USER=ubuntu VM_IP=1.2.3.4 ./scripts/deploy.sh
# ──────────────────────────────────────────────────────────────

set -euo pipefail

VM_IP="${VM_IP:-146.56.247.221}"
VM_USER="${VM_USER:-ubuntu}"
REMOTE_DIR="${REMOTE_DIR:-~/app}"

# Resolve repo root (works from any subdirectory)
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> BD Go deploy → ${VM_USER}@${VM_IP}:${REMOTE_DIR}"
echo ""

# ── 1. Sync code ──────────────────────────────────────────────
echo "--- 1/3: rsync api/ + Dockerfile ---"
rsync -avz --progress \
  "${REPO_ROOT}/api/" "${VM_USER}@${VM_IP}:${REMOTE_DIR}/api/"
rsync -avz \
  "${REPO_ROOT}/Dockerfile" "${VM_USER}@${VM_IP}:${REMOTE_DIR}/Dockerfile"

# ── 2. Build image + restart container ────────────────────────
echo ""
echo "--- 2/3: build image + restart container ---"
ssh "${VM_USER}@${VM_IP}" bash <<'REMOTE'
  set -euo pipefail
  cd ~/app
  docker build -t bdgo-api .
  docker rm -f bdgo 2>/dev/null || true
  docker run -d --name bdgo \
    --env-file ~/.env \
    -p 8001:8001 \
    --restart unless-stopped \
    bdgo-api
REMOTE

# ── 3. Health check ───────────────────────────────────────────
echo ""
echo "--- 3/3: health check ---"
for i in $(seq 1 15); do
  if ssh "${VM_USER}@${VM_IP}" "curl -sf http://localhost:8001/api/health" > /dev/null 2>&1; then
    echo "    OK — backend is healthy"
    break
  fi
  if [ "$i" -eq 15 ]; then
    echo "    ERROR: health check failed after 30s"
    echo "    Check logs: ssh ${VM_USER}@${VM_IP} 'docker logs bdgo'"
    exit 1
  fi
  echo "    waiting... ($i/15)"
  sleep 2
done

echo ""
echo "==> Done. http://${VM_IP}:8001/api/health"
