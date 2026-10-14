#!/usr/bin/env bash
# Dev-only local MongoDB, no docker/sudo required.
# Fallback for when the `docker` group isn't set up on this machine yet
# (see "NEEDS YOU" in OVERNIGHT_REPORT.md for the real fix).
#
# Downloads the mongod/mongosh tarballs into .bin/ (gitignored) on first use
# if they're missing -- nothing to install system-wide, no sudo.
#
# Usage: ./dev_mongod.sh {start|stop|status|init|seed|seed-if-empty}
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HERE/.bin"
DATA="$HERE/.data"
MONGOD="$BIN/mongodb/bin/mongod"
MONGOSH="$BIN/mongosh/bin/mongosh"
PIDFILE="$DATA/mongod.pid"
LOGFILE="$DATA/mongod.log"
URI="mongodb://localhost:27017/?directConnection=true"
CONTENT_URI="mongodb://localhost:27017/ieee?directConnection=true"
CONTENT_COLLECTIONS=(events announcements about achievements board)

log() { echo "mongo: $*"; }
die() { echo "mongo: ERROR: $*" >&2; exit 1; }

port_in_use() {
  ss -ltn 2>/dev/null | awk '{print $4}' | grep -q ":$1\$"
}

is_running() {
  cleanup_stale_pid
  [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null
}

cleanup_stale_pid() {
  if [ -f "$PIDFILE" ] && ! kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
    log "removing stale pidfile (process no longer running)"
    rm -f "$PIDFILE"
  fi
}

ensure_binaries() {
  if [ -x "$MONGOD" ] && [ -x "$MONGOSH" ]; then
    return 0
  fi
  log "binaries not found in $BIN, downloading (one-time, needs network)..."
  mkdir -p "$BIN"
  local tmp
  tmp="$(mktemp -d)"
  # shellcheck disable=SC2064
  trap "rm -rf '$tmp'" RETURN

  local mongod_url mongosh_url
  mongod_url="$(python3 - <<'PY'
import json, urllib.request
data = json.load(urllib.request.urlopen("https://downloads.mongodb.org/current.json", timeout=20))
for v in data["versions"]:
    if not v["version"].startswith("7.0"):
        continue
    for dl in v["downloads"]:
        if dl.get("edition") == "targeted" and dl.get("target") == "ubuntu2204" and dl.get("arch") == "x86_64":
            print(dl["archive"]["url"])
PY
  )" || true
  mongosh_url="$(python3 - <<'PY'
import json, urllib.request
data = json.load(urllib.request.urlopen("https://downloads.mongodb.com/compass/mongosh.json", timeout=20))
v = data["versions"][0]
for dl in v["downloads"]:
    url = dl.get("archive", {}).get("url", "")
    if dl.get("distro") == "linux" and dl.get("arch") == "x86_64" and "openssl" not in url:
        print(url)
        break
PY
  )" || true

  [ -n "$mongod_url" ] || die "could not resolve a mongod download URL (network down?)"
  [ -n "$mongosh_url" ] || die "could not resolve a mongosh download URL (network down?)"

  log "downloading mongod: $mongod_url"
  curl -sS -o "$tmp/mongodb.tgz" "$mongod_url"
  log "downloading mongosh: $mongosh_url"
  curl -sS -o "$tmp/mongosh.tgz" "$mongosh_url"

  tar xzf "$tmp/mongodb.tgz" -C "$BIN"
  tar xzf "$tmp/mongosh.tgz" -C "$BIN"
  ln -sfn "$(basename "$(find "$BIN" -maxdepth 1 -name 'mongodb-linux-*' -type d | head -1)")" "$BIN/mongodb"
  ln -sfn "$(basename "$(find "$BIN" -maxdepth 1 -name 'mongosh-*' -type d | head -1)")" "$BIN/mongosh"
  [ -x "$MONGOD" ] && [ -x "$MONGOSH" ] || die "download/extract didn't produce usable binaries"
  log "binaries ready"
}

wait_for_ping() {
  for _ in $(seq 1 60); do
    "$MONGOSH" "$URI" --quiet --eval "db.runCommand({ping:1})" >/dev/null 2>&1 && return 0
    # If the process died outright, don't wait out the full timeout.
    if [ -f "$PIDFILE" ] && ! kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
      return 1
    fi
    sleep 0.5
  done
  return 1
}

start() {
  if is_running; then
    log "already running (pid $(cat "$PIDFILE"))"
    return 0
  fi
  if port_in_use 27017; then
    die "port 27017 is already in use by something else (not this script's mongod). Check with: ss -ltnp | grep 27017"
  fi
  ensure_binaries
  mkdir -p "$DATA"
  "$MONGOD" --replSet rs0 --dbpath "$DATA" --port 27017 --bind_ip 127.0.0.1 \
    --fork --logpath "$LOGFILE" --pidfilepath "$PIDFILE"
  log "waiting for mongod to accept connections..."
  wait_for_ping || die "mongod did not come up -- see $LOGFILE"
  init_replset
  log "started (pid $(cat "$PIDFILE"))"
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
    log "stopped"
  else
    cleanup_stale_pid
    log "not running"
  fi
}

status() {
  if is_running; then
    log "running (pid $(cat "$PIDFILE"))"
    "$MONGOSH" "$URI" --quiet --eval "rs.status().myState" 2>&1 || true
  else
    log "not running"
  fi
}

init_db() {
  "$MONGOSH" "$URI" "$HERE/init_db.js"
}

seed() {
  "$MONGOSH" "$URI" "$HERE/seed.js"
}

content_doc_count() {
  local filter
  filter="$(printf '"%s",' "${CONTENT_COLLECTIONS[@]}")"
  "$MONGOSH" "$CONTENT_URI" --quiet --eval "print([${filter}].reduce((s,c)=>s+db[c].countDocuments({}),0))"
}

seed_if_empty() {
  local count
  count="$(content_doc_count)"
  if [ "$count" = "0" ]; then
    log "content collections are empty, seeding dev data"
    seed
  else
    log "content collections already have $count doc(s) total, not reseeding"
  fi
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  status) status ;;
  init) init_db ;;
  seed) seed ;;
  seed-if-empty) seed_if_empty ;;
  *) echo "usage: $0 {start|stop|status|init|seed|seed-if-empty}"; exit 1 ;;
esac
