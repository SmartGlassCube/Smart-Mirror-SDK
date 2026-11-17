#!/usr/bin/env bash
#
# Process-level supervisor for the mirror app (python -m glasscube).
#
# A segfault in a native library (whisper.cpp, mediapipe/XNNPACK,
# PortAudio/ALSA -- all running concurrently under asyncio here) kills the
# whole Python process outright. No in-process try/except can catch that --
# see SmartMirrorServer.run() (glasscube/server/app.py) and
# Assistant.listen_loop for what *is* catchable (ordinary exceptions).
# This script is the mitigation for the rest: restart on any non-zero
# exit, segfault included, and log every restart with a timestamp and exit
# code so a crash is visible instead of just leaving the mirror dead.
#
# For a permanent Pi deployment, prefer a systemd unit with
# `Restart=on-failure` over this script -- it's the standard tool for the
# job and integrates with `journalctl`. This is the quick/portable option
# for dev, bring-up, or anywhere systemd isn't available.
#
# Usage: scripts/run_supervised.sh   (from backend/)
# Log:   mirror_supervisor.log (override with GLASSCUBE_SUPERVISOR_LOG)

set -u
cd "$(dirname "$0")/.."

LOG_FILE="${GLASSCUBE_SUPERVISOR_LOG:-mirror_supervisor.log}"
MAX_RESTARTS_PER_MIN=6
restart_times=()

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

while true; do
    log "Starting the mirror app"
    python3 -m glasscube
    exit_code=$?

    if [ "$exit_code" -eq 0 ]; then
        log "the mirror app exited cleanly (0) -- not restarting"
        break
    elif [ "$exit_code" -eq 139 ]; then
        log "the mirror app SEGFAULTED (exit 139) -- restarting"
    else
        log "the mirror app exited with code $exit_code -- restarting"
    fi

    now=$(date +%s)
    restart_times+=("$now")
    cutoff=$((now - 60))
    kept=()
    for t in "${restart_times[@]}"; do
        [ "$t" -ge "$cutoff" ] && kept+=("$t")
    done
    restart_times=("${kept[@]}")

    if [ "${#restart_times[@]}" -gt "$MAX_RESTARTS_PER_MIN" ]; then
        log "More than $MAX_RESTARTS_PER_MIN restarts in the last minute -- giving up, this needs investigation, not another restart"
        exit 1
    fi

    sleep 2
done
