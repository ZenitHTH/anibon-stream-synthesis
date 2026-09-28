#!/usr/bin/env zsh
# launch_local.zsh — Detached runner for process_chunks_local.py (Zsh)
set -e

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

SCRIPT_DIR="${0:A:h}"
RUNNER_SCRIPT="${SCRIPT_DIR}/process_chunks_local.py"
LOG_FILE="${WORKSPACE}/timestamper.log"
ERR_FILE="${WORKSPACE}/timestamper_err.log"

nohup python3 -X utf8 "$RUNNER_SCRIPT" "$WORKSPACE" \
    --endpoint "$ENDPOINT" \
    --model "$MODEL" \
    --lang "$LANG" \
    --mode "$MODE" > "$LOG_FILE" 2> "$ERR_FILE" &!

PID=$!
echo "✅ Timestamper launched in background (PID: $PID)."
echo "   Endpoint    : $ENDPOINT"
echo "   Monitor log : $LOG_FILE"
echo "   State file  : ${WORKSPACE}/anibon_timestamper_state.json"
