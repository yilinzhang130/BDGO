#!/usr/bin/env bash
# ── BD Go — Deploy to VM ──
# Usage:
#   ./scripts/deploy.sh <VM_IP> [SSH_USER]
#
# Prerequisites on the VM:
#   - Docker & Docker Compose installed
#   - Git repo cloned to ~/crm-dashboard (or set REMOTE_DIR)
#   - .env file configured with secrets
#   - data/ directory with crm.db, guidelines.db, BP/, Reports/

set -euo pipefail

# ── Args ──
VM_IP="${1:?Usage: ./scripts/deploy.sh <VM_IP> [SSH_USER]}"
SSH_USER="${2:-root}"
REMOTE_DIR="${REMOTE_DIR:-~/crm-dashboard}"

echo "==> Deploying BD Go to ${SSH_USER}@${VM_IP}"
echo "    Remote directory: ${REMOTE_DIR}"
echo ""

# ── Step 1: Pull latest code ──
echo "--- Step 1/4: Pulling latest code ---"
ssh "${SSH_USER}@${VM_IP}" "cd ${REMOTE_DIR} && git pull origin main"

# ── Step 2: Build and restart containers ──
echo "--- Step 2/4: Building and starting containers ---"
ssh "${SSH_USER}@${VM_IP}" "cd ${REMOTE_DIR} && docker compose up -d --build"

# ── Step 3: Wait for health check ──
echo "--- Step 3/4: Waiting for backend health check ---"
MAX_RETRIES=15
RETRY_INTERVAL=2
for i in $(seq 1 $MAX_RETRIES); do
    if ssh "${SSH_USER}@${VM_IP}" "curl -sf http://localhost:8001/api/health > /dev/null 2>&1"; then
        echo "    Backend is healthy!"
        break
    fi
    if [ "$i" -eq "$MAX_RETRIES" ]; then
        echo "    ERROR: Backend failed health check after $((MAX_RETRIES * RETRY_INTERVAL))s"
        echo "    Check logs: ssh ${SSH_USER}@${VM_IP} 'cd ${REMOTE_DIR} && docker compose logs backend'"
        exit 1
    fi
    echo "    Attempt $i/$MAX_RETRIES — waiting ${RETRY_INTERVAL}s..."
    sleep $RETRY_INTERVAL
done

# ── Step 4: Print status ──
echo "--- Step 4/4: Container status ---"
ssh "${SSH_USER}@${VM_IP}" "cd ${REMOTE_DIR} && docker compose ps"

echo ""
echo "==> Deployment complete!"
echo "    Backend API:  http://${VM_IP}:8001/api/health"
echo "    Nginx proxy:  http://${VM_IP}/"
echo ""
echo "    Next steps:"
echo "    - Set NEXT_PUBLIC_API_URL=http://${VM_IP}:8001 in Vercel env vars"
echo "    - Redeploy frontend on Vercel"
