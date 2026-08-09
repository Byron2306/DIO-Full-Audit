#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-status}"
LIMIT="${2:-100}"

if ! command -v falco >/dev/null 2>&1; then
  echo '{"success":false,"error":"falco_not_installed"}'
  exit 1
fi

case "$ACTION" in
  status)
    VERSION="$(falco --version 2>/dev/null | head -n 1 || true)"
    if pgrep -f falco >/dev/null 2>&1; then
      RUNNING=true
    else
      RUNNING=false
    fi
    printf '{"success":true,"mode":"status","version":"%s","running":%s}\n' "${VERSION//\"/\\\"}" "$RUNNING"
    ;;
  alerts)
    ALERT_FILE="${FALCO_ALERTS_PATH:-/var/log/falco/falco_alerts.json}"
    if [[ ! -f "$ALERT_FILE" ]]; then
      echo '{"success":false,"error":"falco_alert_file_missing"}'
      exit 1
    fi
    tail -n "$LIMIT" "$ALERT_FILE"
    ;;
  *)
    echo '{"success":false,"error":"unsupported_action"}'
    exit 2
    ;;
esac
