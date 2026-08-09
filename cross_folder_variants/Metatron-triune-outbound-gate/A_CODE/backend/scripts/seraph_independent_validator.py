#!/usr/bin/env python3
"""Independent read-only validation of Seraph/Arda evidence integrity and outcomes."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_by_technique(evidence_dir: Path) -> Dict[str, Tuple[str, Path, Dict[str, Any]]]:
    latest: Dict[str, Tuple[str, Path, Dict[str, Any]]] = {}
    for path in sorted(evidence_dir.glob("arda_prevention_T*.json")):
        try:
            payload = _load_json(path)
        except Exception:
            continue
        technique = str(payload.get("technique_id") or "").strip().upper()
        if not technique:
            continue
        ts = str(payload.get("captured_at") or payload.get("started_at") or "")
        prev = latest.get(technique)
        if (not prev) or ts > prev[0]:
            latest[technique] = (ts, path, payload)
    return latest


def _digest_latest(latest: Dict[str, Tuple[str, Path, Dict[str, Any]]]) -> str:
    h = hashlib.sha256()
    for technique in sorted(latest.keys()):
        ts, path, payload = latest[technique]
        h.update(technique.encode("utf-8"))
        h.update(ts.encode("utf-8"))
        h.update(path.name.encode("utf-8"))
        verdict = str(payload.get("verdict") or "")
        denied = str(((payload.get("exec_attempt") or {}).get("denied")))
        h.update(verdict.encode("utf-8"))
        h.update(denied.encode("utf-8"))
    return h.hexdigest()


def _dagor_status(report_path: Path) -> Dict[str, Any]:
    if not report_path.exists():
        return {"available": False}
    payload = _load_json(report_path)
    events = payload.get("events") or []
    verdicts = [e for e in events if e.get("event_type") == "verdict"]
    if not verdicts:
        return {"available": False}
    v = verdicts[-1]
    details = v.get("details") or {}
    return {
        "available": True,
        "status": v.get("status"),
        "hostile_total": int(details.get("hostile_total") or 0),
        "hostile_denied": int(details.get("hostile_denied") or 0),
        "hostile_approved": int(details.get("hostile_approved") or 0),
        "hostile_queued": int(details.get("hostile_queued") or 0),
        "global_strictness": details.get("global_strictness"),
    }


def run(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = repo_root / "artifacts" / "evidence" / "arda_prevention"
    dagor_report = repo_root / "backend" / "scripts" / "telemetry_logs" / "DAGOR_DAGORLACH_ULTIMATE_GAUNTLET_report.json"

    if not evidence_dir.exists():
        raise SystemExit(f"Missing evidence dir: {evidence_dir}")

    latest = _latest_by_technique(evidence_dir)
    technique_count = len(latest)
    prevented = 0
    denied_true = 0

    for _tech, (_ts, _path, payload) in latest.items():
        verdict = str(payload.get("verdict") or "")
        denied = bool(((payload.get("exec_attempt") or {}).get("denied")))
        if verdict == "kernel_prevented":
            prevented += 1
        if denied:
            denied_true += 1

    dagor = _dagor_status(dagor_report)
    digest = _digest_latest(latest)

    pass_conditions = {
        "all_latest_kernel_prevented": prevented == technique_count,
        "all_latest_exec_denied": denied_true == technique_count,
        "dagor_no_hostile_approvals": (not dagor.get("available")) or int(dagor.get("hostile_approved", 1)) == 0,
    }

    all_pass = all(pass_conditions.values())

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "technique_count": technique_count,
        "kernel_prevented_count": prevented,
        "exec_denied_true_count": denied_true,
        "evidence_digest_sha256": digest,
        "dagor": dagor,
        "pass_conditions": pass_conditions,
        "overall_status": "pass" if all_pass else "fail",
    }

    out_path = repo_root / "backend" / "scripts" / "telemetry_logs" / "seraph_independent_validator_latest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(json.dumps({"overall_status": out["overall_status"], "output": str(out_path), "evidence_digest_sha256": digest}, indent=2))
    return 0 if all_pass else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Independent Seraph/Arda evidence validator")
    parser.add_argument("--repo-root", default=".", help="Repository root path")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
