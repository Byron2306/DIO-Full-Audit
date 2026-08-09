#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTAINER="${METATRON_BACKEND_CONTAINER:-metatron-seraph-v9-backend-1}"
PACKAGE_DATE="${PACKAGE_DATE:-2026-04-18}"
OUT_DIR_IN_CONTAINER="${REAL_S5_EVIDENCE_OUT:-/tmp/evidence-bundle-real-s5}"
STAGING_DIR="$ROOT_DIR/metatron-evidence-package-real-sandbox-s5-${PACKAGE_DATE}"
ZIP_BASE="$ROOT_DIR/metatron-coverage-package-${PACKAGE_DATE}-real-sandbox-s5"

docker cp "$ROOT_DIR/backend/evidence_bundle.py" "$CONTAINER:/app/backend/evidence_bundle.py"

TECH_LIST="$ROOT_DIR/.tmp/real_sandbox_s5_techniques.txt"
mkdir -p "$(dirname "$TECH_LIST")"

docker exec "$CONTAINER" sh -lc "python3 - <<'PY' > /tmp/real_s5_techniques.txt
import json, glob
from collections import defaultdict

runs = defaultdict(int)
for f in glob.glob('/var/lib/seraph-ai/atomic-validation/run_*.json'):
    try:
        d = json.load(open(f))
    except Exception:
        continue
    stdout = str(d.get('stdout') or '')
    command = str(d.get('command') or d.get('command_line') or '')
    if d.get('status') == 'success' and int(d.get('exit_code', -1)) == 0 and 'Executing test:' in stdout and 'ShowDetailsBrief' not in command and d.get('sandbox') == 'docker-network-none-cap-drop-all':
        for t in d.get('techniques_executed') or []:
            runs[str(t).strip().upper()] += 1

eligible = sorted([tech for tech, count in runs.items() if count >= 3])
print(','.join(eligible))
PY"

docker cp "$CONTAINER:/tmp/real_s5_techniques.txt" "$TECH_LIST"

if [[ ! -s "$TECH_LIST" ]]; then
  echo "No S5-eligible techniques found yet." >&2
  exit 1
fi

docker exec "$CONTAINER" rm -rf "$OUT_DIR_IN_CONTAINER"
docker exec "$CONTAINER" sh -lc "python3 /app/scripts/generate_evidence_bundle.py --techniques \"\$(cat /tmp/real_s5_techniques.txt)\" --output '$OUT_DIR_IN_CONTAINER'"

rm -rf "$STAGING_DIR" "${ZIP_BASE}.zip"
mkdir -p "$STAGING_DIR"/scripts "$STAGING_DIR"/backend "$STAGING_DIR"/docs "$STAGING_DIR"/config

docker cp "$CONTAINER:$OUT_DIR_IN_CONTAINER" "$STAGING_DIR/evidence_bundle"
cp "$ROOT_DIR/backend/evidence_bundle.py" "$STAGING_DIR/backend/"
cp "$ROOT_DIR/backend/atomic_validation.py" "$STAGING_DIR/backend/"
cp "$ROOT_DIR/scripts/generate_evidence_bundle.py" "$STAGING_DIR/scripts/"
cp "$ROOT_DIR/scripts/run_real_sandbox_sweep.py" "$STAGING_DIR/scripts/"
cp "$ROOT_DIR/scripts/run_real_sandbox_s5_promotion.sh" "$STAGING_DIR/scripts/"
cp "$ROOT_DIR/scripts/setup_windows_validation_vm.sh" "$STAGING_DIR/scripts/"
cp "$ROOT_DIR/scripts/import_windows_dev_vm.sh" "$STAGING_DIR/scripts/"
cp "$ROOT_DIR/docs/ATOMIC_MULTI_PLATFORM_RUNNERS.md" "$STAGING_DIR/docs/"
cp "$ROOT_DIR/docs/WINDOWS_VALIDATION_VM.md" "$STAGING_DIR/docs/"
cp "$ROOT_DIR/config/atomic_runner_profiles.example.yml" "$STAGING_DIR/config/"
cp "$ROOT_DIR/config/windows_validation_vm.env.example" "$STAGING_DIR/config/"

python3 - <<'PY'
import json, shutil
from pathlib import Path

root = Path('/home/byron/Downloads/Metatron-triune-outbound-gate')
staging = root / 'metatron-evidence-package-real-sandbox-s5-2026-04-18'
summary = json.loads((staging / 'evidence_bundle' / 'coverage_summary.json').read_text())
manifest = {
    'package_name': staging.name,
    'generated_at': '2026-04-18',
    'tier_breakdown': summary.get('tier_breakdown', {}),
    'coverage_source_count': (summary.get('derivation') or {}).get('source_count'),
}
(staging / 's5_execution_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
archive = shutil.make_archive(str(root / 'metatron-coverage-package-2026-04-18-real-sandbox-s5'), 'zip', staging.parent, staging.name)
print(archive)
PY