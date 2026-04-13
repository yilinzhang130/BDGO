#!/usr/bin/env bash
# =============================================================================
# sync_crm.sh — One-way data sync: local macOS → cloud VM
# =============================================================================
#
# Syncs:
#   1. CRM data (PostgreSQL): pg_dump openclaw_crm | ssh | psql
#   2. Guidelines SQLite DB:  rsync to ~/bdgo/data/
#
# Usage:
#   ./scripts/sync_crm.sh [VM_IP] [--restart]
#
# Examples:
#   ./scripts/sync_crm.sh 146.56.247.221
#   ./scripts/sync_crm.sh 146.56.247.221 --restart
#   BDGO_VM_IP=146.56.247.221 ./scripts/sync_crm.sh --restart
#
# Crontab (daily 2 AM):
#   0 2 * * * BDGO_VM_IP=146.56.247.221 /path/to/scripts/sync_crm.sh --restart >> ~/sync_crm.log 2>&1
#
# Prerequisites:
#   - SSH key auth configured for VM (no password prompts)
#   - pg_dump (PostgreSQL 17) available locally
#   - sqlite3 installed locally
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
LOCAL_GUIDELINES_DB="${HOME}/.openclaw/workspace/guidelines/guidelines.db"
LOCAL_PG_DB="openclaw_crm"
LOCAL_PG_DUMP="/opt/homebrew/opt/postgresql@17/bin/pg_dump"  # macOS Homebrew path
LOCAL_PSQL="/opt/homebrew/opt/postgresql@17/bin/psql"

REMOTE_USER="ubuntu"
REMOTE_DATA_DIR="/home/ubuntu/bdgo/data"
REMOTE_CONTAINER="bdgo_backend"

SSH_KEY=""  # Optional: path to SSH key (e.g. ~/.ssh/id_rsa_vm)

# Tables to verify after CRM sync
CRM_TABLES=("公司" "资产" "临床" "交易")

# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYNC_LOG="${SCRIPT_DIR}/../sync_crm.log"
RESTART=false
VM_IP=""

log() {
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[${ts}] $*" | tee -a "${SYNC_LOG}"
}

die() { log "ERROR: $*"; exit 1; }

ssh_cmd() {
  local opts=(-o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new)
  [[ -n "${SSH_KEY}" ]] && opts+=(-i "${SSH_KEY}")
  ssh "${opts[@]}" "${REMOTE_USER}@${VM_IP}" "$@"
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
for arg in "$@"; do
  case "${arg}" in
    --restart) RESTART=true ;;
    -*) die "Unknown flag: ${arg}" ;;
    *)  [[ -z "${VM_IP}" ]] && VM_IP="${arg}" || die "Unexpected argument: ${arg}" ;;
  esac
done

[[ -z "${VM_IP}" ]] && VM_IP="${BDGO_VM_IP:-}"
[[ -z "${VM_IP}" ]] && die "VM_IP required. Pass as argument or set BDGO_VM_IP."

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------
log "========== Starting sync to ${VM_IP} =========="

[[ ! -f "${LOCAL_GUIDELINES_DB}" ]] && die "Guidelines DB not found: ${LOCAL_GUIDELINES_DB}"
command -v sqlite3 &>/dev/null || die "sqlite3 not installed"
[[ -f "${LOCAL_PG_DUMP}" ]] || die "pg_dump not found at ${LOCAL_PG_DUMP}"

log "Testing SSH..."
ssh_cmd "echo ok" &>/dev/null || die "SSH to ${REMOTE_USER}@${VM_IP} failed"
log "SSH OK"

# ---------------------------------------------------------------------------
# Step 1: Sync CRM — pg_dump local | ssh | psql on VM
# ---------------------------------------------------------------------------
log "--- CRM PostgreSQL sync ---"

# Count local rows first (store as name=count pairs, bash 3 compatible)
LOCAL_COUNTS_FILE="$(mktemp /tmp/sync_counts.XXXXXX)"
for table in "${CRM_TABLES[@]}"; do
  count="$("${LOCAL_PSQL}" -h localhost -d "${LOCAL_PG_DB}" -tAc "SELECT COUNT(*) FROM \"${table}\";" 2>/dev/null || echo "?")"
  echo "${table}=${count}" >> "${LOCAL_COUNTS_FILE}"
  log "  Local ${table}: ${count} rows"
done

log "Dumping and restoring openclaw_crm via SSH pipe..."
"${LOCAL_PG_DUMP}" \
  -d "${LOCAL_PG_DB}" \
  --clean --if-exists \
  --no-owner --no-privileges \
  | grep -v "^SET transaction_timeout" \
  | ssh -o ConnectTimeout=15 \
      ${SSH_KEY:+-i "${SSH_KEY}"} \
      "${REMOTE_USER}@${VM_IP}" \
      "sudo -u postgres psql -d openclaw_crm -q"

log "CRM dump+restore done"

# Verify remote row counts
log "Verifying remote row counts..."
VERIFY_PASS=true
while IFS='=' read -r table local_count; do
  remote_count="$(ssh_cmd "sudo -u postgres psql -d openclaw_crm -tAc \"SELECT COUNT(*) FROM \\\"${table}\\\";\"" 2>/dev/null || echo "?")"
  if [[ "${remote_count}" == "${local_count}" ]]; then
    log "  PASS  ${table}: ${local_count}"
  else
    log "  FAIL  ${table}: local=${local_count} remote=${remote_count}"
    VERIFY_PASS=false
  fi
done < "${LOCAL_COUNTS_FILE}"
rm -f "${LOCAL_COUNTS_FILE}"
[[ "${VERIFY_PASS}" == "true" ]] && log "All CRM counts match" || log "WARNING: count mismatch — check above"

# ---------------------------------------------------------------------------
# Step 2: Sync Guidelines SQLite
# ---------------------------------------------------------------------------
log "--- Guidelines SQLite sync ---"

sqlite3 "${LOCAL_GUIDELINES_DB}" "PRAGMA wal_checkpoint(TRUNCATE);" 2>/dev/null || true
LOCAL_G_SIZE="$(stat -f%z "${LOCAL_GUIDELINES_DB}" 2>/dev/null || stat -c%s "${LOCAL_GUIDELINES_DB}")"
log "  Local guidelines.db: $(( LOCAL_G_SIZE / 1024 )) KB"

# Backup existing on remote, then transfer
ssh_cmd bash -s <<REMOTE_BACKUP
set -e
DATA="${REMOTE_DATA_DIR}"
mkdir -p "\${DATA}"
[ -f "\${DATA}/guidelines.db" ] && cp "\${DATA}/guidelines.db" "\${DATA}/guidelines.db.bak" || true
echo "backup done"
REMOTE_BACKUP

rsync -az \
  --checksum \
  "${LOCAL_GUIDELINES_DB}" \
  "${REMOTE_USER}@${VM_IP}:${REMOTE_DATA_DIR}/"

log "  Guidelines sync done"

# ---------------------------------------------------------------------------
# Step 3: Optionally restart backend
# ---------------------------------------------------------------------------
if [[ "${RESTART}" == "true" ]]; then
  log "Restarting backend container..."
  ssh_cmd "docker restart ${REMOTE_CONTAINER}" | while read -r line; do log "  [docker] ${line}"; done
  sleep 3
  health="$(ssh_cmd "curl -sf http://localhost:8001/api/health" 2>/dev/null || echo "no response")"
  log "  Health check: ${health}"
else
  log "Skipping restart (pass --restart to enable)"
fi

log "========== Sync complete =========="
