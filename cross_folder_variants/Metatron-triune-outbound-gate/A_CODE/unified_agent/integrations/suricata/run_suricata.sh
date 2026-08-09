#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-status}"
LIMIT="${2:-100}"
EVE_PATH="${SURICATA_EVE_PATH:-/var/log/suricata/eve.json}"

if ! command -v suricata >/dev/null 2>&1; then
  echo '{"success":false,"error":"suricata_not_installed"}'
  exit 1
fi

case "$ACTION" in
  status)
    VERSION="$(suricata -V 2>/dev/null | head -n 1 || true)"
    EXISTS=false
    if [[ -f "$EVE_PATH" ]]; then
      EXISTS=true
    fi
    printf '{"success":true,"mode":"status","version":"%s","eve_exists":%s}\n' "${VERSION//\"/\\\"}" "$EXISTS"
    ;;
  alerts)
    if [[ ! -f "$EVE_PATH" ]]; then
      echo '{"success":false,"error":"eve_file_missing"}'
      exit 1
    fi
    tail -n "$LIMIT" "$EVE_PATH"
    ;;
  *)
    echo '{"success":false,"error":"unsupported_action"}'
    exit 2
    ;;
esac
