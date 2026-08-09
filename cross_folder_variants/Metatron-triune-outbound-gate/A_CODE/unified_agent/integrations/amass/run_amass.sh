#!/usr/bin/env bash
# Amass Integration – Seraph AI Defense
# Usage: run_amass.sh [domain] [output_file]
set -euo pipefail

DOMAIN="${1:-}"
OUTPUT_FILE="${2:-}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
DOCKER_BIN=$(command -v docker 2>/dev/null || echo "")
AMASS_IMAGE="caffix/amass:latest"

if [ -z "$DOMAIN" ]; then
    echo '{"success":false,"error":"domain_required"}'
    exit 1
fi

# Try native amass binary first
AMASS_BIN=$(command -v amass 2>/dev/null || echo "")

run_amass() {
    local domain="$1"
    if [ -n "$AMASS_BIN" ]; then
        "$AMASS_BIN" enum -passive -d "$domain" -json /dev/stdout 2>/dev/null || true
    elif [ -n "$DOCKER_BIN" ]; then
        "$DOCKER_BIN" run --rm "$AMASS_IMAGE" enum -passive -d "$domain" -json /dev/stdout 2>/dev/null || true
    else
        echo ""
    fi
}

RESULT_RAW=$(run_amass "$DOMAIN")
RESULT_COUNT=$(echo "$RESULT_RAW" | grep -c '"name"' 2>/dev/null || echo 0)

OUTPUT=$(python3 - <<PYEOF
import json, sys

raw = """$RESULT_RAW"""
entries = []
for line in raw.strip().splitlines():
    line = line.strip()
    if not line:
        continue
    try:
        obj = json.loads(line)
        entries.append(obj)
    except json.JSONDecodeError:
        if line:
            entries.append({"name": line})

result = {
    "success": True,
    "domain": "$DOMAIN",
    "timestamp": "$TIMESTAMP",
    "findings_count": len(entries),
    "findings": entries[:200]  # cap at 200
}
print(json.dumps(result))
PYEOF
)

if [ -n "$OUTPUT_FILE" ]; then
    echo "$OUTPUT" > "$OUTPUT_FILE"
    echo "Results written to $OUTPUT_FILE"
else
    echo "$OUTPUT"
fi
