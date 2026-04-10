#!/usr/bin/env bash
# =============================================================================
# sync_crm.sh — One-way CRM database sync: local macOS → cloud VM
# =============================================================================
#
# Usage:
#   ./scripts/sync_crm.sh [VM_IP] [--restart]
#
#   VM_IP can also be set via BDGO_VM_IP environment variable.
#   If both are provided, the positional argument takes precedence.
#
# Examples:
#   ./scripts/sync_crm.sh 1.2.3.4
#   ./scripts/sync_crm.sh 1.2.3.4 --restart
#   BDGO_VM_IP=1.2.3.4 ./scripts/sync_crm.sh --restart
#
# Crontab (daily at 2 AM):
#   0 2 * * * /path/to/scripts/sync_crm.sh 1.2.3.4 --restart >> /path/to/sync.log 2>&1
#
# Prerequisites:
#   - SSH key-based auth configured for the VM (no password prompts)
#   - sqlite3 installed locally
#   - gzip installed locally (standard on macOS/Linux)
#   - Docker + docker-compose on the VM (if using --restart)
#
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
LOCAL_CRM_DB="${HOME}/.openclaw/workspace/crm-database/crm.db"
LOCAL_GUIDELINES_DB="${HOME}/.openclaw/workspace/guidelines/guidelines.db"
REMOTE_DATA_DIR="/data"
REMOTE_USER="root"
SSH_KEY=""  # Optional: path to SSH private key (e.g., ~/.ssh/id_rsa_vm)

# CRM tables to verify after sync
CRM_TABLES=("公司" "资产" "临床" "交易")

# ---------------------------------------------------------------------------
# Internals — do not edit below unless you know what you're doing
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYNC_LOG="${SCRIPT_DIR}/../sync.log"
TMPDIR_SYNC=""
RESTART=false
VM_IP=""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log() {
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[${ts}] $*" | tee -a "${SYNC_LOG}"
}

die() {
  log "ERROR: $*"
  exit 1
}

cleanup() {
  local exit_code=$?
  if [[ -n "${TMPDIR_SYNC}" && -d "${TMPDIR_SYNC}" ]]; then
    log "Cleaning up temp directory ${TMPDIR_SYNC}"
    rm -rf "${TMPDIR_SYNC}"
  fi
  if [[ ${exit_code} -ne 0 ]]; then
    log "Sync FAILED (exit code ${exit_code})"
  fi
}
trap cleanup EXIT

ssh_cmd() {
  local ssh_opts=(-o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new -o BatchMode=yes)
  if [[ -n "${SSH_KEY}" ]]; then
    ssh_opts+=(-i "${SSH_KEY}")
  fi
  ssh "${ssh_opts[@]}" "${REMOTE_USER}@${VM_IP}" "$@"
}

scp_cmd() {
  local scp_opts=(-o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new -o BatchMode=yes)
  if [[ -n "${SSH_KEY}" ]]; then
    scp_opts+=(-i "${SSH_KEY}")
  fi
  scp "${scp_opts[@]}" "$@"
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
for arg in "$@"; do
  case "${arg}" in
    --restart)
      RESTART=true
      ;;
    -*)
      die "Unknown flag: ${arg}"
      ;;
    *)
      if [[ -z "${VM_IP}" ]]; then
        VM_IP="${arg}"
      else
        die "Unexpected argument: ${arg}"
      fi
      ;;
  esac
done

# Fall back to env var if no positional IP given
if [[ -z "${VM_IP}" ]]; then
  VM_IP="${BDGO_VM_IP:-}"
fi

if [[ -z "${VM_IP}" ]]; then
  die "VM_IP is required. Pass as first argument or set BDGO_VM_IP env var.\n  Usage: $0 [VM_IP] [--restart]"
fi

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
log "========== Starting CRM sync to ${VM_IP} =========="

# Check sqlite3
if ! command -v sqlite3 &>/dev/null; then
  die "sqlite3 is not installed or not in PATH"
fi

# Check local DB files exist
if [[ ! -f "${LOCAL_CRM_DB}" ]]; then
  die "Local CRM database not found: ${LOCAL_CRM_DB}"
fi
if [[ ! -f "${LOCAL_GUIDELINES_DB}" ]]; then
  die "Local guidelines database not found: ${LOCAL_GUIDELINES_DB}"
fi

# Check SSH connectivity
log "Testing SSH connectivity to ${VM_IP}..."
if ! ssh_cmd "echo ok" &>/dev/null; then
  die "Cannot SSH to ${REMOTE_USER}@${VM_IP}. Check SSH key auth and network."
fi
log "SSH connection OK"

# Create temp directory for compressed files
TMPDIR_SYNC="$(mktemp -d "${TMPDIR:-/tmp}/sync_crm.XXXXXX")"
log "Temp directory: ${TMPDIR_SYNC}"

# ---------------------------------------------------------------------------
# Step 1: WAL checkpoint (flush WAL to main DB file)
# ---------------------------------------------------------------------------
log "Checkpointing CRM database WAL..."
sqlite3 "${LOCAL_CRM_DB}" "PRAGMA wal_checkpoint(TRUNCATE);"
log "CRM WAL checkpoint complete"

log "Checkpointing guidelines database WAL..."
sqlite3 "${LOCAL_GUIDELINES_DB}" "PRAGMA wal_checkpoint(TRUNCATE);"
log "Guidelines WAL checkpoint complete"

# ---------------------------------------------------------------------------
# Step 2: Collect local row counts (for verification later)
# ---------------------------------------------------------------------------
declare -A LOCAL_COUNTS
for table in "${CRM_TABLES[@]}"; do
  count="$(sqlite3 "${LOCAL_CRM_DB}" "SELECT COUNT(*) FROM \"${table}\";")"
  LOCAL_COUNTS["${table}"]="${count}"
  log "Local ${table}: ${count} rows"
done

LOCAL_CRM_SIZE="$(stat -f%z "${LOCAL_CRM_DB}" 2>/dev/null || stat -c%s "${LOCAL_CRM_DB}" 2>/dev/null)"
LOCAL_GUIDELINES_SIZE="$(stat -f%z "${LOCAL_GUIDELINES_DB}" 2>/dev/null || stat -c%s "${LOCAL_GUIDELINES_DB}" 2>/dev/null)"
log "Local CRM size: $(( LOCAL_CRM_SIZE / 1024 / 1024 )) MB"
log "Local guidelines size: $(( LOCAL_GUIDELINES_SIZE / 1024 )) KB"

# ---------------------------------------------------------------------------
# Step 3: Cloud-side backup rotation
# ---------------------------------------------------------------------------
log "Rotating backups on remote..."
ssh_cmd bash -s <<'REMOTE_BACKUP'
set -euo pipefail
DATA="/data"

# CRM: rotate 3 backups
rm -f "${DATA}/crm.db.bak.3"
[ -f "${DATA}/crm.db.bak.2" ] && mv "${DATA}/crm.db.bak.2" "${DATA}/crm.db.bak.3"
[ -f "${DATA}/crm.db.bak.1" ] && mv "${DATA}/crm.db.bak.1" "${DATA}/crm.db.bak.2"
[ -f "${DATA}/crm.db"       ] && cp "${DATA}/crm.db" "${DATA}/crm.db.bak.1"

# Guidelines: keep 1 backup
rm -f "${DATA}/guidelines.db.bak"
[ -f "${DATA}/guidelines.db" ] && cp "${DATA}/guidelines.db" "${DATA}/guidelines.db.bak"

echo "Backup rotation done"
REMOTE_BACKUP
log "Remote backup rotation complete"

# ---------------------------------------------------------------------------
# Step 4: Compress local DBs
# ---------------------------------------------------------------------------
log "Compressing databases for transfer..."
gzip -c "${LOCAL_CRM_DB}" > "${TMPDIR_SYNC}/crm.db.gz"
gzip -c "${LOCAL_GUIDELINES_DB}" > "${TMPDIR_SYNC}/guidelines.db.gz"

CRM_GZ_SIZE="$(stat -f%z "${TMPDIR_SYNC}/crm.db.gz" 2>/dev/null || stat -c%s "${TMPDIR_SYNC}/crm.db.gz" 2>/dev/null)"
log "Compressed CRM size: $(( CRM_GZ_SIZE / 1024 / 1024 )) MB"

# ---------------------------------------------------------------------------
# Step 5: Transfer to VM
# ---------------------------------------------------------------------------
log "Transferring compressed databases to ${VM_IP}..."
scp_cmd "${TMPDIR_SYNC}/crm.db.gz" "${TMPDIR_SYNC}/guidelines.db.gz" "${REMOTE_USER}@${VM_IP}:${REMOTE_DATA_DIR}/"
log "Transfer complete"

# ---------------------------------------------------------------------------
# Step 6: Decompress + atomic swap on remote
# ---------------------------------------------------------------------------
log "Decompressing and swapping on remote..."
ssh_cmd bash -s <<'REMOTE_SWAP'
set -euo pipefail
DATA="/data"

# Decompress to .new files
gunzip -c "${DATA}/crm.db.gz" > "${DATA}/crm.db.new"
gunzip -c "${DATA}/guidelines.db.gz" > "${DATA}/guidelines.db.new"

# Atomic swap (mv is atomic on same filesystem)
mv "${DATA}/crm.db.new" "${DATA}/crm.db"
mv "${DATA}/guidelines.db.new" "${DATA}/guidelines.db"

# Clean up compressed files
rm -f "${DATA}/crm.db.gz" "${DATA}/guidelines.db.gz"

# Remove any stale WAL/SHM files from previous runs
rm -f "${DATA}/crm.db-wal" "${DATA}/crm.db-shm"
rm -f "${DATA}/guidelines.db-wal" "${DATA}/guidelines.db-shm"

echo "Atomic swap done"
REMOTE_SWAP
log "Remote swap complete"

# ---------------------------------------------------------------------------
# Step 7: Verify row counts
# ---------------------------------------------------------------------------
log "Verifying remote row counts..."
VERIFY_PASS=true

for table in "${CRM_TABLES[@]}"; do
  remote_count="$(ssh_cmd "sqlite3 ${REMOTE_DATA_DIR}/crm.db \"SELECT COUNT(*) FROM \\\"${table}\\\";\"")"
  local_count="${LOCAL_COUNTS[${table}]}"

  if [[ "${remote_count}" == "${local_count}" ]]; then
    log "  PASS  ${table}: local=${local_count} remote=${remote_count}"
  else
    log "  FAIL  ${table}: local=${local_count} remote=${remote_count}"
    VERIFY_PASS=false
  fi
done

if [[ "${VERIFY_PASS}" == "true" ]]; then
  log "All row count checks PASSED"
else
  log "WARNING: Some row count checks FAILED — investigate before relying on remote data"
fi

# ---------------------------------------------------------------------------
# Step 8: Optionally restart backend
# ---------------------------------------------------------------------------
if [[ "${RESTART}" == "true" ]]; then
  log "Restarting backend container on remote..."
  ssh_cmd "cd /opt/bdgo && docker-compose restart backend" 2>&1 | while read -r line; do
    log "  [docker] ${line}"
  done
  log "Backend restart complete"
else
  log "Skipping backend restart (pass --restart to enable)"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
log "========== Sync complete =========="
