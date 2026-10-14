#!/usr/bin/env bash
# One command for the whole dev stack: Mongo + dashboard backend + frontend.
# Idempotent -- safe to run `up` from any state (fresh clone, already up,
# after a crash, after a reboot). See `./dev.sh help`.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$HERE/.env"
ENV_EXAMPLE="$HERE/.env.example"
DEV_DIR="$HERE/.dev"
LOG_DIR="$DEV_DIR/logs"
PID_DIR="$DEV_DIR/pids"

MONGO_DIR="$HERE/infra/mongo"
MONGO_SH="$MONGO_DIR/dev_mongod.sh"
MONGOSH_BIN="$MONGO_DIR/.bin/mongosh/bin/mongosh"

BACKEND_DIR="$HERE/dashboard/backend"
FRONTEND_DIR="$HERE/dashboard/frontend"
BACKEND_PORT=8000
FRONTEND_PORT=5174
BACKEND_BIN="$BACKEND_DIR/.venv/bin/uvicorn"
FRONTEND_BIN="$FRONTEND_DIR/node_modules/.bin/vite"

ADMIN_PASSWORD_JUST_GENERATED=false

log() { echo "dev.sh: $*"; }
die() { echo "dev.sh: ERROR: $*" >&2; exit 1; }

# -- env --------------------------------------------------------------------

gen_secret() { openssl rand -hex 32; }
gen_password() { openssl rand -base64 18 | tr -dc 'A-Za-z0-9' | head -c 20; }

ensure_env_file() {
  if [ -f "$ENV_FILE" ]; then
    return 0
  fi
  log ".env missing -- creating it from .env.example with generated secrets"
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  local jwt_secret admin_password
  jwt_secret="$(gen_secret)"
  admin_password="$(gen_password)"
  sed -i "s|^DASHBOARD_JWT_SECRET=.*|DASHBOARD_JWT_SECRET=$jwt_secret|" "$ENV_FILE"
  sed -i "s|^DASHBOARD_ADMIN_PASSWORD=.*|DASHBOARD_ADMIN_PASSWORD=$admin_password|" "$ENV_FILE"
  ADMIN_PASSWORD_JUST_GENERATED=true
}

load_env() {
  if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
  fi
  MONGO_URI="${MONGO_URI:-mongodb://localhost:27017/ieee?directConnection=true}"
  DASHBOARD_ADMIN_USER="${DASHBOARD_ADMIN_USER:-admin}"
  DASHBOARD_ADMIN_PASSWORD="${DASHBOARD_ADMIN_PASSWORD:-}"
  DASHBOARD_JWT_SECRET="${DASHBOARD_JWT_SECRET:-}"
  export MONGO_URI DASHBOARD_ADMIN_USER DASHBOARD_ADMIN_PASSWORD DASHBOARD_JWT_SECRET
}

# -- small shared helpers ----------------------------------------------------

port_listening() {
  ss -ltn 2>/dev/null | awk '{print $4}' | grep -q ":$1\$"
}

wait_for_http() {
  local url="$1" tries="${2:-60}"
  for _ in $(seq 1 "$tries"); do
    curl -fsS "$url" >/dev/null 2>&1 && return 0
    sleep 0.5
  done
  return 1
}

mongo_is_primary() {
  [ -x "$MONGOSH_BIN" ] || return 1
  "$MONGOSH_BIN" "mongodb://localhost:27017/?directConnection=true" --quiet --eval \
    "quit(db.hello().isWritablePrimary ? 0 : 1)" >/dev/null 2>&1
}

dev_mongosh() {
  [ -x "$MONGOSH_BIN" ] || die "mongosh not found -- run './dev.sh up' first to download it"
  "$MONGOSH_BIN" "$MONGO_URI" "$@"
}

# -- process management (pidfile, self-healing via pgrep if it's stale/missing) --

backend_pattern() { echo "[.]venv/bin/uvicorn app\\.main:app.*--port $BACKEND_PORT"; }
frontend_pattern() { echo "node_modules/[.]bin/vite .*--port $FRONTEND_PORT"; }

find_pid() {
  # find_pid <pidfile> <pgrep-pattern>
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
  # stop_proc <pidfile> <pgrep-pattern> <label>
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

# -- backend / frontend lifecycle -------------------------------------------

ensure_backend_venv() {
  if [ ! -x "$BACKEND_BIN" ]; then
    log "backend: first run, installing deps (uv sync)..."
    (cd "$BACKEND_DIR" && uv sync --extra dev)
  fi
}

ensure_frontend_deps() {
  if [ ! -x "$FRONTEND_BIN" ]; then
    log "frontend: first run, installing deps (npm install)..."
    (cd "$FRONTEND_DIR" && npm install)
  fi
}

start_backend() {
  if find_pid "$PID_DIR/backend.pid" "$(backend_pattern)" >/dev/null; then
    log "backend: already running (pid $(cat "$PID_DIR/backend.pid"))"
    return 0
  fi
  if port_listening "$BACKEND_PORT"; then
    die "port $BACKEND_PORT is already in use by something else (not managed by dev.sh) -- free it or edit BACKEND_PORT in dev.sh"
  fi
  ensure_backend_venv
  mkdir -p "$LOG_DIR" "$PID_DIR"
  (
    cd "$BACKEND_DIR"
    nohup "$BACKEND_BIN" app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" \
      >>"$LOG_DIR/backend.log" 2>&1 &
    echo $! >"$PID_DIR/backend.pid"
  )
  wait_for_http "http://127.0.0.1:$BACKEND_PORT/api/health" \
    || die "backend did not come up -- see $LOG_DIR/backend.log"
  log "backend: up (pid $(cat "$PID_DIR/backend.pid")) -- http://localhost:$BACKEND_PORT"
}

start_frontend() {
  if find_pid "$PID_DIR/frontend.pid" "$(frontend_pattern)" >/dev/null; then
    log "frontend: already running (pid $(cat "$PID_DIR/frontend.pid"))"
    return 0
  fi
  if port_listening "$FRONTEND_PORT"; then
    die "port $FRONTEND_PORT is already in use by something else (not managed by dev.sh) -- free it or edit FRONTEND_PORT in dev.sh"
  fi
  ensure_frontend_deps
  mkdir -p "$LOG_DIR" "$PID_DIR"
  (
    cd "$FRONTEND_DIR"
    VITE_DASHBOARD_API_URL="http://localhost:$BACKEND_PORT" \
      nohup "$FRONTEND_BIN" --port "$FRONTEND_PORT" --strictPort \
      >>"$LOG_DIR/frontend.log" 2>&1 &
    echo $! >"$PID_DIR/frontend.pid"
  )
  wait_for_http "http://localhost:$FRONTEND_PORT/" \
    || die "frontend did not come up -- see $LOG_DIR/frontend.log"
  log "frontend: up (pid $(cat "$PID_DIR/frontend.pid")) -- http://localhost:$FRONTEND_PORT"
}

bootstrap_admin_user() {
  local sync_flag="${1:-}"
  ensure_backend_venv
  (
    cd "$BACKEND_DIR"
    if [ -n "$sync_flag" ]; then
      "$BACKEND_DIR/.venv/bin/python" scripts/bootstrap_admin.py "$DASHBOARD_ADMIN_USER" "$DASHBOARD_ADMIN_PASSWORD" "$sync_flag"
    else
      "$BACKEND_DIR/.venv/bin/python" scripts/bootstrap_admin.py "$DASHBOARD_ADMIN_USER" "$DASHBOARD_ADMIN_PASSWORD"
    fi
  )
}

# -- subcommands --------------------------------------------------------------

cmd_up() {
  local sync_password_flag=""
  for arg in "$@"; do
    [ "$arg" = "--sync-admin-password" ] && sync_password_flag="--sync-password"
  done

  ensure_env_file
  load_env
  mkdir -p "$DEV_DIR" "$LOG_DIR" "$PID_DIR"

  "$MONGO_SH" start
  "$MONGO_SH" init
  "$MONGO_SH" seed-if-empty
  bootstrap_admin_user "$sync_password_flag"
  start_backend
  start_frontend
  print_summary
}

print_summary() {
  echo
  echo "================================================================"
  echo " Smart Mirror dev stack is up"
  echo "================================================================"
  echo " Mongo:     $MONGO_URI"
  echo " Backend:   http://localhost:$BACKEND_PORT  (docs: http://localhost:$BACKEND_PORT/docs)"
  echo " Frontend:  http://localhost:$FRONTEND_PORT"
  echo " Admin:     $DASHBOARD_ADMIN_USER"
  if [ "$ADMIN_PASSWORD_JUST_GENERATED" = "true" ]; then
    echo " Password:  $DASHBOARD_ADMIN_PASSWORD   (generated just now -- shown once; also saved in .env)"
  else
    echo " Password:  see DASHBOARD_ADMIN_PASSWORD in $ENV_FILE"
  fi
  echo " Stop:      ./dev.sh down"
  echo " Status:    ./dev.sh status"
  echo " Logs:      ./dev.sh logs {mongo|backend|frontend}"
  echo "================================================================"
}

cmd_down() {
  load_env
  stop_proc "$PID_DIR/frontend.pid" "$(frontend_pattern)" "frontend"
  stop_proc "$PID_DIR/backend.pid" "$(backend_pattern)" "backend"
  "$MONGO_SH" stop
}

cmd_status() {
  load_env
  echo "Mongo:"
  if mongo_is_primary; then echo "  up (PRIMARY)"; else echo "  down"; fi
  echo
  echo "Backend (:$BACKEND_PORT):"
  if curl -fsS "http://localhost:$BACKEND_PORT/api/health" >/dev/null 2>&1; then echo "  up"; else echo "  down"; fi
  echo
  echo "Frontend (:$FRONTEND_PORT):"
  if curl -fsS "http://localhost:$FRONTEND_PORT/" >/dev/null 2>&1; then echo "  up"; else echo "  down"; fi
  echo
  if mongo_is_primary; then
    echo "Content doc counts:"
    dev_mongosh --quiet --eval '
      ["events","announcements","about","achievements","board","mirror_status"].forEach(c =>
        print("  " + c + ": " + db[c].countDocuments({})))
    '
    echo
    echo "Dashboard users:"
    dev_mongosh --quiet --eval '
      db.dashboard_users.find({}, {username:1, role:1, _id:0}).forEach(u => print("  " + u.username + " (" + u.role + ")"))
    '
  fi
}

cmd_logs() {
  local which="${1:-}"
  case "$which" in
    mongo) tail -f "$MONGO_DIR/.data/mongod.log" ;;
    backend) tail -f "$LOG_DIR/backend.log" ;;
    frontend) tail -f "$LOG_DIR/frontend.log" ;;
    *) die "usage: $0 logs {mongo|backend|frontend}" ;;
  esac
}

cmd_mongosh() {
  load_env
  dev_mongosh "$@"
}

cmd_reset_password() {
  local user="${1:-}"
  [ -n "$user" ] || die "usage: $0 reset-password <user> [password]"
  local pass="${2:-}"
  local generated=false
  if [ -z "$pass" ]; then
    pass="$(gen_password)"
    generated=true
  fi
  ensure_backend_venv
  (cd "$BACKEND_DIR" && "$BACKEND_DIR/.venv/bin/python" scripts/set_password.py "$user" "$pass")
  if [ "$generated" = "true" ]; then
    echo "generated password for '$user': $pass"
    echo "(shown once -- store it now)"
  else
    echo "password set for '$user'"
  fi
}

cmd_reseed() {
  local yes=false
  for arg in "$@"; do
    [ "$arg" = "--yes" ] && yes=true
  done
  if [ "$yes" != "true" ]; then
    read -r -p "This wipes events/announcements/about/achievements/board and reseeds dev data. Continue? [y/N] " reply
    case "$reply" in
      y|Y|yes|YES) ;;
      *) echo "aborted"; return 1 ;;
    esac
  fi
  "$MONGO_SH" seed
}

cmd_mirror() {
  load_env
  cd "$HERE"
  exec uv run python examples/mvp.py
}

cmd_install_autostart() {
  local unit_dir="$HOME/.config/systemd/user"
  local unit_file="$unit_dir/smartmirror-mongo.service"
  mkdir -p "$unit_dir"
  cat >"$unit_file" <<EOF
[Unit]
Description=Smart Mirror dev MongoDB (user-level, no sudo)
After=default.target

[Service]
Type=forking
ExecStart=$MONGO_SH start
ExecStop=$MONGO_SH stop
PIDFile=$MONGO_DIR/.data/mongod.pid
Restart=on-failure

[Install]
WantedBy=default.target
EOF
  systemctl --user daemon-reload
  log "installed $unit_file"
  echo "Not enabled or started (your call). To do that yourself:"
  echo "  systemctl --user enable --now smartmirror-mongo.service"
  echo "To have it start even without an active login session:"
  echo "  loginctl enable-linger \$USER   # may need sudo on some systems"
}

cmd_uninstall_autostart() {
  local unit_file="$HOME/.config/systemd/user/smartmirror-mongo.service"
  systemctl --user disable --now smartmirror-mongo.service 2>/dev/null || true
  rm -f "$unit_file"
  systemctl --user daemon-reload 2>/dev/null || true
  log "removed $unit_file"
}

cmd_help() {
  cat <<'EOF'
Usage: ./dev.sh <command> [args]

  up [--sync-admin-password]   Start Mongo + dashboard backend + frontend.
                                Idempotent: reuses whatever's already running.
                                First run creates .env with generated secrets.
                                --sync-admin-password resets the configured
                                admin's password to match .env even if the
                                user already existed.
  down                          Stop frontend, backend, and Mongo.
  status                        Up/down + PRIMARY? + doc counts + user list.
  logs {mongo|backend|frontend} Tail that component's log.
  mongosh [args]                Run the bundled mongosh against MONGO_URI.
  reset-password <user> [pw]    Set/overwrite a password (creates as admin
                                 if the user doesn't exist). Omit the
                                 password to get one generated and printed.
  reseed [--yes]                DESTRUCTIVE: wipe + reseed dev content.
                                 Asks for confirmation unless --yes.
  mirror                        Run examples/mvp.py with MONGO_URI from .env.
  install-autostart              Install (but do not enable) a systemd
                                 --user unit that runs Mongo at login.
  uninstall-autostart             Remove it.
  help                           This.
EOF
}

main() {
  local cmd="${1:-help}"
  [ $# -gt 0 ] && shift || true
  case "$cmd" in
    up) cmd_up "$@" ;;
    down) cmd_down ;;
    status) cmd_status ;;
    logs) cmd_logs "$@" ;;
    mongosh) cmd_mongosh "$@" ;;
    reset-password) cmd_reset_password "$@" ;;
    reseed) cmd_reseed "$@" ;;
    mirror) cmd_mirror ;;
    install-autostart) cmd_install_autostart ;;
    uninstall-autostart) cmd_uninstall_autostart ;;
    help|-h|--help) cmd_help ;;
    *) echo "unknown command: $cmd" >&2; cmd_help; exit 1 ;;
  esac
}

main "$@"
