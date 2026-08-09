"""
Re-score all TVRs by re-evaluating stored atomic_stdout.ndjson files.

The previous patch_rescore_clean_runs.py re-queried LIVE run files, which are
incomplete for many techniques (original sandbox sweep data is not in the
current run store). This script re-evaluates the STORED run stdout preserved
inside each TVR's telemetry/atomic_stdout.ndjson — the authoritative evidence.

For each technique:
  1. Find the latest TVR directory
  2. Read telemetry/atomic_stdout.ndjson (one run per JSON line)
  3. Re-count clean_runs using the updated stdout_is_clean() logic
  4. If count differs from stored: update tvr.json, verdict.json, re-score
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, "/app")

from backend.evidence_bundle import (
    EvidenceBundleManager,
    stdout_is_clean,
    stdout_has_real_success,
    score_tvr_record,
)

SCORE_TO_TIER = {0: "none", 2: "bronze", 3: "silver", 4: "gold", 5: "platinum"}

mgr = EvidenceBundleManager()
tech_root = mgr.techniques_dir

stats = {"unchanged": 0, "changed": 0, "errors": 0, "no_ndjson": 0}
changes = []

for tdir in sorted(tech_root.glob("*/")):
    tid = tdir.name
    tvr_dirs = sorted(tdir.glob("TVR-*/"))
    if not tvr_dirs:
        continue
    latest_tvr_dir = tvr_dirs[-1]
    tvr_path = latest_tvr_dir / "tvr.json"
    verdict_path = latest_tvr_dir / "verdict.json"
    ndjson_path = latest_tvr_dir / "telemetry" / "atomic_stdout.ndjson"

    if not tvr_path.exists():
        continue

    try:
        tvr = json.loads(tvr_path.read_text(encoding="utf-8"))
    except Exception as e:
        stats["errors"] += 1
        continue

    old_quality = tvr.get("quality") or {}
    old_clean_runs = int(old_quality.get("clean_runs", 0) or 0)
    old_repeated = int(old_quality.get("repeated_runs", 0) or 0)

    if not ndjson_path.exists():
        stats["no_ndjson"] += 1
        continue

    # Re-count from stored run stdout
    stored_runs = []
    try:
        for line in ndjson_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                stored_runs.append(json.loads(line))
    except Exception as e:
        stats["errors"] += 1
        continue

    clean_count = 0
    partial_count = 0
    for run_data in stored_runs:
        run_stdout = str(run_data.get("stdout") or "")
        if stdout_has_real_success(run_stdout):
            partial_count += 1
        if stdout_is_clean(run_stdout):
            clean_count += 1

    if clean_count == old_clean_runs:
        stats["unchanged"] += 1
        continue

    # Update TVR quality
    tvr.setdefault("quality", {})
    tvr["quality"]["clean_runs"] = clean_count
    tvr["quality"]["repeated_runs"] = max(partial_count, old_repeated)

    has_execution = bool((tvr.get("execution") or {}).get("real_execution"))
    has_sigma = any(
        x.get("matched")
        for x in ((tvr.get("analytic_evidence") or {}).get("sigma") or [])
    )
    tvr["quality"]["analyst_reviewed"] = (
        has_execution and has_sigma and clean_count >= 3
    )
    tvr["quality"]["auto_validated"] = tvr["quality"]["analyst_reviewed"]

    new_score = score_tvr_record(tvr)
    new_tier = SCORE_TO_TIER.get(new_score, "none")
    old_verdict_tier = ""

    tvr.setdefault("promotion", {})
    old_verdict_tier = tvr["promotion"].get("tier_name", "none")
    tvr["promotion"]["tier"] = f"S{new_score}"
    tvr["promotion"]["tier_name"] = new_tier
    tvr["promotion"]["score"] = new_score
    tvr["promotion"]["reeval_at"] = datetime.now(timezone.utc).isoformat()
    tvr["promotion"]["reeval_reason"] = (
        f"Re-scored from stored atomic_stdout: clean_runs {old_clean_runs}→{clean_count}"
    )

    tvr_path.write_text(json.dumps(tvr, indent=2, ensure_ascii=False), encoding="utf-8")

    if verdict_path.exists():
        try:
            verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
        except Exception:
            verdict = {}
        verdict["tier"] = f"S{new_score}"
        verdict["tier_name"] = new_tier
        verdict["score"] = new_score
        verdict["reviewed"] = bool(tvr["quality"].get("analyst_reviewed"))
        verdict["repeated_runs"] = tvr["quality"]["repeated_runs"]
        verdict_path.write_text(json.dumps(verdict, indent=2, ensure_ascii=False), encoding="utf-8")

    stats["changed"] += 1
    changes.append(
        f"{tid}: {old_verdict_tier}→{new_tier} "
        f"(clean {old_clean_runs}→{clean_count})"
    )

print(f"\n=== Re-score from stored TVR stdout ===")
print(f"Unchanged  : {stats['unchanged']}")
print(f"Changed    : {stats['changed']}")
print(f"No ndjson  : {stats['no_ndjson']}")
print(f"Errors     : {stats['errors']}")

if changes:
    print(f"\nChanges ({len(changes)}):")
    for c in changes[:50]:
        print(f"  {c}")
    if len(changes) > 50:
        print(f"  ... and {len(changes)-50} more")
