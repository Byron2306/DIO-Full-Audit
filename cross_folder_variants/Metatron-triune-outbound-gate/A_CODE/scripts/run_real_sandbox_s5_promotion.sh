#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTAINER="${METATRON_BACKEND_CONTAINER:-metatron-seraph-v9-backend-1}"
SWEEP_SCRIPT_HOST="$ROOT_DIR/scripts/run_real_sandbox_sweep.py"
SWEEP_SCRIPT_CONTAINER="/tmp/run_real_sandbox_sweep.py"
TECH_LIST_FILE="${REAL_TECH_LIST_FILE:-$ROOT_DIR/.tmp/real_sandbox_222.txt}"
LOG_DIR="${REAL_S5_LOG_DIR:-$ROOT_DIR/test_reports/real_sandbox_s5}"
CONCURRENCY="${REAL_S5_CONCURRENCY:-3}"
BATCH_SIZE="${REAL_S5_BATCH_SIZE:-1}"
PASSES="${REAL_S5_PASSES:-2}"

mkdir -p "$LOG_DIR" "$(dirname "$TECH_LIST_FILE")"

python3 - <<'PY' > "$TECH_LIST_FILE"
import json
from pathlib import Path

manifest = Path('/home/byron/Downloads/Metatron-triune-outbound-gate/metatron-evidence-package-real-sandbox-2026-04-18/real_execution_manifest.json')
data = json.loads(manifest.read_text())
print(','.join(sorted(data['techniques'])))
PY

docker cp "$SWEEP_SCRIPT_HOST" "$CONTAINER:$SWEEP_SCRIPT_CONTAINER"

for pass_num in $(seq 2 $((PASSES + 1))); do
  log_file="$LOG_DIR/pass_${pass_num}.log"
  echo "Starting real sandbox promotion pass $pass_num"
  docker exec "$CONTAINER" python3 "$SWEEP_SCRIPT_CONTAINER" \
    --techniques "$(cat "$TECH_LIST_FILE")" \
    --batch-size "$BATCH_SIZE" \
    --concurrency "$CONCURRENCY" \
    --force | tee "$log_file"
done