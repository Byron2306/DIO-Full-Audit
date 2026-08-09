#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/byron/Integritas-Mechanicus"
ARDA_ROOT="$ROOT/arda_os"
METATRON_ROOT="${ARDA_UNIFIED_AGENT_ROOT:-/home/byron/Downloads/Metatron-triune-outbound-gate}"
PYTHON_BIN="${PYTHON_BIN:-$ROOT/.venv/bin/python}"
LOCAL_DATA_ROOT="$ROOT/evidence/mandos"
EXTERNAL_DATA_ROOT="$METATRON_ROOT/evidence/mandos"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

if [[ -d "$METATRON_ROOT/unified_agent" ]]; then
  export PYTHONPATH="$ARDA_ROOT:$METATRON_ROOT${PYTHONPATH:+:$PYTHONPATH}"
else
  export PYTHONPATH="$ARDA_ROOT${PYTHONPATH:+:$PYTHONPATH}"
fi

if [[ -z "${ARDA_DATA_DIR:-}" ]]; then
  if [[ -d "$LOCAL_DATA_ROOT" ]]; then
    export ARDA_DATA_DIR="$LOCAL_DATA_ROOT"
  else
    export ARDA_DATA_DIR="$EXTERNAL_DATA_ROOT"
  fi
fi
export PRESENCE_PORT="${PRESENCE_PORT:-7070}"
export OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:3b}"
export OLLAMA_FAST_MODEL="${OLLAMA_FAST_MODEL:-qwen2.5:0.5b}"
# This desktop launcher is unprivileged. An explicit value of 1 still selects
# the production fail-closed BPF/LSM path when invoked by an authorized host.
export ARDA_SOVEREIGN_MODE="${ARDA_SOVEREIGN_MODE:-0}"

exec "$PYTHON_BIN" "$ARDA_ROOT/backend/services/presence_server.py"
