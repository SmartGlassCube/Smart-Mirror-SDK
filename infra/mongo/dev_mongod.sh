#!/usr/bin/env bash
# Dev-only local MongoDB, no docker/sudo required.
# Fallback for when the `docker` group isn't set up on this machine yet
# (see "NEEDS YOU" in OVERNIGHT_REPORT.md for the real fix).
#
# Downloads nothing itself -- expects infra/mongo/.bin/mongodb and
# infra/mongo/.bin/mongosh (symlinks to extracted tarballs) to already exist.
#
# Usage: ./dev_mongod.sh start|stop|status|init
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HERE/.bin"
DATA="$HERE/.data"
MONGOD="$BIN/mongodb/bin/mongod"
MONGOSH="$BIN/mongosh/bin/mongosh"
PIDFILE="$DATA/mongod.pid"
LOGFILE="$DATA/mongod.log"
URI="mongodb://localhost:27017/?directConnection=true"

start() {
  if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "already running (pid $(cat "$PIDFILE"))"
    return 0
  fi
  mkdir -p "$DATA"
  "$MONGOD" --replSet rs0 --dbpath "$DATA" --port 27017 --bind_ip 127.0.0.1 \
    --fork --logpath "$LOGFILE" --pidfilepath "$PIDFILE"
  echo "waiting for mongod to accept connections..."
  for _ in $(seq 1 30); do
    if "$MONGOSH" "$URI" --quiet --eval "db.runCommand({ping:1})" >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done
  init_replset
  echo "started (pid $(cat "$PIDFILE"))"
}

init_replset() {
  "$MONGOSH" "$URI" --quiet --eval '
    try {
      rs.status();
    } catch (e) {
      rs.initiate({_id: "rs0", members: [{_id: 0, host: "localhost:27017"}]});
      while (!db.hello().isWritablePrimary) { sleep(200); }
    }
  '
}

stop() {
  if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    kill "$(cat "$PIDFILE")"
    for _ in $(seq 1 30); do
      kill -0 "$(cat "$PIDFILE")" 2>/dev/null || break
      sleep 0.5
    done
    rm -f "$PIDFILE"
    echo "stopped"
  else
    echo "not running"
  fi
}

status() {
  if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "running (pid $(cat "$PIDFILE"))"
    "$MONGOSH" "$URI" --quiet --eval "rs.status().myState" 2>&1 || true
  else
    echo "not running"
  fi
}

init_db() {
  "$MONGOSH" "$URI" "$HERE/init_db.js"
}

seed() {
  "$MONGOSH" "$URI" "$HERE/seed.js"
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  status) status ;;
  init) init_db ;;
  seed) seed ;;
  *) echo "usage: $0 {start|stop|status|init|seed}"; exit 1 ;;
esac
