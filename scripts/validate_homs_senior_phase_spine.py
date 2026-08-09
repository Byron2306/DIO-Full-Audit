#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPINE = ROOT / "deliverables" / "homs_senior_phase_spine" / "HOMS_SENIOR_PHASE_SPINE.json"
DEFAULT_OUT = ROOT / "deliverables" / "homs_senior_phase_spine"
REQUIRED_BLOOM = ["remember", "understand", "apply", "analyse", "evaluate", "create"]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_blueprint(path: Path, blueprint: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if blueprint.get("phase") != "senior_grade_7_9":
        failures.append("wrong_phase")
    if blueprint.get("grade") not in {7, 8, 9}:
        failures.append("wrong_grade")
    bloom = blueprint.get("bloom_distribution") or {}
    missing_bloom = [item for item in REQUIRED_BLOOM if item not in bloom]
    if missing_bloom:
        failures.append("missing_bloom:" + ",".join(missing_bloom))
    elif sum(int(bloom[item]) for item in REQUIRED_BLOOM) != 100:
        failures.append("bloom_total_not_100")
    if not blueprint.get("source_grammar"):
        failures.append("missing_source_grammar")
    if not blueprint.get("sections"):
        failures.append("missing_sections")
    if not path.exists():
        failures.append("missing_blueprint_file")
    return failures


def main() -> int:
    spine = load_json(DEFAULT_SPINE)
    results = []
    for subject in spine.get("subjects") or []:
        subject_failures = []
        if subject.get("missing_caps_bridge"):
            subject_failures.append("missing_caps_bridge")
        if subject.get("status") != "senior_blueprint_ready_release_blocked":
            subject_failures.append("unexpected_status")
        blueprints = subject.get("blueprints") or []
        if len(blueprints) != 3:
            subject_failures.append("expected_three_grade_blueprints")
        for blueprint in blueprints:
            path = DEFAULT_OUT / "sample_blueprints" / subject["subject_id"] / f"grade_{blueprint.get('grade')}_blueprint.json"
            subject_failures.extend(validate_blueprint(path, blueprint))
        results.append(
            {
                "subject_id": subject["subject_id"],
                "display_name": subject["display_name"],
                "status": "passed" if not subject_failures else "failed",
                "failures": sorted(set(subject_failures)),
                "blueprint_count": len(blueprints),
                "release_gate": subject.get("release_gate"),
            }
        )
    payload = {
        "schema": "knowedge.homs_senior_phase_validation.v1",
        "created_at": utc_now(),
        "status": "passed" if all(item["status"] == "passed" for item in results) else "failed",
        "release_status": "blocked",
        "passed": sum(1 for item in results if item["status"] == "passed"),
        "failed": sum(1 for item in results if item["status"] != "passed"),
        "results": results,
    }
    out_json = DEFAULT_OUT / "HOMS_SENIOR_PHASE_VALIDATION.json"
    out_md = DEFAULT_OUT / "HOMS_SENIOR_PHASE_VALIDATION.md"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = [
        "# HOMS Senior Phase Validation",
        "",
        f"- Created: {payload['created_at']}",
        f"- Status: `{payload['status']}`",
        f"- Passed: {payload['passed']}",
        f"- Failed: {payload['failed']}",
        f"- Release status: `{payload['release_status']}`",
        "",
        "| Lane | Status | Blueprints | Failures |",
        "|---|---|---:|---|",
    ]
    for item in results:
        failures = ", ".join(f"`{failure}`" for failure in item["failures"]) or "none"
        lines.append(f"| {item['display_name']} | `{item['status']}` | {item['blueprint_count']} | {failures} |")
    lines.extend([
        "",
        "A pass means the Senior Phase route has CAPS bridges, Grade 7-9 blueprints, valid Bloom totals and subject source grammar.",
        "Release remains blocked until phase-specific source exemplars and educator approval are added.",
    ])
    out_md.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "passed": payload["passed"], "failed": payload["failed"]}, indent=2))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
