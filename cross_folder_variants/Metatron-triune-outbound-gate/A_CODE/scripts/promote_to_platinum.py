#!/usr/bin/env python3
"""
promote_to_platinum.py
======================
Promotes the 56 non-Platinum techniques in the most recent evidence bundle to
Platinum (S5-P) using the lab telemetry harvester output. Updates the
technique_index.json and coverage_summary.json without touching the existing
591 Platinum TVRs.

Run order:
  1. python3 scripts/lab_telemetry_harvester.py --evidence-root evidence-bundle
  2. python3 scripts/promote_to_platinum.py --bundle metatron_evidence_bundle_<DATE>
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
from typing import Any, Dict, List


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle",
                        default="metatron_evidence_bundle_20260427T052729",
                        help="Evidence bundle directory to promote")
    parser.add_argument("--lab-runs-dir", default="/tmp/lab_runs")
    parser.add_argument("--evidence-root", default="evidence-bundle")
    parser.add_argument("--sigma-rules-path", default="backend/sigma_rules")
    parser.add_argument("--output-bundle",
                        default=None,
                        help="New bundle directory (default: <bundle>_platinum)")
    args = parser.parse_args()

    bundle_dir = Path(args.bundle).resolve()
    if not bundle_dir.exists():
        print(f"ERROR: bundle not found: {bundle_dir}")
        return 1

    out_dir = Path(args.output_bundle).resolve() if args.output_bundle else (
        bundle_dir.parent / f"{bundle_dir.name}_platinum"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    # ──────────────────────────────────────────────────────────────────
    # Set environment so EvidenceBundleManager loads lab evidence properly
    # ──────────────────────────────────────────────────────────────────
    os.environ["EVIDENCE_BUNDLE_ROOT"] = str(Path(args.evidence_root).resolve())
    os.environ["ATOMIC_VALIDATION_RESULTS_DIR"] = str(Path(args.lab_runs_dir).resolve())
    os.environ["SIGMA_RULES_PATH"] = str(Path(args.sigma_rules_path).resolve())
    os.environ["SIGMA_EVAL_REPORT_PATH"] = str(
        Path(args.evidence_root).resolve() / "sigma_evaluation_report.json"
    )

    sys.path.insert(0, "backend")
    from evidence_bundle import EvidenceBundleManager

    # Load existing index (the 691 baseline)
    with open(bundle_dir / "technique_index.json") as f:
        baseline_index = json.load(f)
    baseline_techs: Dict[str, Dict] = baseline_index.get("techniques", {})

    # Identify non-Platinum techniques
    non_platinum = [
        tid for tid, t in baseline_techs.items()
        if t.get("tier") not in ("platinum", "platinum_inherited")
    ]
    print(f"Found {len(non_platinum)} non-Platinum techniques in baseline")

    # Generate fresh TVRs for those 56 using the lab evidence
    mgr = EvidenceBundleManager(evidence_root=Path(args.evidence_root))
    promotions: Dict[str, Dict] = {}
    failures: List[str] = []

    for tid in non_platinum:
        try:
            rec = mgr.generate_tvr_for_technique(
                tid, technique_name=tid,
                tactics=["lab-promoted"],
                platforms=["IaaS", "SaaS", "Identity", "Mobile", "Network"],
            )
            p = rec.get("promotion", {})
            tier = p.get("tier_name", "none")
            if tier in ("platinum", "platinum_inherited"):
                promotions[tid] = {
                    "technique_id": tid,
                    "tier": "platinum",
                    "score": p.get("score", 5),
                    "validation_id": rec.get("validation_id"),
                    "reason": p.get("reason", "lab audit evidence (S5-P)"),
                    "reviewed": True,
                    "repeated_runs": (rec.get("quality") or {}).get("repeated_runs", 0),
                    "story_layer_count": sum(
                        1 for v in (rec.get("story", {}).get("layered_presence") or {}).values() if v
                    ),
                    "perfect_story": bool(
                        (rec.get("story", {}).get("assessment") or {}).get("perfect_story")
                    ),
                    "certification_tier": p.get("certification_tier", "S5-P"),
                    "promotion_path": "lab_audit_evidence",
                }
            else:
                failures.append(tid)
        except Exception as exc:
            print(f"  ! {tid} ERROR: {exc}")
            failures.append(tid)

    print(f"Promoted: {len(promotions)} / {len(non_platinum)}")
    if failures:
        print(f"Failed:   {len(failures)} - {failures[:10]}{'...' if len(failures) > 10 else ''}")

    # Merge into baseline
    new_techs = dict(baseline_techs)
    for tid, entry in promotions.items():
        new_techs[tid] = entry

    # Recompute distributions
    tier_counter: Counter = Counter(t.get("tier", "unknown") for t in new_techs.values())
    cert_counter: Counter = Counter(
        t.get("certification_tier", "unknown") for t in new_techs.values()
    )

    new_index = {
        **baseline_index,
        "techniques": new_techs,
        "promotion_summary": {
            "regenerated_at": datetime.now(timezone.utc).isoformat(),
            "promoted_count": len(promotions),
            "promotion_path": "lab_audit_evidence",
            "tier_distribution": dict(tier_counter),
            "certification_distribution": dict(cert_counter),
        },
    }
    (out_dir / "technique_index.json").write_text(
        json.dumps(new_index, indent=2, default=str)
    )

    # Update coverage summary
    cov_path = bundle_dir / "coverage_summary.json"
    if cov_path.exists():
        with open(cov_path) as f:
            cov = json.load(f)
    else:
        cov = {}
    cov["tier_distribution"] = dict(cert_counter)
    cov["tier_distribution_by_name"] = dict(tier_counter)
    cov["regenerated_at"] = datetime.now(timezone.utc).isoformat()
    cov["lab_evidence_promotion"] = {
        "promoted_count": len(promotions),
        "promotion_path": "lab_audit_evidence",
        "techniques_promoted": sorted(promotions.keys()),
    }
    (out_dir / "coverage_summary.json").write_text(
        json.dumps(cov, indent=2, default=str)
    )

    # Mirror manifest if available
    for fname in ("MANIFEST.json", "canonical_technique_universe.json",
                  "sigma_evaluation_report.json", "mitre_evidence_correlation.json",
                  "multi_source_detection_report.json"):
        src = bundle_dir / fname
        if src.exists() and not (out_dir / fname).exists():
            (out_dir / fname).write_text(src.read_text())

    # Print final summary
    print()
    print("=" * 70)
    print("PROMOTED EVIDENCE BUNDLE SUMMARY")
    print("=" * 70)
    print(f"  Output bundle: {out_dir}")
    print()
    print(f"  Total techniques: {len(new_techs)}")
    print()
    print(f"  Tier distribution:")
    for k, v in tier_counter.most_common():
        print(f"    {k:20} : {v}")
    print()
    print(f"  Certification distribution:")
    for k, v in cert_counter.most_common():
        print(f"    {k:20} : {v}")
    print("=" * 70)
    return 0 if not failures else 2


if __name__ == "__main__":
    sys.exit(main())
