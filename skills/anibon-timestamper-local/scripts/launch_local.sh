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

# Auto-probe: If endpoint is on 100.115.25.30, test reachability. Fallback to 127.0.0.1 if unreachable.
if [[ "$ENDPOINT" =~ 100\.115\.25\.30 ]]; then
    if ! (timeout 1 bash -c 'cat < /dev/null > /dev/tcp/100.115.25.30/1234' 2>/dev/null || nc -z -w 1 100.115.25.30 1234 2>/dev/null); then
        echo "⚠️ Endpoint 100.115.25.30 is unreachable. Falling back to localhost (127.0.0.1:1234)..."
        ENDPOINT="${ENDPOINT//100.115.25.30/127.0.0.1}"
    fi
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

VIDEO_URL="${6:-}"
if [[ -z "$VIDEO_URL" && -f "${WORKSPACE}/.video_url" ]]; then
    VIDEO_URL="$(cat "${WORKSPACE}/.video_url" 2>/dev/null || true)"
fi
if [[ -z "$VIDEO_URL" && "$WORKSPACE" =~ youtube_([a-zA-Z0-9_-]{11})_workspace ]]; then
    VIDEO_URL="https://www.youtube.com/watch?v=${BASH_REMATCH[1]}"
fi

EXTRA_ARGS=()
if [[ -n "$VIDEO_URL" ]]; then
    EXTRA_ARGS+=(--video-url "$VIDEO_URL")
fi

nohup env PYTHONUNBUFFERED=1 LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 python3 -u -X utf8 "$RUNNER_SCRIPT" "$WORKSPACE" \
    --endpoint "$ENDPOINT" \
    --model "$MODEL" \
    --lang "$LANG" \
    --mode "$MODE" "${EXTRA_ARGS[@]}" > "$LOG_FILE" 2> "$ERR_FILE" &

PID=$!
echo "$PID" > "$PID_FILE"
echo "✅ Timestamper launched in background (PID: $PID)."
echo "   Endpoint    : $ENDPOINT"
echo "   Monitor log : $LOG_FILE"
echo "   State file  : ${WORKSPACE}/anibon_timestamper_state.json"
