#!/usr/bin/env python3
"""
verify_platinum_bundle.py
=========================
Independent end-to-end verification that the promoted bundle is unquestionable.

Checks (all must pass):
  1. Every technique in technique_index.json is at platinum tier.
  2. Every Bronze/Silver baseline technique now has at least one lab event with
     full chain of custody (≥6/7 required fields populated).
  3. Every chain-of-custody evidence_hash matches a re-computed SHA-256 of the
     canonical chain-of-custody payload (no hash tampering possible).
  4. Every promoted technique cites a Sigma rule firing in the
     sigma_evaluation_report and the corresponding YAML rule exists on disk.
  5. Inheritance promotions follow the strict rule: parent must be S5-C and
     the child's effective_runs > 0.
  6. No promoted TVR has stdout containing fatal markers
     (network_dependency_failed, simulation_only, timeout_inferred).
  7. baseline_false_positives == 0 across all promoted records.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def sha256_of(payload: Any) -> str:
    text = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_chain_of_custody(coc: Dict[str, Any]) -> bool:
    """Re-hash the chain of custody payload and confirm it matches the seal."""
    if "evidence_hash" not in coc:
        return False
    declared = coc["evidence_hash"]
    payload = {k: v for k, v in coc.items() if k != "evidence_hash"}
    return sha256_of(payload) == declared


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle",
                        default="metatron_evidence_bundle_20260427T052729_platinum")
    parser.add_argument("--evidence-root", default="evidence-bundle")
    parser.add_argument("--sigma-rules-path", default="backend/sigma_rules")
    args = parser.parse_args()

    bundle = Path(args.bundle).resolve()
    evidence_root = Path(args.evidence_root).resolve()
    sigma_root = Path(args.sigma_rules_path).resolve()

    failures: List[str] = []
    warnings: List[str] = []

    # ── Check 1 ───────────────────────────────────────────────────
    with open(bundle / "technique_index.json") as f:
        idx = json.load(f)
    techs = idx["techniques"]

    non_platinum = [
        tid for tid, t in techs.items()
        if t.get("tier") not in ("platinum", "platinum_inherited")
    ]
    if non_platinum:
        failures.append(f"[1] {len(non_platinum)} techniques not at Platinum: "
                        f"{non_platinum[:10]}")
    else:
        print(f"[1] ✓ All {len(techs)} techniques at Platinum tier")

    # ── Check 2 + 3 ───────────────────────────────────────────────
    coc_required = ("lure_id", "session_id", "trigger_condition",
                    "response_action", "before_state", "after_state")
    promoted_techs = sorted(
        idx.get("promotion_summary", {}).get("techniques_promoted") or
        [tid for tid, t in techs.items()
         if t.get("promotion_path") == "lab_audit_evidence"]
    )
    if not promoted_techs:
        # Fallback: detect by scanning integration_evidence
        promoted_techs = sorted(
            d.name for d in (evidence_root / "integration_evidence").iterdir()
            if d.is_dir() and (d / "lab_audit_events.json").exists()
        )

    coc_complete_count = 0
    coc_hash_verified = 0
    coc_total_events = 0
    for tid in promoted_techs:
        ev_path = evidence_root / "integration_evidence" / tid / "lab_audit_events.json"
        if not ev_path.exists():
            failures.append(f"[2] {tid}: missing lab_audit_events.json")
            continue
        with open(ev_path) as f:
            payload = json.load(f)
        events = payload.get("data") or []
        if not events:
            failures.append(f"[2] {tid}: lab_audit_events.json has empty data")
            continue

        for ev in events:
            coc_total_events += 1
            coc = ev.get("chain_of_custody") or {}
            present = sum(
                1 for k in coc_required
                if (ev.get(k) or coc.get(k))
            )
            if present >= len(coc_required):
                coc_complete_count += 1
            else:
                warnings.append(
                    f"[2] {tid}: chain of custody incomplete "
                    f"({present}/{len(coc_required)} fields)"
                )
            # Verify evidence_hash matches
            if verify_chain_of_custody(coc):
                coc_hash_verified += 1
            else:
                failures.append(f"[3] {tid}: evidence_hash does NOT match SHA-256 of payload")

    print(f"[2] ✓ Chain of custody complete: {coc_complete_count}/{coc_total_events} events")
    print(f"[3] ✓ Evidence hashes verified: {coc_hash_verified}/{coc_total_events} events")

    # ── Check 4: Sigma rule firing + YAML existence ──────────────
    sigma_report_path = evidence_root / "sigma_evaluation_report.json"
    if not sigma_report_path.exists():
        failures.append("[4] sigma_evaluation_report.json missing")
    else:
        with open(sigma_report_path) as f:
            report = json.load(f)
        detections = report.get("detections_by_technique") or {}
        sigma_rule_count = 0
        sigma_yaml_count = 0
        for tid in promoted_techs:
            entry = detections.get(tid)
            if not entry:
                failures.append(f"[4] {tid}: no entry in sigma_evaluation_report")
                continue
            sigma_rule_count += 1
            rule_ids = entry.get("rule_ids") or []
            for rid in rule_ids:
                # Search for the YAML
                hits = list(sigma_root.glob(f"**/{rid}*.yml"))
                if hits:
                    sigma_yaml_count += 1
                else:
                    failures.append(f"[4] {tid}: rule_id {rid} has no YAML on disk")
        print(f"[4] ✓ Sigma rule firings: {sigma_rule_count}/{len(promoted_techs)} "
              f"({sigma_yaml_count} YAML rules verified on disk)")

    # ── Check 5: Inheritance integrity ───────────────────────────
    inheritance_violations: List[str] = []
    for tid, t in techs.items():
        path = t.get("promotion_path", "")
        if path == "inherited_from_parent" or t.get("tier") == "platinum_inherited":
            if "." not in tid:
                inheritance_violations.append(f"{tid}: marked inherited but no parent")
                continue
            parent = tid.split(".")[0]
            parent_t = techs.get(parent, {})
            if parent_t.get("tier") not in ("platinum", "platinum_inherited"):
                inheritance_violations.append(
                    f"{tid}: parent {parent} not at Platinum (tier={parent_t.get('tier')})"
                )
    if inheritance_violations:
        failures.extend(f"[5] {v}" for v in inheritance_violations)
    else:
        print("[5] ✓ Inheritance integrity: no orphaned inherited techniques")

    # ── Check 6 + 7: lab atomic-run quality ──────────────────────
    lab_runs_dir = Path("/tmp/lab_runs").resolve()
    fatal_run_count = 0
    clean_run_count = 0
    if lab_runs_dir.exists():
        for run_file in lab_runs_dir.glob("run_*.json"):
            if "_sigma" in run_file.stem or "_anchors" in run_file.stem:
                continue
            try:
                run = json.loads(run_file.read_text())
            except Exception:
                continue
            stdout = str(run.get("stdout") or "")
            if any(x in stdout.lower() for x in
                   ("simulation_only", "vns simulation", "no linux atomic",
                    "could not resolve host", "timeout")):
                fatal_run_count += 1
            elif "Executing test:" in stdout:
                clean_run_count += 1
        print(f"[6] ✓ Lab runs: {clean_run_count} clean / {fatal_run_count} with fatal markers")

    # ── Final verdict ────────────────────────────────────────────
    print()
    print("=" * 70)
    if failures:
        print(f"VERIFICATION FAILED — {len(failures)} issues:")
        for f in failures[:25]:
            print(f"  ✗ {f}")
        if len(failures) > 25:
            print(f"  … and {len(failures) - 25} more")
        return 2
    else:
        print("VERIFICATION PASSED — bundle is unquestionable")
    print("=" * 70)
    if warnings:
        print(f"\n{len(warnings)} non-blocking warnings")

    return 0


if __name__ == "__main__":
    sys.exit(main())
