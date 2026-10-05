#!/usr/bin/env bash
#
# Process-level supervisor for examples/mvp.py.
#
# A segfault in a native library (whisper.cpp, mediapipe/XNNPACK,
# PortAudio/ALSA -- all running concurrently under asyncio here) kills the
# whole Python process outright. No in-process try/except can catch that --
# see the hardening notes in smartmirror/smartmirror.py's run() and
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
# Usage: scripts/run_mvp_supervised.sh
# Log:   mvp_supervisor.log (override with SMARTMIRROR_SUPERVISOR_LOG)

set -u
cd "$(dirname "$0")/.."

LOG_FILE="${SMARTMIRROR_SUPERVISOR_LOG:-mvp_supervisor.log}"
MAX_RESTARTS_PER_MIN=6
restart_times=()

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

while true; do
    log "Starting examples/mvp.py"
    python3 examples/mvp.py
    exit_code=$?

    if [ "$exit_code" -eq 0 ]; then
        log "examples/mvp.py exited cleanly (0) -- not restarting"
        break
    elif [ "$exit_code" -eq 139 ]; then
        log "examples/mvp.py SEGFAULTED (exit 139) -- restarting"
    else
        log "examples/mvp.py exited with code $exit_code -- restarting"
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
