#!/usr/bin/env bash
# =============================================================================
# sync_crm.sh — CRM data sync between local macOS and cloud VM
# =============================================================================
#
# Local is the primary source (AI bulk maintenance).
# VM manually_edited rows have highest priority and survive both directions.
#
# Default (push): local → VM, row-level merge
#   1. Save VM's manually_edited rows
#   2. Full pg_dump local → VM (replaces everything)
#   3. UPSERT saved rows back → VM corrections survive
#
#   --pull: VM manually_edited rows → local (partial merge, not full replace)
#   Only rows where manually_edited=TRUE on VM are fetched and upserted locally.
#
# Mark a VM row as locked after editing:
#   UPDATE "公司" SET manually_edited = TRUE WHERE "客户名称" = 'Pfizer';
#
# Usage:
#   ./scripts/sync_crm.sh [VM_IP] [--restart]   # push
#   ./scripts/sync_crm.sh [VM_IP] --pull         # pull locked rows only
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
LOCAL_PG_DUMP="/opt/homebrew/opt/postgresql@17/bin/pg_dump"
LOCAL_PSQL="/opt/homebrew/opt/postgresql@17/bin/psql"

REMOTE_USER="ubuntu"
REMOTE_DATA_DIR="/home/ubuntu/bdgo/data"
REMOTE_CONTAINER="bdgo_backend"

SSH_KEY=""  # Optional: path to SSH key (e.g. ~/.ssh/id_rsa_vm)

# Tables that participate in row-level merge (have manually_edited column).
# Each entry: "table_name:conflict_key_cols" (key cols are bare, no quotes).
MERGE_TABLE_DEFS=(
  "公司:客户名称"
  "资产:资产名称,所属客户"
  "临床:记录ID"
  "交易:交易名称"
  "IP:专利号"
  "MNC画像:company_name"
)

# Tables to show row counts for in verification
VERIFY_TABLES=("公司" "资产" "临床" "交易")

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

# Build "col1 = EXCLUDED.col1, col2 = EXCLUDED.col2, ..." for all columns
# of $table except the key columns listed (bare names, space-separated).
gen_set_clause() {
  local table="$1"; shift
  local not_in_sql=""
  for col in "$@"; do
    [[ -n "${not_in_sql}" ]] && not_in_sql+=","
    not_in_sql+="'${col}'"
  done
  "${LOCAL_PSQL}" -h localhost -d "${LOCAL_PG_DB}" -tAc "
    SELECT string_agg(
      '\"' || attname || '\" = EXCLUDED.\"' || attname || '\"',
      ', ' ORDER BY attnum
    )
    FROM pg_attribute
    WHERE attrelid = '\"${table}\"'::regclass
      AND attnum > 0 AND NOT attisdropped
      AND attname NOT IN (${not_in_sql})
  " | tr -d '\n' | tr -s ' '
}

# Upsert rows from a local CSV file into a target database via psql.
# Usage: upsert_csv csv_file table conflict_key_sql set_clause_sql psql_cmd...
# psql_cmd is e.g.:   sudo -u postgres psql -d bdgo -q -f -
#             or:     /path/to/psql -h localhost -d bdgo -q -f -
upsert_csv() {
  local csv_file="$1"
  local table="$2"
  local key_sql="$3"       # e.g. '"客户名称"'
  local set_clause="$4"
  shift 4
  # remaining args = psql command to pipe into

  local n
  n=$(tail -n +2 "${csv_file}" | wc -l | tr -d ' ')
  [[ "${n}" -eq 0 ]] && return 0

  {
    printf 'CREATE TEMP TABLE _stage (LIKE "%s" INCLUDING ALL);\n' "${table}"
    printf 'COPY _stage FROM STDIN (FORMAT CSV, HEADER);\n'
    cat "${csv_file}"
    printf '\\.\n'
    printf 'INSERT INTO "%s" SELECT * FROM _stage ON CONFLICT (%s) DO UPDATE SET %s;\n' \
      "${table}" "${key_sql}" "${set_clause}"
    printf 'DROP TABLE _stage;\n'
  } | "$@"

  echo "${n}"
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
  log "========== Pulling VM locked rows → local (${VM_IP}) =========="
else
  log "========== Pushing local → VM with merge (${VM_IP}) =========="
fi

[[ ! -f "${LOCAL_GUIDELINES_DB}" ]] && die "Guidelines DB not found: ${LOCAL_GUIDELINES_DB}"
command -v sqlite3 &>/dev/null || die "sqlite3 not installed"
[[ -f "${LOCAL_PG_DUMP}" ]] || die "pg_dump not found at ${LOCAL_PG_DUMP}"
[[ -f "${LOCAL_PSQL}" ]] || die "psql not found at ${LOCAL_PSQL}"

log "Testing SSH..."
ssh_cmd "echo ok" &>/dev/null || die "SSH to ${REMOTE_USER}@${VM_IP} failed"
log "SSH OK"

# ---------------------------------------------------------------------------
# Step 1: CRM PostgreSQL sync
# ---------------------------------------------------------------------------
log "--- CRM PostgreSQL sync ---"

TMPDIR="$(mktemp -d /tmp/crm_sync.XXXXXX)"
trap 'rm -rf "${TMPDIR}"' EXIT

if [[ "${PULL}" == "true" ]]; then
  # ── Pull: fetch VM's manually_edited rows → upsert into local ────────────
  log "  Fetching VM manually_edited rows..."
  total_pulled=0

  for entry in "${MERGE_TABLE_DEFS[@]}"; do
    table="${entry%%:*}"
    key_cols_raw="${entry##*:}"                        # e.g. 资产名称,所属客户
    key_sql=$(echo "${key_cols_raw}" | sed 's/\([^,]*\)/"\1"/g')  # "资产名称","所属客户"
    IFS=',' read -ra key_arr <<< "${key_cols_raw}"

    csv_file="${TMPDIR}/${table}.csv"

    # Export locked rows from VM
    ssh_cmd "sudo -u postgres psql -d bdgo -q -c \
      \"COPY (SELECT * FROM \\\"${table}\\\" WHERE manually_edited = TRUE) \
        TO STDOUT (FORMAT CSV, HEADER)\"" \
      > "${csv_file}"

    n=$(tail -n +2 "${csv_file}" | wc -l | tr -d ' ')
    [[ "${n}" -eq 0 ]] && log "    ${table}: 0 locked rows — skipped" && continue

    set_clause=$(gen_set_clause "${table}" "${key_arr[@]}")

    upsert_csv "${csv_file}" "${table}" "${key_sql}" "${set_clause}" \
      "${LOCAL_PSQL}" -h localhost -d "${LOCAL_PG_DB}" -q -f - \
      > /dev/null

    log "    ${table}: ${n} locked rows pulled and merged into local"
    total_pulled=$(( total_pulled + n ))
  done

  log "  Pull complete — ${total_pulled} total locked rows merged locally"

else
  # ── Push: save VM locked rows → full dump → restore locked rows ──────────

  # 1. Show local counts
  for table in "${VERIFY_TABLES[@]}"; do
    count=$("${LOCAL_PSQL}" -h localhost -d "${LOCAL_PG_DB}" -tAc \
      "SELECT COUNT(*) FROM \"${table}\";" 2>/dev/null || echo "?")
    log "  Local ${table}: ${count} rows"
  done

  # 2. Save VM's manually_edited rows locally before wiping
  log "  Saving VM manually_edited rows..."
  total_locked=0
  for entry in "${MERGE_TABLE_DEFS[@]}"; do
    table="${entry%%:*}"
    csv_file="${TMPDIR}/${table}.csv"

    ssh_cmd "sudo -u postgres psql -d bdgo -q -c \
      \"COPY (SELECT * FROM \\\"${table}\\\" WHERE manually_edited = TRUE) \
        TO STDOUT (FORMAT CSV, HEADER)\"" \
      > "${csv_file}"

    n=$(tail -n +2 "${csv_file}" | wc -l | tr -d ' ')
    log "    ${table}: ${n} locked rows saved"
    total_locked=$(( total_locked + n ))
  done
  log "  ${total_locked} total locked rows saved"

  # 3. Full local → VM dump (wipes and replaces all VM data)
  log "  Applying local pg_dump to VM..."
  "${LOCAL_PG_DUMP}" \
    -d "${LOCAL_PG_DB}" \
    --clean --if-exists \
    --no-owner --no-privileges \
    | grep -v "^SET transaction_timeout" \
    | ssh -o ConnectTimeout=15 ${SSH_KEY:+-i "${SSH_KEY}"} \
        "${REMOTE_USER}@${VM_IP}" \
        "sudo -u postgres psql -d bdgo -q"
  log "  pg_dump applied"

  # 4. UPSERT locked rows back (VM corrections win over local data)
  if [[ "${total_locked}" -gt 0 ]]; then
    log "  Restoring VM manually_edited rows..."
    for entry in "${MERGE_TABLE_DEFS[@]}"; do
      table="${entry%%:*}"
      key_cols_raw="${entry##*:}"
      key_sql=$(echo "${key_cols_raw}" | sed 's/\([^,]*\)/"\1"/g')
      IFS=',' read -ra key_arr <<< "${key_cols_raw}"
      csv_file="${TMPDIR}/${table}.csv"

      n=$(tail -n +2 "${csv_file}" | wc -l | tr -d ' ')
      [[ "${n}" -eq 0 ]] && continue

      set_clause=$(gen_set_clause "${table}" "${key_arr[@]}")

      upsert_csv "${csv_file}" "${table}" "${key_sql}" "${set_clause}" \
        ssh_cmd "sudo -u postgres psql -d bdgo -q -f -" \
        > /dev/null

      log "    ${table}: ${n} locked rows restored on VM"
    done
  fi

  # 5. Verify row counts
  log "  Verifying row counts..."
  VERIFY_PASS=true
  for table in "${VERIFY_TABLES[@]}"; do
    local_count=$("${LOCAL_PSQL}" -h localhost -d "${LOCAL_PG_DB}" -tAc \
      "SELECT COUNT(*) FROM \"${table}\";" 2>/dev/null || echo "?")
    remote_count=$(ssh_cmd \
      "sudo -u postgres psql -d bdgo -tAc \"SELECT COUNT(*) FROM \\\"${table}\\\";\"" \
      2>/dev/null || echo "?")
    if [[ "${remote_count}" == "${local_count}" ]]; then
      log "    PASS  ${table}: ${local_count}"
    else
      # VM will have more rows if it has manually_edited entries not in local
      log "    INFO  ${table}: local=${local_count} VM=${remote_count} (delta may be locked rows)"
    fi
  done
fi

# ---------------------------------------------------------------------------
# Step 2: Sync Guidelines SQLite (push only)
# ---------------------------------------------------------------------------
if [[ "${PULL}" == "true" ]]; then
  log "--- Guidelines SQLite: skipped on pull ---"
else
  log "--- Guidelines SQLite sync ---"

  sqlite3 "${LOCAL_GUIDELINES_DB}" "PRAGMA wal_checkpoint(TRUNCATE);" 2>/dev/null || true
  LOCAL_G_SIZE="$(stat -f%z "${LOCAL_GUIDELINES_DB}" 2>/dev/null || stat -c%s "${LOCAL_GUIDELINES_DB}")"
  log "  Local guidelines.db: $(( LOCAL_G_SIZE / 1024 )) KB"

  ssh_cmd bash -s <<REMOTE_BACKUP
set -e
DATA="${REMOTE_DATA_DIR}"
mkdir -p "\${DATA}"
[ -f "\${DATA}/guidelines.db" ] && cp "\${DATA}/guidelines.db" "\${DATA}/guidelines.db.bak" || true
REMOTE_BACKUP

  rsync -az --checksum \
    "${LOCAL_GUIDELINES_DB}" \
    "${REMOTE_USER}@${VM_IP}:${REMOTE_DATA_DIR}/"

  log "  Guidelines sync done"
fi

# ---------------------------------------------------------------------------
# Step 3: Optionally restart backend (push only)
# ---------------------------------------------------------------------------
if [[ "${PULL}" == "true" ]]; then
  log "Pull complete"
elif [[ "${RESTART}" == "true" ]]; then
  log "Restarting backend..."
  ssh_cmd "docker restart ${REMOTE_CONTAINER}" | while read -r line; do log "  [docker] ${line}"; done
  sleep 3
  health="$(ssh_cmd "curl -sf http://localhost:8001/api/health" 2>/dev/null || echo "no response")"
  log "  Health check: ${health}"
else
  log "Skipping restart (pass --restart to enable)"
fi

log "========== Sync complete =========="
