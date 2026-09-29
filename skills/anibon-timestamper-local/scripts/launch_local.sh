#!/usr/bin/env bash
# launch_local.sh — Detached runner for process_chunks_local.py
set -euo pipefail

usage() {
    echo "Usage: $0 <WORKSPACE> [ENDPOINT_OR_IP] [MODEL] [LANG] [MODE]"
    echo "  ENDPOINT_OR_IP: Full URL or IP address (default: 100.115.25.30)"
    echo "  MODEL: Model identifier (default: auto)"
    echo "  LANG: Output language th|en (default: th)"
    echo "  MODE: recursive|group (default: recursive)"
    exit 1
}

if [[ $# -lt 1 ]]; then
    usage
fi

WORKSPACE="$1"
ENDPOINT="${2:-100.115.25.30}"
MODEL="${3:-auto}"
LANG="${4:-th}"
MODE="${5:-recursive}"

if [[ ! -d "$WORKSPACE" ]]; then
    echo "Error: Workspace directory does not exist: $WORKSPACE" >&2
    exit 1
fi

if [[ ! "$ENDPOINT" =~ ^https?:// ]]; then
    ENDPOINT="http://${ENDPOINT}:1234/v1/chat/completions"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER_SCRIPT="${SCRIPT_DIR}/process_chunks_local.py"
LOG_FILE="${WORKSPACE}/timestamper.log"
ERR_FILE="${WORKSPACE}/timestamper_err.log"
PID_FILE="${WORKSPACE}/timestamper.pid"

if [[ -f "$PID_FILE" ]]; then
    EXISTING_PID=$(cat "$PID_FILE" 2>/dev/null || echo "")
    if [[ -n "$EXISTING_PID" ]] && kill -0 "$EXISTING_PID" 2>/dev/null; then
        echo "⚠️ Timestamper is already running for this workspace (PID: $EXISTING_PID)."
        echo "   To stop it first: kill $EXISTING_PID"
        exit 0
    fi
fi

nohup env PYTHONUNBUFFERED=1 LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 python3 -u -X utf8 "$RUNNER_SCRIPT" "$WORKSPACE" \
    --endpoint "$ENDPOINT" \
    --model "$MODEL" \
    --lang "$LANG" \
    --mode "$MODE" > "$LOG_FILE" 2> "$ERR_FILE" &

PID=$!
echo "$PID" > "$PID_FILE"
echo "✅ Timestamper launched in background (PID: $PID)."
echo "   Endpoint    : $ENDPOINT"
echo "   Monitor log : $LOG_FILE"
echo "   State file  : ${WORKSPACE}/anibon_timestamper_state.json"
