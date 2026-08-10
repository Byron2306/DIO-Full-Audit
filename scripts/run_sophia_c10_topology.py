#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.sophia.c10_gate import require_scholarly_release_clear_summary  # noqa: E402
from adapters.sophia.longitudinal_speculum import build_longitudinal_export  # noqa: E402
from adapters.sophia.scholarly_topology import (  # noqa: E402
    build_and_write_topology,
    record_topology_decision,
)


DEFAULT_SOPHIA_ROOT = Path("/home/byron/Integritas-Mechanicus")


def _lineage_summary(payload: dict) -> dict:
    return {
        "state": "longitudinal_speculum_ready",
        "version_count": int(payload.get("version_count") or 0),
        "lineage_count": int(payload.get("lineage_count") or 0),
        "unresolved_continuity_candidates": len(payload.get("unresolved_continuity_candidates") or []),
        "burden_mutation_lineages": len(payload.get("burden_mutation_lineages") or []),
        "author_decisions": len(payload.get("author_decisions") or []),
        "longitudinal_speculum_hash": payload.get("longitudinal_speculum_hash") or "",
        "native_integrity_record_hash": payload.get("native_integrity_record_hash") or "",
    }


def audit(*, state_root: Path, project_id: str, sophia_root: Path) -> dict:
    longitudinal = build_longitudinal_export(
        state_root=state_root,
        project_id=project_id,
        sophia_root=sophia_root,
    )
    topology = build_and_write_topology(
        state_root=state_root,
        project_id=project_id,
        sophia_root=sophia_root,
    )
    return {
        "project_id": project_id,
        "longitudinal": _lineage_summary(longitudinal),
        "topology": topology,
        "release_state": "hold_for_human_decisions" if int(topology.get("blocking_decision_queue") or 0) else "scholarly_release_clear",
    }


def decide(
    *,
    state_root: Path,
    project_id: str,
    issue_id: str,
    decision: str,
    actor: str,
    rationale: str,
    sophia_root: Path,
) -> dict:
    result = record_topology_decision(
        state_root=state_root,
        project_id=project_id,
        issue_id=issue_id,
        decision=decision,
        actor=actor,
        rationale=rationale,
        sophia_root=sophia_root,
    )
    return audit(state_root=state_root, project_id=project_id, sophia_root=sophia_root) | {"decision_result": result}


def gate(*, state_root: Path, project_id: str, minimum_versions: int, sophia_root: Path) -> dict:
    result = audit(state_root=state_root, project_id=project_id, sophia_root=sophia_root)
    require_scholarly_release_clear_summary(
        result["longitudinal"],
        minimum_versions=minimum_versions,
        topology=result["topology"],
    )
    result["release_state"] = "scholarly_release_clear"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Sophia C10 scholarly topology and human-decision gate.")
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--sophia-root", type=Path, default=DEFAULT_SOPHIA_ROOT)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("audit", help="Build the scholarly topology audit and decision queue.")

    decision = sub.add_parser("decide", help="Record a human interpretation of a split, merge or material surface mutation.")
    decision.add_argument("--issue", required=True)
    decision.add_argument("--decision", required=True)
    decision.add_argument("--actor", required=True)
    decision.add_argument("--rationale", required=True)

    release = sub.add_parser("gate", help="Fail closed unless lineage and scholarly decision obligations are clear.")
    release.add_argument("--minimum-versions", type=int, default=2)

    args = parser.parse_args()
    state_root = args.state_root.expanduser().resolve()
    sophia_root = args.sophia_root.expanduser().resolve()
    if args.command == "audit":
        result = audit(state_root=state_root, project_id=args.project_id, sophia_root=sophia_root)
    elif args.command == "decide":
        result = decide(
            state_root=state_root,
            project_id=args.project_id,
            issue_id=args.issue,
            decision=args.decision,
            actor=args.actor,
            rationale=args.rationale,
            sophia_root=sophia_root,
        )
    else:
        result = gate(
            state_root=state_root,
            project_id=args.project_id,
            minimum_versions=args.minimum_versions,
            sophia_root=sophia_root,
        )
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Sophia C10 topology gate blocked: {error}", file=sys.stderr)
        raise SystemExit(2)
