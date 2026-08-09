#!/usr/bin/env python3
"""
report_atomic_definition_gaps.py
================================
Produces a report of Atomic Red Team definition gaps relative to the technique
IDs referenced by sigma_engine.

Outputs:
- artifacts/reports/atomic_definition_gaps.json (default)

Usage:
  python3 scripts/report_atomic_definition_gaps.py
  python3 scripts/report_atomic_definition_gaps.py --out docs/atomic_definition_gaps.json
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Set

import yaml


def _load_sigma_techniques() -> List[str]:
    import sys

    sys.path.insert(0, "backend")
    sys.path.insert(0, ".")
    try:
        from sigma_engine import sigma_engine
    except Exception:
        from backend.sigma_engine import sigma_engine  # type: ignore

    summary = sigma_engine.coverage_summary()
    rows = (summary.get("unified_coverage") or {}).get("techniques") or []
    out: List[str] = []
    for row in rows:
        tid = str((row or {}).get("technique") or "").strip().upper()
        if tid:
            out.append(tid)
    return sorted(set(out))


def _atomic_yaml_path(atomics_root: Path, technique: str) -> Path:
    tid = technique.strip().upper()
    return atomics_root / tid / f"{tid}.yaml"


def _load_supported_platforms(yaml_path: Path) -> Set[str]:
    try:
        doc = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    tests = (doc or {}).get("atomic_tests") or []
    plats: Set[str] = set()
    for test in tests:
        if not isinstance(test, dict):
            continue
        for p in test.get("supported_platforms") or []:
            p2 = str(p).strip().lower()
            if p2:
                plats.add(p2)
    return plats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--atomics-root", default=os.environ.get("ATOMIC_RED_TEAM_ATOMICS", "atomic-red-team/atomics"))
    parser.add_argument("--out", default="artifacts/reports/atomic_definition_gaps.json")
    args = parser.parse_args()

    atomics_root = Path(args.atomics_root)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    sigma_techniques = _load_sigma_techniques()

    present: List[str] = []
    missing: List[str] = []
    linux_supported: List[str] = []
    non_linux_only: List[str] = []

    for tid in sigma_techniques:
        yml = _atomic_yaml_path(atomics_root, tid)
        if not yml.exists():
            missing.append(tid)
            continue
        present.append(tid)
        plats = _load_supported_platforms(yml)
        if "linux" in plats:
            linux_supported.append(tid)
        else:
            non_linux_only.append(tid)

    report: Dict[str, Any] = {
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "atomics_root": str(atomics_root),
        "sigma_technique_count": len(sigma_techniques),
        "present_atomic_yaml_count": len(present),
        "missing_atomic_yaml_count": len(missing),
        "linux_supported_count": len(linux_supported),
        "non_linux_only_count": len(non_linux_only),
        "missing_atomic_yaml": missing,
        "non_linux_only": non_linux_only,
    }

    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(str(out_path))
    print(f"missing_atomic_yaml={len(missing)}  non_linux_only={len(non_linux_only)}  linux_supported={len(linux_supported)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

