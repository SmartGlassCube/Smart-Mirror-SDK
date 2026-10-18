#!/usr/bin/env bash
# This repo's dev stack: the content-sync daemon (Mongo -> RAG + widget
# cache) and the mirror app. MongoDB itself, the dashboard, and the data
# contract are owned by the Dashboard repo (../Dashboard) -- this repo
# depends on it only through MONGO_URI. See `./dev.sh help`.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$HERE/.env"
ENV_EXAMPLE="$HERE/.env.example"
DEV_DIR="$HERE/.dev"
LOG_DIR="$DEV_DIR/logs"
PID_DIR="$DEV_DIR/pids"

CONTENT_SYNC_SCRIPT="$HERE/scripts/content_sync_daemon.py"
CONTENT_SYNC_MIRROR_ID="dev-content-sync"

DASHBOARD_HINT="start it from the Dashboard repo: ../Dashboard/dev.sh up"

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
  export MONGO_URI
}

# -- helpers ------------------------------------------------------------------

mongo_reachable() {
  "$HERE/.venv/bin/python" -c "
import sys
from pymongo import MongoClient
from pymongo.errors import PyMongoError
try:
    MongoClient('$MONGO_URI', serverSelectionTimeoutMS=1500).admin.command('ping')
except PyMongoError:
    sys.exit(1)
" 2>/dev/null
}

require_mongo() {
  mongo_reachable || die "$DASHBOARD_HINT"
}

wait_for_mongo_truthy() {
  # wait_for_mongo_truthy <python-expr-returning-bool> [tries]
  local expr="$1" tries="${2:-60}"
  for _ in $(seq 1 "$tries"); do
    [ "$("$HERE/.venv/bin/python" -c "
from pymongo import MongoClient
client = MongoClient('$MONGO_URI', serverSelectionTimeoutMS=2000)
db = client.get_default_database()
print($expr)
" 2>/dev/null)" = "True" ] && return 0
    sleep 0.5
  done
  return 1
}

ensure_root_venv_extras() {
  if ! "$HERE/.venv/bin/python" -c "import pymongo, qdrant_client, sentence_transformers" >/dev/null 2>&1; then
    log "first run, installing data+assistant extras (pulls in torch -- can take a few minutes)..."
    (cd "$HERE" && uv sync --extra data --extra assistant)
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
  require_mongo
  ensure_root_venv_extras
  mkdir -p "$LOG_DIR" "$PID_DIR"
  (
    cd "$HERE"
    SMARTMIRROR_MIRROR_ID="$CONTENT_SYNC_MIRROR_ID" \
      nohup "$HERE/.venv/bin/python" "$CONTENT_SYNC_SCRIPT" \
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
  echo " Content sync is up -- Mongo: $MONGO_URI"
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
  echo "Mongo ($MONGO_URI):"
  if mongo_reachable; then
    echo "  reachable"
  else
    echo "  NOT reachable -- $DASHBOARD_HINT"
  fi
  echo
  echo "Content sync:"
  if find_pid "$PID_DIR/content-sync.pid" "$(content_sync_pattern)" >/dev/null; then
    echo "  up (pid $(cat "$PID_DIR/content-sync.pid"))"
    if mongo_reachable; then
      "$HERE/.venv/bin/python" -c "
from pymongo import MongoClient
client = MongoClient('$MONGO_URI', serverSelectionTimeoutMS=2000)
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
  mirror_pid="$(pgrep -f 'python.*examples/mvp\.py' | head -1 || true)"
  echo "Mirror app (examples/mvp.py):"
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
  require_mongo
  # examples/mvp.py does its own full Mongo<->Qdrant sync; it can't share
  # Qdrant's embedded storage lock with the standalone content-sync daemon
  # at the same time, so stop that first (`up` brings it back later).
  if find_pid "$PID_DIR/content-sync.pid" "$(content_sync_pattern)" >/dev/null; then
    log "stopping the content-sync daemon first (the mirror app does its own syncing; they can't both hold Qdrant's storage lock)"
    stop_proc "$PID_DIR/content-sync.pid" "$(content_sync_pattern)" "content-sync"
  fi
  cd "$HERE"
  exec uv run python examples/mvp.py
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
  mirror    Run the full camera-driven mirror app (examples/mvp.py) with
            MONGO_URI from .env. Stops the content-sync daemon first (see
            note below); `up` brings it back afterward.
  help      This.

MongoDB itself, the dashboard, and infra/mongo/CONTRACT.md are owned by
the Dashboard repo: https://github.com/SmartGlassCube/Dashboard
Point this repo's .env (MONGO_URI) at whatever Mongo its ./dev.sh up
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
