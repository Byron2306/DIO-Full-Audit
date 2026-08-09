#!/usr/bin/env bash
# ClamAV Integration – Seraph AI Defense
# Usage: run_clamav.sh [scan_path] [output_file]
# Outputs JSON to stdout or output_file

set -euo pipefail

SCAN_PATH="${1:-/tmp}"
OUTPUT_FILE="${2:-}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

json_escape() {
    printf '%s' "$1" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo '"'"$1"'"'
}

run_scan() {
    if command -v clamscan >/dev/null 2>&1; then
        CLAM_BIN="clamscan"
    elif command -v clamdscan >/dev/null 2>&1; then
        CLAM_BIN="clamdscan"
    else
        # Try docker-based ClamAV
        if command -v docker >/dev/null 2>&1; then
            RESULT=$(docker run --rm -v "${SCAN_PATH}:/scandir:ro" clamav/clamav:stable \
                clamscan --recursive --infected --no-summary /scandir 2>&1 || true)
            echo "$RESULT"
            return
        fi
        echo "ERROR: clamscan not found. Install clamav or start the clamav docker service."
        exit 1
    fi

    # Update virus definitions if freshclam is available
    if command -v freshclam >/dev/null 2>&1; then
        freshclam --quiet 2>/dev/null || true
    fi

    "$CLAM_BIN" --recursive --infected --no-summary "$SCAN_PATH" 2>&1 || true
}

SCAN_OUTPUT=$(run_scan)
INFECTED_COUNT=$(echo "$SCAN_OUTPUT" | grep -c "FOUND" 2>/dev/null || echo 0)
INFECTED_FILES=$(echo "$SCAN_OUTPUT" | grep "FOUND" 2>/dev/null | head -50 || echo "")

# Build JSON result
RESULT=$(python3 - <<PYEOF
import json, sys

output = """$SCAN_OUTPUT"""
infected_files = [l.strip() for l in """$INFECTED_FILES""".strip().splitlines() if l.strip()]
result = {
    "tool": "clamav",
    "timestamp": "$TIMESTAMP",
    "scan_path": "$SCAN_PATH",
    "infected_count": $INFECTED_COUNT,
    "infected_files": infected_files,
    "clean": $INFECTED_COUNT == 0,
    "output": output[:2000],
    "success": True
}
print(json.dumps(result, indent=2))
PYEOF
)

if [ -n "$OUTPUT_FILE" ]; then
    echo "$RESULT" > "$OUTPUT_FILE"
    echo "Results written to $OUTPUT_FILE"
else
    echo "$RESULT"
fi
