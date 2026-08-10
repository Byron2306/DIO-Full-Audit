#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.sophia.c10_validation import ALLOWED_ROLES, build_human_validation  # noqa: E402


def markdown(payload: dict) -> str:
    reviewer = payload.get("reviewer") or {}
    metrics = payload.get("metrics") or {}
    gates = payload.get("gates") or {}
    lines = [
        "# Sophia C10 Human Validation Receipt",
        "",
        f"Project: `{payload.get('project_id')}`",
        f"Validation result: **{'PASS' if payload.get('validation_passed') else 'NOT YET PASSED'}**",
        f"Reviewer role: {reviewer.get('role')}",
        f"Independent of build: {reviewer.get('independent_of_build')}",
        "",
        "## Observed Sample",
        "",
        f"- Support-mapping accuracy: {metrics.get('support_mapping_accuracy')}",
        f"- Review false-positive rate: {metrics.get('review_false_positive_rate')}",
        f"- Topology usefulness: {metrics.get('topology_usefulness')}",
        "",
        "## Gates",
        "",
    ]
    lines.extend(f"- {'PASS' if value else 'FAIL'} · `{key}`" for key, value in gates.items())
    lines.extend([
        "",
        "## Notes",
        "",
        str(payload.get("notes") or "No notes supplied."),
        "",
        "## Truth Boundary",
        "",
        str(payload.get("truth_boundary") or ""),
        "",
        f"Receipt SHA-256: `{payload.get('validation_receipt_sha256')}`",
    ])
    return "\n".join(lines)


def parse_optional_bool(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized in {"yes", "true", "1"}:
        return True
    if normalized in {"no", "false", "0"}:
        return False
    if normalized in {"unknown", "unsure", "na", "n/a"}:
        return None
    raise argparse.ArgumentTypeError("Use yes, no, or unknown.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a human validation sample for one Sophia C10 live case.")
    parser.add_argument("--job-dir", type=Path, required=True)
    parser.add_argument("--reviewer-alias", required=True)
    parser.add_argument("--reviewer-role", choices=sorted(ALLOWED_ROLES), required=True)
    parser.add_argument("--independent-of-build", action="store_true")
    parser.add_argument("--claims-checked", type=int, required=True)
    parser.add_argument("--support-mappings-correct", type=int, required=True)
    parser.add_argument("--review-flags-checked", type=int, required=True)
    parser.add_argument("--false-positive-flags", type=int, required=True)
    parser.add_argument("--source-verifications-completed", type=int, required=True)
    parser.add_argument("--topology-questions-reviewed", type=int, default=0)
    parser.add_argument("--topology-questions-useful", type=int, default=0)
    parser.add_argument("--missed-material-issues", type=int, default=0)
    parser.add_argument("--decisions-materially-helped", type=int, required=True)
    parser.add_argument("--authorship-boundary-respected", type=parse_optional_bool, required=True)
    parser.add_argument("--would-use-again", type=parse_optional_bool, default=None)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    if args.authorship_boundary_respected is None:
        raise ValueError("authorship-boundary-respected must be yes or no for validation.")
    job_dir = args.job_dir.expanduser().resolve()
    job_path = job_dir / "JOB.json"
    if not job_path.is_file():
        raise FileNotFoundError(job_path)
    job = json.loads(job_path.read_text(encoding="utf-8"))
    project_id = str(job.get("job_id") or job_dir.name)
    payload = build_human_validation(
        project_id=project_id,
        reviewer_alias=args.reviewer_alias,
        reviewer_role=args.reviewer_role,
        independent_of_build=args.independent_of_build,
        claims_checked=args.claims_checked,
        support_mappings_correct=args.support_mappings_correct,
        review_flags_checked=args.review_flags_checked,
        false_positive_flags=args.false_positive_flags,
        source_verifications_completed=args.source_verifications_completed,
        topology_questions_reviewed=args.topology_questions_reviewed,
        topology_questions_useful=args.topology_questions_useful,
        missed_material_issues=args.missed_material_issues,
        decisions_materially_helped=args.decisions_materially_helped,
        authorship_boundary_respected=bool(args.authorship_boundary_respected),
        would_use_again=args.would_use_again,
        notes=args.notes,
    )
    c10_root = job_dir / "C10_LONGITUDINAL_SPECULUM"
    c10_root.mkdir(parents=True, exist_ok=True)
    (c10_root / "C10_HUMAN_VALIDATION.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (c10_root / "C10_HUMAN_VALIDATION.md").write_text(markdown(payload) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0 if payload["validation_passed"] else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Sophia C10 human validation blocked: {error}", file=sys.stderr)
        raise SystemExit(2)
