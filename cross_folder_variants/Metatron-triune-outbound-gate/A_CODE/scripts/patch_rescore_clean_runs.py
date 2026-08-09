"""
Patch script: re-score all TVRs using the updated stdout_is_clean() logic.

After expanding _HARD_FAILURE_RE to catch exit 127 and 'cannot open script file',
previously-clean runs with those failures need to be re-counted.

Steps:
  1. Load all raw atomic runs (with stdout)
  2. Re-compute clean_runs per technique using updated stdout_is_clean()
  3. For each TVR on disk: update quality.clean_runs, quality.analyst_reviewed,
     promotion.tier, promotion.reason
  4. Write updated TVR back to disk
  5. Print diff summary
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
    tier_name,
)

SCORE_TO_TIER = {0: "none", 2: "bronze", 3: "silver", 4: "gold", 5: "platinum"}

mgr = EvidenceBundleManager()
raw_runs = mgr._load_atomic_runs()

technique_dirs = list(mgr.evidence_root.glob("techniques/*/"))

stats = {"unchanged": 0, "demoted": 0, "promoted": 0, "errors": 0}
demoted_list = []
promoted_list = []

for tdir in sorted(technique_dirs):
    tid = tdir.name
    tvr_dirs = sorted(tdir.glob("TVR-*/"))
    if not tvr_dirs:
        continue
    latest_tvr_dir = tvr_dirs[-1]
    tvr_path = latest_tvr_dir / "tvr.json"
    if not tvr_path.exists():
        continue

    try:
        tvr = json.loads(tvr_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ERROR reading {tvr_path}: {e}")
        stats["errors"] += 1
        continue

    runs = raw_runs.get(tid, [])
    tech_runs = runs

    # Re-count clean runs using updated logic
    clean_count = 0
    partial_count = 0
    for run in tech_runs:
        run_stdout = str(run.get("stdout") or "")
        # Skip synthetic/VNS runs
        if "[PCAP] Generated" in run_stdout:
            continue
        if "[VNS]" in run_stdout and "[PCAP]" not in run_stdout:
            continue
        if "Malware-PCAP-Replay" in run_stdout:
            continue
        if str(run.get("execution_mode") or "") == "pcap_replay":
            continue
        if stdout_has_real_success(run_stdout):
            partial_count += 1
        if stdout_is_clean(run_stdout):
            clean_count += 1

    old_quality = tvr.get("quality") or {}
    old_clean_runs = int(old_quality.get("clean_runs", 0) or 0)
    old_tier = (tvr.get("promotion") or {}).get("tier", "none")

    if clean_count == old_clean_runs:
        # No change in clean run count → score won't change
        stats["unchanged"] += 1
        continue

    # Update TVR quality fields
    tvr.setdefault("quality", {})
    tvr["quality"]["clean_runs"] = clean_count
    tvr["quality"]["repeated_runs"] = partial_count
    tvr["quality"]["successful_detections"] = partial_count

    # Re-derive analyst_reviewed from updated clean count
    has_execution = bool((tvr.get("execution") or {}).get("real_execution"))
    has_sigma = any(
        x.get("matched")
        for x in ((tvr.get("analytic_evidence") or {}).get("sigma") or [])
    )
    tvr["quality"]["analyst_reviewed"] = (
        has_execution and has_sigma and clean_count >= 3
    )

    # Re-score
    new_score = score_tvr_record(tvr)
    new_tier = SCORE_TO_TIER.get(new_score, "none")

    if new_tier != old_tier:
        tvr.setdefault("promotion", {})
        tvr["promotion"]["tier"] = new_tier
        tvr["promotion"]["score"] = new_score
        tvr["promotion"]["patched_at"] = datetime.now(timezone.utc).isoformat()
        tvr["promotion"]["patch_reason"] = (
            f"Re-scored after stdout_is_clean() fix: "
            f"clean_runs {old_clean_runs}→{clean_count}"
        )

        if new_score < {"none": 0, "bronze": 2, "silver": 3, "gold": 4, "platinum": 5}.get(old_tier, 0):
            stats["demoted"] += 1
            demoted_list.append(f"{tid}: {old_tier}→{new_tier} (clean {old_clean_runs}→{clean_count})")
        else:
            stats["promoted"] += 1
            promoted_list.append(f"{tid}: {old_tier}→{new_tier} (clean {old_clean_runs}→{clean_count})")
    else:
        stats["unchanged"] += 1

    tvr_path.write_text(json.dumps(tvr, indent=2, ensure_ascii=False), encoding="utf-8")

    # Also update verdict.json — build_coverage_summary() reads this file
    verdict_path = latest_tvr_dir / "verdict.json"
    if verdict_path.exists():
        try:
            verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
        except Exception:
            verdict = {}
        verdict["tier"] = f"S{new_score}"
        verdict["tier_name"] = new_tier
        verdict["score"] = new_score
        verdict["reviewed"] = bool(tvr["quality"].get("analyst_reviewed"))
        verdict["repeated_runs"] = tvr["quality"].get("repeated_runs", 0)
        if new_tier != old_tier:
            verdict["patch_reason"] = (
                f"Re-scored after stdout_is_clean() fix: "
                f"clean_runs {old_clean_runs}→{clean_count}"
            )
        verdict_path.write_text(json.dumps(verdict, indent=2, ensure_ascii=False), encoding="utf-8")


print("\n=== Re-score Results ===")
print(f"Unchanged : {stats['unchanged']}")
print(f"Demoted   : {stats['demoted']}")
print(f"Promoted  : {stats['promoted']}")
print(f"Errors    : {stats['errors']}")

if demoted_list:
    print(f"\nDemotions ({len(demoted_list)}):")
    for d in demoted_list[:30]:
        print(f"  {d}")
    if len(demoted_list) > 30:
        print(f"  ... and {len(demoted_list)-30} more")

if promoted_list:
    print(f"\nPromotions ({len(promoted_list)}):")
    for p in promoted_list:
        print(f"  {p}")
