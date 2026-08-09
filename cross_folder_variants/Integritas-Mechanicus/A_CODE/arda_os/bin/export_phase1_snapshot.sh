#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ARDA_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
DOCS_ROOT=$(CDPATH= cd -- "$ARDA_ROOT/.." && pwd)/docs
STAMP=$(date -u +%Y%m%dT%H%M%SZ)

JSON_OUT="$DOCS_ROOT/ARDA_PHASE1_STATUS_${STAMP}.json"
MD_OUT="$DOCS_ROOT/ARDA_PHASE1_STATUS_${STAMP}.md"

cd "$ARDA_ROOT"
python3 bin/arda_status.py --json > "$JSON_OUT"
python3 bin/arda_status.py --markdown > "$MD_OUT"

echo "ARDA_EXPORT: wrote $JSON_OUT"
echo "ARDA_EXPORT: wrote $MD_OUT"
