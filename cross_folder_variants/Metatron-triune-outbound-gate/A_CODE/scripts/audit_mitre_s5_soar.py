#!/usr/bin/env python3
"""Audit which S5 techniques have SOAR linkage evidence.

Reads:
- evidence-bundle/technique_index.json (TVR score/tier)
- backend/data/soar_executions_archive.json (SOAR execution evidence snapshot)
- backend/soar_engine.py (playbook -> technique mapping via regex)

This script is local-only and does not call the API.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple


TECH_RE = re.compile(r"\bT\d{4}(?:\.\d{3})?\b", re.IGNORECASE)


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _tvr_scores(evidence_root: Path) -> Dict[str, int]:
    idx = evidence_root / "technique_index.json"
    if not idx.exists():
        raise FileNotFoundError(f"Missing {idx}")
    payload = _read_json(idx)
    techniques = payload.get("techniques") or {}
    if not isinstance(techniques, dict):
        return {}
    out: Dict[str, int] = {}
    for tid, row in techniques.items():
        try:
            out[str(tid).strip().upper()] = int((row or {}).get("score") or 0)
        except Exception:
            out[str(tid).strip().upper()] = 0
    return out


def _soar_execution_techniques(archive_path: Path) -> Set[str]:
    if not archive_path.exists():
        return set()
    payload = _read_json(archive_path)
    if not isinstance(payload, list):
        return set()
    found: Set[str] = set()
    for row in payload:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "").lower()
        if status not in {"completed", "commands_queued", "success", "executed", "partial"}:
            continue
        trigger_event = row.get("trigger_event") if isinstance(row.get("trigger_event"), dict) else {}
        for key in ("validated_techniques", "techniques", "mitre_techniques", "attack_techniques"):
            value = trigger_event.get(key)
            if isinstance(value, list):
                for item in value:
                    tid = str(item or "").strip().upper()
                    if TECH_RE.fullmatch(tid):
                        found.add(tid)
    return found


def _soar_playbook_techniques(source_path: Path) -> Set[str]:
    if not source_path.exists():
        return set()
    text = source_path.read_text(encoding="utf-8", errors="ignore")
    return {match.group(0).upper() for match in TECH_RE.finditer(text)}


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    evidence_root = Path(os.environ.get("EVIDENCE_BUNDLE_ROOT", str(root / "evidence-bundle"))).resolve()
    archive_path = Path(
        os.environ.get("SIGMA_SOAR_EXECUTION_ARCHIVE_PATH", str(root / "backend" / "data" / "soar_executions_archive.json"))
    ).resolve()
    soar_engine_path = (root / "backend" / "soar_engine.py").resolve()

    tvr = _tvr_scores(evidence_root)
    tvr_s5 = {tid for tid, score in tvr.items() if score >= 5}

    exec_techs = _soar_execution_techniques(archive_path)
    playbook_techs = _soar_playbook_techniques(soar_engine_path)
    soar_linked = exec_techs | playbook_techs

    report = {
        "evidence_bundle_root": str(evidence_root),
        "tvr_indexed_techniques": len(tvr),
        "tvr_s5_count": len(tvr_s5),
        "soar_playbook_techniques": len(playbook_techs),
        "soar_execution_techniques": len(exec_techs),
        "tvr_s5_with_soar_link": len(tvr_s5 & soar_linked),
        "tvr_s5_missing_soar_link": len(tvr_s5 - soar_linked),
        "sample_missing": sorted(list(tvr_s5 - soar_linked))[:25],
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

