#!/usr/bin/env bash
# SpiderFoot Integration – Seraph AI Defense
# Usage: run_spiderfoot.sh [action] [target] [output_file]
# action: status | scan
set -euo pipefail

ACTION="${1:-status}"
TARGET="${2:-}"
OUTPUT_FILE="${3:-}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
DOCKER_BIN=$(command -v docker 2>/dev/null || echo "")
SF_IMAGE="spiderfoot/spiderfoot:latest"
SF_PORT="${SPIDERFOOT_PORT:-5009}"

case "$ACTION" in
  status)
    RUNNING="false"
    if [ -n "$DOCKER_BIN" ]; then
      CONTAINERS=$("$DOCKER_BIN" ps --filter "ancestor=$SF_IMAGE" --format "{{.Names}}" 2>/dev/null || echo "")
      if [ -n "$CONTAINERS" ]; then
        RUNNING="true"
      fi
    fi
    printf '{"success":true,"action":"status","running":%s,"docker_available":%s,"image":"%s"}\n' \
      "$RUNNING" "$( [ -n "$DOCKER_BIN" ] && echo true || echo false )" "$SF_IMAGE"
    ;;
  scan)
    if [ -z "$TARGET" ]; then
      echo '{"success":false,"error":"target_required"}'
      exit 1
    fi
    if [ -z "$DOCKER_BIN" ]; then
      echo '{"success":false,"error":"docker_not_available"}'
      exit 1
    fi
    RESULT_DIR=$(mktemp -d)
    "$DOCKER_BIN" run --rm \
      -v "$RESULT_DIR:/tmp/sf-output" \
      "$SF_IMAGE" \
      -s "$TARGET" -t "INTERNET_NAME,IP_ADDRESS,DOMAIN_NAME" \
      -o json -f "$RESULT_DIR/results.json" 2>/dev/null || true
    if [ -f "$RESULT_DIR/results.json" ]; then
      RESULT=$(cat "$RESULT_DIR/results.json")
    else
      RESULT='[]'
    fi
    OUTPUT="{\"success\":true,\"action\":\"scan\",\"target\":\"$TARGET\",\"timestamp\":\"$TIMESTAMP\",\"results\":$RESULT}"
    rm -rf "$RESULT_DIR"
    if [ -n "$OUTPUT_FILE" ]; then
      echo "$OUTPUT" > "$OUTPUT_FILE"
    else
      echo "$OUTPUT"
    fi
    ;;
  *)
    echo '{"success":false,"error":"unsupported_action"}'
    exit 1
    ;;
esac
