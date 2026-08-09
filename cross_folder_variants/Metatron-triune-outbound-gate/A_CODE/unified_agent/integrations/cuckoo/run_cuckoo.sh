#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-status}" # status | submit_file | task_status | report
CUCKOO_API_URL="${CUCKOO_API_URL:-}"
CUCKOO_API_TOKEN="${CUCKOO_API_TOKEN:-}"
ARG="${2:-}"

if [[ -z "$CUCKOO_API_URL" ]]; then
  echo '{"success":false,"error":"cuckoo_api_url_not_configured"}'
  exit 1
fi

HEADER=()
if [[ -n "$CUCKOO_API_TOKEN" ]]; then
  HEADER=(-H "Authorization: Bearer $CUCKOO_API_TOKEN")
fi

if ! command -v curl >/dev/null 2>&1; then
  echo '{"success":false,"error":"curl_not_installed"}'
  exit 1
fi

case "$ACTION" in
  status)
    exec curl -fsS "${HEADER[@]}" "$CUCKOO_API_URL/cuckoo/status"
    ;;
  submit_file)
    if [[ -z "$ARG" || ! -f "$ARG" ]]; then
      echo '{"success":false,"error":"valid_file_path_required"}'
      exit 1
    fi
    exec curl -fsS "${HEADER[@]}" -F "file=@$ARG" "$CUCKOO_API_URL/tasks/create/file"
    ;;
  task_status)
    if [[ -z "$ARG" ]]; then
      echo '{"success":false,"error":"task_id_required"}'
      exit 1
    fi
    exec curl -fsS "${HEADER[@]}" "$CUCKOO_API_URL/tasks/view/$ARG"
    ;;
  report)
    if [[ -z "$ARG" ]]; then
      echo '{"success":false,"error":"task_id_required"}'
      exit 1
    fi
    exec curl -fsS "${HEADER[@]}" "$CUCKOO_API_URL/tasks/report/$ARG"
    ;;
  *)
    echo '{"success":false,"error":"unsupported_action"}'
    exit 2
    ;;
esac
