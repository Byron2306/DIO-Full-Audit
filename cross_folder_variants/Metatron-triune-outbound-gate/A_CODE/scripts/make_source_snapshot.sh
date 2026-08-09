#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: Not a git repository: $ROOT_DIR" >&2
  exit 1
fi

STAMP="$(date +%Y-%m-%d)"
OUT_DIR="$ROOT_DIR/dist"
OUT_FILE="$OUT_DIR/metatron-source-snapshot-$STAMP.tar.gz"

mkdir -p "$OUT_DIR"

# Source-only snapshot: relies on .gitignore to keep secrets/artifacts out of the index.
git archive --format=tar HEAD | gzip -9 > "$OUT_FILE"

echo "Wrote: $OUT_FILE"

