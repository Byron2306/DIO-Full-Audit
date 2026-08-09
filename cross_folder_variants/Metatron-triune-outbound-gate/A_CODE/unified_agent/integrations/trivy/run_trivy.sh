#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-status}" # status | fs | image | repo | config
TARGET="${2:-.}"

if ! command -v trivy >/dev/null 2>&1; then
  echo '{"success":false,"error":"trivy_not_installed"}'
  exit 1
fi

if [[ "$MODE" == "status" ]]; then
  VERSION="$(trivy --version 2>/dev/null | tr '\n' ' ' || true)"
  printf '{"success":true,"mode":"status","version":"%s"}\n' "${VERSION//\"/\\\"}"
  exit 0
fi

if [[ "$MODE" != "fs" && "$MODE" != "image" && "$MODE" != "repo" && "$MODE" != "config" ]]; then
  echo '{"success":false,"error":"unsupported_mode"}'
  exit 2
fi

exec trivy "$MODE" --severity HIGH,CRITICAL --no-progress "$TARGET"
