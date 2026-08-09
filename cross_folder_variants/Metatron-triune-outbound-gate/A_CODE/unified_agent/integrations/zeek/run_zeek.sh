#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-status}" # status | logs
LOG_TYPE="${2:-conn}"
LIMIT="${3:-100}"
LOG_DIR="${ZEEK_LOG_DIR:-/var/log/zeek/current}"

if [[ "$ACTION" == "status" ]]; then
  if command -v zeek >/dev/null 2>&1; then
    VERSION="$(zeek --version 2>/dev/null | head -n 1 || true)"
    HAS_BIN=true
  else
    VERSION=""
    HAS_BIN=false
  fi
  HAS_LOGS=false
  if [[ -d "$LOG_DIR" ]]; then
    HAS_LOGS=true
  fi
  printf '{"success":true,"mode":"status","zeek_binary":%s,"version":"%s","log_dir":"%s","log_dir_exists":%s}\n' "$HAS_BIN" "${VERSION//\"/\\\"}" "$LOG_DIR" "$HAS_LOGS"
  exit 0
fi

if [[ "$ACTION" == "logs" ]]; then
  FILE="$LOG_DIR/$LOG_TYPE.log"
  if [[ ! -f "$FILE" ]]; then
    echo '{"success":false,"error":"log_file_missing"}'
    exit 1
  fi
  tail -n "$LIMIT" "$FILE"
  exit 0
fi

echo '{"success":false,"error":"unsupported_action"}'
exit 2
