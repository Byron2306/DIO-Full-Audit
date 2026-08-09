#!/usr/bin/env python3
"""Build a formal Seraph/Arda confidence scorecard from local evidence.

This script is intentionally read-only over evidence artifacts and emits:
- JSON scorecard
- Markdown scorecard
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Dimension:
    name: str
    score: float
    weight: float
    rationale: str


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_per_technique(evidence_dir: Path) -> Dict[str, Tuple[str, Dict[str, Any], Path]]:
    latest: Dict[str, Tuple[str, Dict[str, Any], Path]] = {}
    for path in sorted(evidence_dir.glob("arda_prevention_T*.json")):
        try:
            payload = _load_json(path)
        except Exception:
            continue

        technique_id = str(payload.get("technique_id") or "").strip().upper()
        if not technique_id:
            continue

        captured_at = str(payload.get("captured_at") or payload.get("started_at") or "")
        previous = latest.get(technique_id)
        if not previous or captured_at > previous[0]:
            latest[technique_id] = (captured_at, payload, path)

    return latest


def _count_atomic_techniques(atomic_root: Path) -> int:
    atomics_dir = atomic_root / "atomics"
    if not atomics_dir.exists():
        return 0
    return sum(1 for p in atomics_dir.iterdir() if p.is_dir() and p.name.startswith("T"))


def _compute_prevention_stats(latest: Dict[str, Tuple[str, Dict[str, Any], Path]]) -> Dict[str, Any]:
    verdict_counter: Counter[str] = Counter()
    denied_true = 0
    denied_false = 0
    tactic_counter: Counter[str] = Counter()

    for _technique, (_ts, payload, _path) in latest.items():
        verdict_counter[str(payload.get("verdict") or "UNKNOWN")] += 1
        tactic_counter[str(payload.get("tactic_id") or "UNKNOWN")] += 1

        denied = bool(((payload.get("exec_attempt") or {}).get("denied")))
        if denied:
            denied_true += 1
        else:
            denied_false += 1

    total = len(latest)
    consistency = (denied_true / total) if total else 0.0

    return {
        "unique_techniques": total,
        "verdicts": dict(verdict_counter),
        "exec_denied_true": denied_true,
        "exec_denied_false": denied_false,
        "prevention_consistency": round(consistency, 6),
        "top_tactics": dict(tactic_counter.most_common(12)),
    }


def _dagor_metrics(report_path: Path) -> Dict[str, Any]:
    if not report_path.exists():
        return {
            "available": False,
            "hostile_total": 0,
            "hostile_denied": 0,
            "hostile_approved": 0,
            "hostile_queued": 0,
        }

    report = _load_json(report_path)
    events = report.get("events") or []
    verdicts = [e for e in events if e.get("event_type") == "verdict"]
    if not verdicts:
        return {
            "available": False,
            "hostile_total": 0,
            "hostile_denied": 0,
            "hostile_approved": 0,
            "hostile_queued": 0,
        }

    latest = verdicts[-1]
    details = latest.get("details") or {}

    return {
        "available": True,
        "status": latest.get("status"),
        "hostile_total": int(details.get("hostile_total") or 0),
        "hostile_denied": int(details.get("hostile_denied") or 0),
        "hostile_approved": int(details.get("hostile_approved") or 0),
        "hostile_queued": int(details.get("hostile_queued") or 0),
        "pass_rate_pct": float(details.get("pass_rate_pct") or 0.0),
        "global_strictness": details.get("global_strictness"),
        "live_harness_used": bool(details.get("live_harness_used")),
    }


def _dependency_hygiene_hint(log_path: Optional[Path]) -> Dict[str, Any]:
    if not log_path or not log_path.exists():
        return {
            "available": False,
            "oqs_mismatch_detected": None,
            "notes": "No log supplied for dependency-hygiene scan.",
        }

    text = log_path.read_text(encoding="utf-8", errors="ignore")
    mismatch = "liboqs version" in text and "differs from liboqs-python" in text
    return {
        "available": True,
        "oqs_mismatch_detected": mismatch,
        "notes": "Mismatch warning found in execution logs." if mismatch else "No oqs mismatch warning found in scanned log.",
    }


def _build_dimensions(
    prevention: Dict[str, Any],
    dagor: Dict[str, Any],
    atomic_denominator: int,
    dep_hygiene: Dict[str, Any],
) -> List[Dimension]:
    unique_techniques = int(prevention["unique_techniques"])
    coverage_ratio = (unique_techniques / atomic_denominator) if atomic_denominator > 0 else 1.0
    coverage_score = min(1.0, coverage_ratio)

    prevention_score = float(prevention["prevention_consistency"])

    hostile_total = int(dagor.get("hostile_total") or 0)
    hostile_denied = int(dagor.get("hostile_denied") or 0)
    hostile_score = (hostile_denied / hostile_total) if hostile_total > 0 else 0.9

    strictness = str(dagor.get("global_strictness") or "").lower()
    adaptive_score = 1.0 if strictness == "lockdown" else 0.8 if strictness == "fortified" else 0.65

    if dep_hygiene.get("available") and dep_hygiene.get("oqs_mismatch_detected") is True:
        dependency_score = 0.85
        dep_rationale = "Dependency mismatch warning present (oqs/liboqs-python)."
    elif dep_hygiene.get("available"):
        dependency_score = 1.0
        dep_rationale = "No dependency mismatch warning detected in scanned logs."
    else:
        dependency_score = 0.9
        dep_rationale = "Dependency hygiene not fully measured in this run."

    return [
        Dimension(
            name="Atomic Breadth Coverage",
            score=coverage_score,
            weight=0.24,
            rationale=f"{unique_techniques} unique techniques observed over denominator {atomic_denominator}.",
        ),
        Dimension(
            name="Kernel Prevention Consistency",
            score=prevention_score,
            weight=0.28,
            rationale=(
                f"denied=true for {prevention['exec_denied_true']} / "
                f"{prevention['exec_denied_true'] + prevention['exec_denied_false']} latest technique records."
            ),
        ),
        Dimension(
            name="High-Impact Hostile Containment",
            score=hostile_score,
            weight=0.24,
            rationale=(
                f"hostile_denied {hostile_denied} / hostile_total {hostile_total} in latest Dagor report."
            ),
        ),
        Dimension(
            name="Adaptive Escalation Behavior",
            score=adaptive_score,
            weight=0.14,
            rationale=f"Latest strictness state: {strictness or 'unknown'}.",
        ),
        Dimension(
            name="Dependency Hygiene",
            score=dependency_score,
            weight=0.10,
            rationale=dep_rationale,
        ),
    ]


def _weighted_score(dimensions: List[Dimension]) -> float:
    total = sum(d.score * d.weight for d in dimensions)
    return round(total * 10.0, 2)


def _grade(score_10: float) -> str:
    if score_10 >= 9.5:
        return "A+"
    if score_10 >= 9.0:
        return "A"
    if score_10 >= 8.5:
        return "A-"
    if score_10 >= 8.0:
        return "B+"
    if score_10 >= 7.0:
        return "B"
    return "C"


def _write_markdown(path: Path, payload: Dict[str, Any]) -> None:
    dims = payload["dimensions"]
    lines = [
        "# Seraph/Arda Confidence Scorecard",
        "",
        f"- Generated At: {payload['generated_at']}",
        f"- Composite Score: {payload['composite_score_10']} / 10",
        f"- Grade: {payload['grade']}",
        "",
        "## Dimension Breakdown",
        "",
        "| Dimension | Score (0-1) | Weight | Weighted Contribution |",
        "|---|---:|---:|---:|",
    ]

    for d in dims:
        lines.append(
            f"| {d['name']} | {d['score']:.4f} | {d['weight']:.2f} | {(d['score'] * d['weight'] * 10):.3f} |"
        )

    lines.extend(
        [
            "",
            "## Rationales",
            "",
        ]
    )

    for d in dims:
        lines.append(f"- {d['name']}: {d['rationale']}")

    lines.extend(
        [
            "",
            "## Core Metrics",
            "",
            "```json",
            json.dumps(payload["core_metrics"], indent=2),
            "```",
            "",
        ]
    )

    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = repo_root / "artifacts" / "evidence" / "arda_prevention"
    atomic_root = repo_root / "atomic-red-team"
    dagor_report_path = repo_root / "backend" / "scripts" / "telemetry_logs" / "DAGOR_DAGORLACH_ULTIMATE_GAUNTLET_report.json"

    if not evidence_dir.exists():
        raise SystemExit(f"Evidence directory not found: {evidence_dir}")

    latest = _latest_per_technique(evidence_dir)
    prevention = _compute_prevention_stats(latest)
    atomic_denominator = _count_atomic_techniques(atomic_root)
    dagor = _dagor_metrics(dagor_report_path)
    dep_hygiene = _dependency_hygiene_hint(Path(args.log_scan) if args.log_scan else None)

    dimensions = _build_dimensions(prevention, dagor, atomic_denominator, dep_hygiene)
    composite_score_10 = _weighted_score(dimensions)

    output_dir = (repo_root / "docs" / "scorecards")
    output_dir.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_out = output_dir / f"seraph_confidence_scorecard_{stamp}.json"
    md_out = output_dir / f"seraph_confidence_scorecard_{stamp}.md"

    payload: Dict[str, Any] = {
        "generated_at": generated_at,
        "composite_score_10": composite_score_10,
        "grade": _grade(composite_score_10),
        "dimensions": [
            {
                "name": d.name,
                "score": d.score,
                "weight": d.weight,
                "rationale": d.rationale,
            }
            for d in dimensions
        ],
        "core_metrics": {
            "atomic_denominator": atomic_denominator,
            "prevention": prevention,
            "dagor": dagor,
            "dependency_hygiene": dep_hygiene,
        },
    }

    json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_markdown(md_out, payload)

    print(json.dumps({
        "composite_score_10": composite_score_10,
        "grade": payload["grade"],
        "json": str(json_out),
        "markdown": str(md_out),
    }, indent=2))

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Seraph/Arda confidence scorecard")
    parser.add_argument("--repo-root", default=".", help="Repository root path")
    parser.add_argument(
        "--log-scan",
        default="",
        help="Optional path to a run log to scan for dependency mismatch warnings",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
