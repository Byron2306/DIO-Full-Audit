#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-status}" # status | live_query
SQL="${2:-select name, pid from processes limit 10;}"

if command -v osqueryi >/dev/null 2>&1; then
  BIN="osqueryi"
elif command -v osqueryd >/dev/null 2>&1; then
  BIN="osqueryd"
else
  echo '{"success":false,"error":"osquery_not_installed"}'
  exit 1
fi

case "$ACTION" in
  status)
    VERSION="$($BIN --version 2>/dev/null || true)"
    printf '{"success":true,"mode":"status","binary":"%s","version":"%s"}\n' "$BIN" "${VERSION//\"/\\\"}"
    ;;
  live_query)
    if [[ "$BIN" != "osqueryi" ]]; then
      echo '{"success":false,"error":"osqueryi_required_for_live_query"}'
      exit 1
    fi
    exec osqueryi --json "$SQL"
    ;;
  *)
    echo '{"success":false,"error":"unsupported_action"}'
    exit 2
    ;;
esac
