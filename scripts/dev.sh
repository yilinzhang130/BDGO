#!/usr/bin/env bash
# scripts/dev.sh — one-command local dev for BDGO
#
# Brings up the FastAPI backend (port 8000) and the Next.js frontend
# (port 3000) in two subprocesses, with proper cleanup on Ctrl-C and
# pre-flight checks for .env, .venv, and node_modules.
#
# Usage:
#   scripts/dev.sh            # start both
#   scripts/dev.sh api        # backend only
#   scripts/dev.sh frontend   # frontend only
#   scripts/dev.sh --check    # pre-flight only, no start

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# ─────────────────────────────────────────────────────────────
# Colors
# ─────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()   { printf "${BLUE}[dev]${NC} %s\n" "$*"; }
ok()    { printf "${GREEN}[ok]${NC}  %s\n" "$*"; }
warn()  { printf "${YELLOW}[warn]${NC} %s\n" "$*"; }
err()   { printf "${RED}[err]${NC} %s\n" "$*" >&2; }

# ─────────────────────────────────────────────────────────────
# Pre-flight checks
# ─────────────────────────────────────────────────────────────
preflight() {
  local errs=0

  # .env
  if [[ ! -f .env ]]; then
    err ".env missing — copy .env.example to .env, set JWT_SECRET + MINIMAX_API_KEY"
    err "  cp .env.example .env"
    err "  python3 -c 'import secrets; print(\"JWT_SECRET=\" + secrets.token_hex(32))' >> .env"
    errs=$((errs+1))
  else
    ok ".env present"
    if ! grep -q "^MINIMAX_API_KEY=." .env; then
      warn "MINIMAX_API_KEY is empty in .env — LLM features (incl. /draft-X arg parsing) will fail"
    fi
    if ! grep -q "^JWT_SECRET=." .env; then
      warn "JWT_SECRET is empty in .env — DB-mode startup will refuse"
    fi
  fi

  # api/.venv
  if [[ ! -d api/.venv ]]; then
    err "api/.venv missing — run:"
    err "  cd api && uv venv && uv pip install -r requirements.txt"
    errs=$((errs+1))
  else
    ok "api/.venv present"
  fi

  # frontend/node_modules
  if [[ ! -d frontend/node_modules ]]; then
    err "frontend/node_modules missing — run:"
    err "  cd frontend && npm install"
    errs=$((errs+1))
  else
    ok "frontend/node_modules present"
  fi

  # Port collisions
  if lsof -i :8000 -t >/dev/null 2>&1; then
    warn "port 8000 already in use — kill the existing process first:"
    warn "  lsof -i :8000 -t | xargs kill"
  fi
  if lsof -i :3000 -t >/dev/null 2>&1; then
    warn "port 3000 already in use — kill the existing process first:"
    warn "  lsof -i :3000 -t | xargs kill"
  fi

  return $errs
}

# ─────────────────────────────────────────────────────────────
# Start helpers
# ─────────────────────────────────────────────────────────────
start_api() {
  log "starting backend (uvicorn :8000)…"
  cd "$ROOT/api"
  exec ./.venv/bin/uvicorn main:app --reload --host 127.0.0.1 --port 8000
}

start_frontend() {
  log "starting frontend (next dev :3000)…"
  cd "$ROOT/frontend"
  exec npm run dev
}

# ─────────────────────────────────────────────────────────────
# Argument dispatch
# ─────────────────────────────────────────────────────────────
case "${1:-both}" in
  --check|-c)
    preflight && ok "ready to start. run: scripts/dev.sh" || exit 1
    ;;
  api)
    preflight || exit 1
    start_api
    ;;
  frontend|fe)
    preflight || exit 1
    start_frontend
    ;;
  both|"")
    preflight || exit 1
    log "starting both api + frontend; Ctrl-C kills both"
    log "  backend logs prefixed [api]"
    log "  frontend logs prefixed [fe]"
    log "  api:      http://localhost:8000/docs"
    log "  frontend: http://localhost:3000"

    # Run both in background and forward SIGINT to children
    (cd "$ROOT/api"      && ./.venv/bin/uvicorn main:app --reload --host 127.0.0.1 --port 8000 2>&1 | sed -u 's/^/[api] /') &
    API_PID=$!
    (cd "$ROOT/frontend" && npm run dev                                                          2>&1 | sed -u 's/^/[fe]  /') &
    FE_PID=$!

    # Trap Ctrl-C and forward to children
    cleanup() {
      log "shutting down…"
      kill "$API_PID" "$FE_PID" 2>/dev/null || true
      wait 2>/dev/null || true
      ok "stopped"
      exit 0
    }
    trap cleanup INT TERM

    # If either child exits, take down the other
    wait -n
    log "one of api/frontend exited; tearing down the other"
    kill "$API_PID" "$FE_PID" 2>/dev/null || true
    wait 2>/dev/null || true
    ;;
  -h|--help|help)
    cat <<USAGE
scripts/dev.sh — local BDGO dev launcher

Usage:
  scripts/dev.sh             start both api (:8000) + frontend (:3000)
  scripts/dev.sh api         backend only
  scripts/dev.sh frontend    frontend only
  scripts/dev.sh --check     pre-flight checks only (no start)
  scripts/dev.sh --help      this message

Pre-flight verifies:
  - .env present (with JWT_SECRET + MINIMAX_API_KEY)
  - api/.venv exists
  - frontend/node_modules exists
  - ports 8000/3000 free

First-time setup:
  cp .env.example .env
  python3 -c 'import secrets; print("JWT_SECRET=" + secrets.token_hex(32))' >> .env
  # paste your MINIMAX_API_KEY into .env
  cd api && uv venv && uv pip install -r requirements.txt && cd ..
  cd frontend && npm install && cd ..
USAGE
    ;;
  *)
    err "unknown command: $1 (try --help)"
    exit 1
    ;;
esac
