#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-status}" # status | scan
RULES_PATH="${2:-/workspace/yara_rules}"
TARGET_PATH="${3:-/tmp}"

if ! command -v yara >/dev/null 2>&1; then
  echo '{"success":false,"error":"yara_not_installed"}'
  exit 1
fi

case "$ACTION" in
  status)
    VERSION="$(yara --version 2>/dev/null || true)"
    printf '{"success":true,"mode":"status","version":"%s"}\n' "${VERSION//\"/\\\"}"
    ;;
  scan)
    exec yara -r "$RULES_PATH" "$TARGET_PATH"
    ;;
  *)
    echo '{"success":false,"error":"unsupported_action"}'
    exit 2
    ;;
esac
