#!/usr/bin/env bash
# This repo's dev stack: the content-sync daemon (Mongo -> RAG + widget
# cache) and the mirror app (backend/ + frontend/). MongoDB itself, the
# dashboard, and the data contract are owned by the Dashboard repo
# (../Dashboard) -- this repo depends on it only through MONGO_URI.
# See `./dev.sh help`.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$HERE/backend"
ENV_FILE="$BACKEND/.env"
ENV_EXAMPLE="$BACKEND/.env.example"
DEV_DIR="$HERE/.dev"
LOG_DIR="$DEV_DIR/logs"
PID_DIR="$DEV_DIR/pids"

# backend/.venv's python: bin/ on Linux/macOS (the Pi), Scripts/ under Git Bash on Windows.
venv_python() {
  if [ -x "$BACKEND/.venv/bin/python" ]; then echo "$BACKEND/.venv/bin/python"; else echo "$BACKEND/.venv/Scripts/python.exe"; fi
}
PYTHON="$(venv_python)"

CONTENT_SYNC_SCRIPT="$BACKEND/scripts/content_sync_daemon.py"
CONTENT_SYNC_MIRROR_ID="dev-content-sync"

# Shown when Mongo can't be reached. A local Mongo is the one the Dashboard
# repo's ./dev.sh up starts on this machine; Atlas needs nothing started here.
local_mongo_hint() { echo "start it from the Dashboard repo on this machine: ../Dashboard/dev.sh up"; }
atlas_hint() { echo "check MONGO_URI in backend/.env, and that this machine's public IP is in the Atlas cluster's IP access list"; }

log() { echo "dev.sh: $*"; }
die() { echo "dev.sh: ERROR: $*" >&2; exit 1; }

# -- env --------------------------------------------------------------------

ensure_env_file() {
  if [ -f "$ENV_FILE" ]; then
    return 0
  fi
  log ".env missing -- creating it from .env.example"
  cp "$ENV_EXAMPLE" "$ENV_FILE"
}

load_env() {
  if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
  fi
  MONGO_URI="${MONGO_URI:-mongodb://localhost:27017/ieee?directConnection=true}"
  # An Atlas SRV lookup + TLS handshake alone can take ~2s; local is instant.
  if mongo_uri_is_local; then MONGO_TIMEOUT_MS=1500; else MONGO_TIMEOUT_MS=8000; fi
  export MONGO_URI MONGO_TIMEOUT_MS
}

# -- local vs remote Mongo ------------------------------------------------------
# MONGO_URI may hold credentials (e.g. an Atlas mongodb+srv:// URI), so it is
# never printed -- only a label -- and the Python helpers below read it from
# the environment rather than having it pasted into their source (and argv).

mongo_uri_is_local() {
  case "$MONGO_URI" in
    mongodb://*) ;;
    *) return 1 ;;
  esac
  local authority="${MONGO_URI#mongodb://}" host
  authority="${authority%%[/?]*}"   # drop /db?options
  authority="${authority##*@}"      # drop user:pass@
  [ -n "$authority" ] || return 1
  local IFS=,
  for host in $authority; do
    case "$host" in
      localhost|localhost:*|127.0.0.1|127.0.0.1:*|"[::1]"|"[::1]:"*) ;;
      *) return 1 ;;
    esac
  done
}

mongo_label() {
  if mongo_uri_is_local; then
    echo "local"
  elif [[ "$MONGO_URI" == *.mongodb.net* ]]; then
    echo "Atlas (remote)"
  else
    echo "remote"
  fi
}

# -- helpers ------------------------------------------------------------------

# Prints why Mongo can't be reached -- credentials stripped -- or nothing if it can.
mongo_ping_error() {
  [ -x "$PYTHON" ] || { echo "backend/.venv is missing (run ./dev.sh up once to create it)"; return; }
  "$PYTHON" -c "
import os, re
try:
    from pymongo import MongoClient
    MongoClient(os.environ['MONGO_URI'], serverSelectionTimeoutMS=int(os.environ['MONGO_TIMEOUT_MS'])).admin.command('ping')
except ImportError as error:
    print(f'{error} -- the data extra is not installed in .venv')
except Exception as error:
    print(type(error).__name__ + ': ' + re.sub(r'://[^/?@ ]*@', '://', str(error))[:400])
" 2>&1
}

mongo_hint() {
  if mongo_uri_is_local; then local_mongo_hint; else atlas_hint; fi
}

require_mongo() {
  local reason
  reason="$(mongo_ping_error)"
  [ -z "$reason" ] || die "can't reach Mongo ($(mongo_label)): $reason
  -> $(mongo_hint)"
}

wait_for_mongo_truthy() {
  # wait_for_mongo_truthy <python-expr-returning-bool> [tries]
  local expr="$1" tries="${2:-60}"
  for _ in $(seq 1 "$tries"); do
    [ "$("$PYTHON" -c "
import os
from pymongo import MongoClient
client = MongoClient(os.environ['MONGO_URI'], serverSelectionTimeoutMS=int(os.environ['MONGO_TIMEOUT_MS']))
db = client.get_default_database()
print($expr)
" 2>/dev/null)" = "True" ] && return 0
    sleep 0.5
  done
  return 1
}

ensure_backend_venv() {
  if ! "$PYTHON" -c "import pymongo, qdrant_client, sentence_transformers" >/dev/null 2>&1; then
    log "first run, installing data+assistant extras (pulls in torch -- can take a few minutes)..."
    (cd "$BACKEND" && uv sync --extra data --extra assistant)
    PYTHON="$(venv_python)"
  fi
}

content_sync_pattern() { echo "python.*scripts/content_sync_daemon\\.py"; }

find_pid() {
  local pidfile="$1" pattern="$2"
  if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile" 2>/dev/null)" 2>/dev/null; then
    cat "$pidfile"
    return 0
  fi
  local pid
  pid="$(pgrep -f "$pattern" | head -1 || true)"
  if [ -n "$pid" ]; then
    echo "$pid" >"$pidfile"
    echo "$pid"
    return 0
  fi
  rm -f "$pidfile"
  return 1
}

stop_proc() {
  local pidfile="$1" pattern="$2" label="$3" pid
  if pid="$(find_pid "$pidfile" "$pattern")"; then
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.25
    done
    kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
    rm -f "$pidfile"
    log "$label: stopped"
  else
    log "$label: not running"
  fi
}

# -- content-sync daemon lifecycle -------------------------------------------

start_content_sync() {
  if find_pid "$PID_DIR/content-sync.pid" "$(content_sync_pattern)" >/dev/null; then
    log "content-sync: already running (pid $(cat "$PID_DIR/content-sync.pid"))"
    return 0
  fi
  ensure_backend_venv
  require_mongo
  mkdir -p "$LOG_DIR" "$PID_DIR"
  (
    cd "$BACKEND"
    GLASSCUBE_MIRROR_ID="$CONTENT_SYNC_MIRROR_ID" \
      nohup "$PYTHON" "$CONTENT_SYNC_SCRIPT" \
      >>"$LOG_DIR/content-sync.log" 2>&1 &
    echo $! >"$PID_DIR/content-sync.pid"
  )
  log "content-sync: waiting for the first Mongo -> Qdrant reconcile..."
  wait_for_mongo_truthy "db.mirror_status.find_one({'mirror_id': '$CONTENT_SYNC_MIRROR_ID'}) is not None" 60 \
    || die "content-sync daemon did not report in -- see $LOG_DIR/content-sync.log"
  log "content-sync: up (pid $(cat "$PID_DIR/content-sync.pid")) -- dashboard edits now reach the RAG + widget cache live"
}

# -- subcommands --------------------------------------------------------------

cmd_up() {
  ensure_env_file
  load_env
  mkdir -p "$DEV_DIR" "$LOG_DIR" "$PID_DIR"
  start_content_sync
  echo
  echo "================================================================"
  echo " Content sync is up -- Mongo: $(mongo_label)"
  echo " Stop:   ./dev.sh down"
  echo " Status: ./dev.sh status"
  echo " Logs:   ./dev.sh logs"
  echo " The dashboard itself lives in the Dashboard repo (../Dashboard)."
  echo "================================================================"
}

cmd_down() {
  load_env
  stop_proc "$PID_DIR/content-sync.pid" "$(content_sync_pattern)" "content-sync"
}

cmd_status() {
  load_env
  echo "Mongo: $(mongo_label)"
  local reason
  reason="$(mongo_ping_error)"
  if [ -z "$reason" ]; then
    echo "  reachable"
  else
    echo "  NOT reachable: $reason"
    echo "  -> $(mongo_hint)"
  fi
  echo
  echo "Content sync:"
  if find_pid "$PID_DIR/content-sync.pid" "$(content_sync_pattern)" >/dev/null; then
    echo "  up (pid $(cat "$PID_DIR/content-sync.pid"))"
    if [ -z "$reason" ]; then
      "$PYTHON" -c "
import os
from pymongo import MongoClient
client = MongoClient(os.environ['MONGO_URI'], serverSelectionTimeoutMS=int(os.environ['MONGO_TIMEOUT_MS']))
db = client.get_default_database()
m = db.mirror_status.find_one({'mirror_id': '$CONTENT_SYNC_MIRROR_ID'})
print('  last synced:', m['last_sync_at'] if m else 'never yet')
print('  last error: ', m.get('last_error') if m else None)
" 2>/dev/null || true
    fi
  else
    echo "  down"
  fi
  echo
  local mirror_pid
  mirror_pid="$(pgrep -f 'python.* -m glasscube' | head -1 || true)"
  echo "Mirror app (python -m glasscube):"
  if [ -n "$mirror_pid" ]; then
    echo "  up (pid $mirror_pid)"
  else
    echo "  down"
  fi
}

cmd_logs() {
  mkdir -p "$LOG_DIR"
  tail -f "$LOG_DIR/content-sync.log"
}

cmd_mirror() {
  load_env
  ensure_backend_venv
  require_mongo
  # The mirror app does its own full Mongo<->Qdrant sync; it can't share
  # Qdrant's embedded storage lock with the standalone content-sync daemon
  # at the same time, so stop that first (`up` brings it back later).
  if find_pid "$PID_DIR/content-sync.pid" "$(content_sync_pattern)" >/dev/null; then
    log "stopping the content-sync daemon first (the mirror app does its own syncing; they can't both hold Qdrant's storage lock)"
    stop_proc "$PID_DIR/content-sync.pid" "$(content_sync_pattern)" "content-sync"
  fi
  cd "$BACKEND"
  exec uv run python -m glasscube club
}

cmd_help() {
  cat <<'EOF'
Usage: ./dev.sh <command>

  up        Start the content-sync daemon (Mongo -> assistant RAG + mirror's
            cached widget data). Needs Mongo reachable (see status). First
            run installs the data/assistant extras (torch etc.).
  down      Stop it.
  status    Mongo reachable? + content-sync up/last-sync + mirror app up?
  logs      Tail the content-sync daemon's log.
  mirror    Run the full camera-driven mirror app (python -m glasscube club,
            frontend included) with MONGO_URI from backend/.env. Stops the
            content-sync daemon first (see
            note below); `up` brings it back afterward.
  help      This.

MongoDB itself, the dashboard, and infra/mongo/CONTRACT.md are owned by
the Dashboard repo: https://github.com/SmartGlassCube/Dashboard
Point backend/.env (MONGO_URI) at whatever Mongo its ./dev.sh up
started, and run that repo's own ./dev.sh up first.

The content-sync daemon and the mirror app can't run at the same time
(Qdrant's embedded storage takes an exclusive lock) -- `mirror` stops the
daemon for you, `up` starts it again.
EOF
}

main() {
  local cmd="${1:-help}"
  [ $# -gt 0 ] && shift || true
  case "$cmd" in
    up) cmd_up ;;
    down) cmd_down ;;
    status) cmd_status ;;
    logs) cmd_logs ;;
    mirror) cmd_mirror ;;
    help|-h|--help) cmd_help ;;
    *) echo "unknown command: $cmd" >&2; cmd_help; exit 1 ;;
  esac
}

main "$@"
