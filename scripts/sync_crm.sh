#!/usr/bin/env bash
# =============================================================================
# sync_crm.sh — CRM data sync between local macOS and cloud VM
# =============================================================================
#
# Default (push): local → VM   pg_dump local | ssh | psql on VM
#   --pull       : VM → local  pg_dump on VM | ssh | psql local
#                  Use after manual DB edits on the VM so corrections
#                  propagate back to the local dev database.
#
# Usage:
#   ./scripts/sync_crm.sh [VM_IP] [--restart]
#   ./scripts/sync_crm.sh [VM_IP] --pull
#
# Examples:
#   ./scripts/sync_crm.sh 146.56.247.221            # push local → VM
#   ./scripts/sync_crm.sh 146.56.247.221 --restart  # push + restart backend
#   ./scripts/sync_crm.sh 146.56.247.221 --pull      # pull VM → local
#   BDGO_VM_IP=146.56.247.221 ./scripts/sync_crm.sh --pull
#
# Crontab (daily 2 AM push):
#   0 2 * * * BDGO_VM_IP=146.56.247.221 /path/to/scripts/sync_crm.sh --restart >> ~/sync_crm.log 2>&1
#
# Prerequisites:
#   - SSH key auth configured for VM (no password prompts)
#   - pg_dump + psql (PostgreSQL 17) available locally
#   - sqlite3 installed locally
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
LOCAL_GUIDELINES_DB="${HOME}/.openclaw/workspace/guidelines/guidelines.db"
LOCAL_PG_DB="bdgo"
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
PULL=false
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
    --pull)    PULL=true ;;
    -*) die "Unknown flag: ${arg}" ;;
    *)  [[ -z "${VM_IP}" ]] && VM_IP="${arg}" || die "Unexpected argument: ${arg}" ;;
  esac
done

[[ "${PULL}" == "true" && "${RESTART}" == "true" ]] && die "--pull and --restart cannot be combined"

[[ -z "${VM_IP}" ]] && VM_IP="${BDGO_VM_IP:-}"
[[ -z "${VM_IP}" ]] && die "VM_IP required. Pass as argument or set BDGO_VM_IP."

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------
if [[ "${PULL}" == "true" ]]; then
  log "========== Pulling VM → local (${VM_IP}) =========="
else
  log "========== Pushing local → VM (${VM_IP}) =========="
fi

[[ ! -f "${LOCAL_GUIDELINES_DB}" ]] && die "Guidelines DB not found: ${LOCAL_GUIDELINES_DB}"
command -v sqlite3 &>/dev/null || die "sqlite3 not installed"
[[ -f "${LOCAL_PG_DUMP}" ]] || die "pg_dump not found at ${LOCAL_PG_DUMP}"
[[ -f "${LOCAL_PSQL}" ]] || die "psql not found at ${LOCAL_PSQL}"

log "Testing SSH..."
ssh_cmd "echo ok" &>/dev/null || die "SSH to ${REMOTE_USER}@${VM_IP} failed"
log "SSH OK"

# ---------------------------------------------------------------------------
# Step 1: Sync CRM PostgreSQL
# ---------------------------------------------------------------------------
log "--- CRM PostgreSQL sync ---"

COUNTS_FILE="$(mktemp /tmp/sync_counts.XXXXXX)"

if [[ "${PULL}" == "true" ]]; then
  # ── Pull: VM → local ──────────────────────────────────────────────────────
  # Count VM rows before pull
  for table in "${CRM_TABLES[@]}"; do
    count="$(ssh_cmd "sudo -u postgres psql -d bdgo -tAc \"SELECT COUNT(*) FROM \\\"${table}\\\";\"" 2>/dev/null || echo "?")"
    echo "${table}=${count}" >> "${COUNTS_FILE}"
    log "  VM ${table}: ${count} rows"
  done

  log "Dumping VM bdgo → local psql..."
  ssh -o ConnectTimeout=15 \
      ${SSH_KEY:+-i "${SSH_KEY}"} \
      "${REMOTE_USER}@${VM_IP}" \
      "sudo -u postgres pg_dump -d bdgo --clean --if-exists --no-owner --no-privileges" \
    | grep -v "^SET transaction_timeout" \
    | "${LOCAL_PSQL}" -h localhost -d "${LOCAL_PG_DB}" -q

  log "Pull done — verifying local row counts..."
  VERIFY_PASS=true
  while IFS='=' read -r table vm_count; do
    local_count="$("${LOCAL_PSQL}" -h localhost -d "${LOCAL_PG_DB}" -tAc "SELECT COUNT(*) FROM \"${table}\";" 2>/dev/null || echo "?")"
    if [[ "${local_count}" == "${vm_count}" ]]; then
      log "  PASS  ${table}: ${vm_count}"
    else
      log "  FAIL  ${table}: VM=${vm_count} local=${local_count}"
      VERIFY_PASS=false
    fi
  done < "${COUNTS_FILE}"

else
  # ── Push: local → VM ──────────────────────────────────────────────────────
  for table in "${CRM_TABLES[@]}"; do
    count="$("${LOCAL_PSQL}" -h localhost -d "${LOCAL_PG_DB}" -tAc "SELECT COUNT(*) FROM \"${table}\";" 2>/dev/null || echo "?")"
    echo "${table}=${count}" >> "${COUNTS_FILE}"
    log "  Local ${table}: ${count} rows"
  done

  log "Dumping and restoring bdgo via SSH pipe..."
  "${LOCAL_PG_DUMP}" \
    -d "${LOCAL_PG_DB}" \
    --clean --if-exists \
    --no-owner --no-privileges \
    | grep -v "^SET transaction_timeout" \
    | ssh -o ConnectTimeout=15 \
        ${SSH_KEY:+-i "${SSH_KEY}"} \
        "${REMOTE_USER}@${VM_IP}" \
        "sudo -u postgres psql -d bdgo -q"

  log "Push done — verifying remote row counts..."
  VERIFY_PASS=true
  while IFS='=' read -r table local_count; do
    remote_count="$(ssh_cmd "sudo -u postgres psql -d bdgo -tAc \"SELECT COUNT(*) FROM \\\"${table}\\\";\"" 2>/dev/null || echo "?")"
    if [[ "${remote_count}" == "${local_count}" ]]; then
      log "  PASS  ${table}: ${local_count}"
    else
      log "  FAIL  ${table}: local=${local_count} remote=${remote_count}"
      VERIFY_PASS=false
    fi
  done < "${COUNTS_FILE}"
fi

rm -f "${COUNTS_FILE}"
[[ "${VERIFY_PASS}" == "true" ]] && log "All CRM counts match" || log "WARNING: count mismatch — check above"

# ---------------------------------------------------------------------------
# Step 2: Sync Guidelines SQLite (push only — guidelines are local-only)
# ---------------------------------------------------------------------------
if [[ "${PULL}" == "true" ]]; then
  log "--- Guidelines SQLite: skipped on pull (local-only source) ---"
else
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
fi  # end push-only block

# ---------------------------------------------------------------------------
# Step 3: Optionally restart backend (push only)
# ---------------------------------------------------------------------------
if [[ "${PULL}" == "true" ]]; then
  log "Pull complete — restart not applicable"
elif [[ "${RESTART}" == "true" ]]; then
  log "Restarting backend container..."
  ssh_cmd "docker restart ${REMOTE_CONTAINER}" | while read -r line; do log "  [docker] ${line}"; done
  sleep 3
  health="$(ssh_cmd "curl -sf http://localhost:8001/api/health" 2>/dev/null || echo "no response")"
  log "  Health check: ${health}"
else
  log "Skipping restart (pass --restart to enable)"
fi  # end restart block

log "========== Sync complete =========="
