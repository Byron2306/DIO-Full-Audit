#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX = ROOT / "deliverables" / "homs_caps_term_visual_content_matrix" / "HOMS_CAPS_TERM_VISUAL_CONTENT_MATRIX.json"
DEFAULT_OUT = ROOT / "deliverables" / "homs_caps_term_visual_content_matrix"
FET_PHASE = "fet_grade_10_12"


EXPECTED_VISUALS = {
    "calculation_problem_solving": {"working_grid"},
    "case_study_structured_questions": {"case_table"},
    "data_diagram_practical_investigation": {"investigation_sheet"},
    "language_integrated_assessment": {"language_planner"},
    "practical_project_design_task": {"design_log"},
    "practical_performance_or_portfolio": {"performance_map", "rubric_observation_table"},
    "source_based_plus_essay": {"source_extract", "evidence_table", "map_extract", "data_table"},
    "source_based_plus_extended_response": {"source_extract", "evidence_table", "map_extract", "data_table"},
}

EXPECTED_SHELLS = {
    "calculation_problem_solving": "question_paper",
    "case_study_structured_questions": "structured_case_paper",
    "data_diagram_practical_investigation": "investigation_task_sheet",
    "language_integrated_assessment": "language_integrated_task",
    "practical_project_design_task": "project_task_sheet",
    "practical_performance_or_portfolio": "performance_task_sheet",
    "source_based_plus_essay": "source_essay_paper",
    "source_based_plus_extended_response": "source_response_paper",
}

SOURCE_TYPE_VISUALS = {
    "map_extract": {"map_extract"},
    "data_table": {"data_table", "axis_diagram", "investigation_sheet"},
    "source_extract": {"source_extract", "map_extract"},
    "visual_source": {"source_extract", "map_extract"},
    "evidence_table": {"evidence_table", "map_extract", "data_table"},
    "case_file": {"case_table"},
    "investigation_sheet": {"investigation_sheet"},
    "calculation_workspace": {"working_grid", "axis_diagram"},
    "performance_observation": {"performance_map", "rubric_observation_table"},
    "portfolio_evidence": {"performance_map", "rubric_observation_table"},
    "design_brief": {"design_log"},
    "diagram": {"axis_diagram", "data_table", "investigation_sheet", "design_log"},
    "language_text": {"language_planner", "source_extract"},
}

QUESTION_CONTRACT = {
    "calculation_problem_solving": {
        "must_do": ["calculate", "solve", "plot", "show working", "justify"],
        "needs": ["numeric data", "workspace", "method marks"],
    },
    "case_study_structured_questions": {
        "must_do": ["identify", "explain", "recommend", "justify"],
        "needs": ["case facts", "stakeholders", "decision evidence"],
    },
    "data_diagram_practical_investigation": {
        "must_do": ["record", "compare", "analyse", "conclude"],
        "needs": ["aim", "variables", "observations", "data"],
    },
    "language_integrated_assessment": {
        "must_do": ["read", "view", "plan", "draft", "edit"],
        "needs": ["text panel", "planner", "language features"],
    },
    "practical_project_design_task": {
        "must_do": ["design", "build", "test", "improve"],
        "needs": ["constraints", "prototype evidence", "test record"],
    },
    "practical_performance_or_portfolio": {
        "must_do": ["prepare", "perform", "present", "reflect"],
        "needs": ["performance map", "observation rubric", "portfolio evidence"],
    },
    "source_based_plus_essay": {
        "must_do": ["interpret", "compare", "argue", "cite evidence"],
        "needs": ["source extract", "evidence table", "extended response prompt"],
    },
    "source_based_plus_extended_response": {
        "must_do": ["identify", "describe", "explain", "infer", "cite evidence"],
        "needs": ["source extract", "map or table", "evidence table"],
    },
}

GENERIC_OR_ADMIN_RE = re.compile(
    r"("
    r"grades?\s+10\s*[-–]\s*12|"
    r"national curriculum|curriculum and assessment|policy statement|"
    r"programme of assessment|formal assessment|informal assessment|"
    r"recording and reporting|moderation|time allocation|"
    r"summary of annual teaching plan|annual teaching plan|content outline|"
    r"topic:\s*time|additional resources|suggested contact time|"
    r"resources:\s*$|implementation date|"
    r"practical assessment task|pat\s*\(|practical phase|"
    r"\bpat\s+\d|"
    r"suggested practicals and investigations|"
    r"prescribed practical activities|recommended practical activities|"
    r"weighting of topics|"
    r"revision|examination|exam preparation|written exams?|"
    r"learners aim to|"
    r"covered in grades?\s+10\s*,?\s+11\s+and\s+12|"
    r"subject contains the following|"
    r"teachers could introduce|"
    r"teaching time|textbook|newspaper articles|"
    r"cost for practical tasks|practical work and the theory for practical work|"
    r"editorial|kindly requested|"
    r"there are several practical activities|"
    r"suggested drama play script list|"
    r"appropriate visual arts terminology|"
    r"exclusive but are interrelated"
    r")",
    re.IGNORECASE,
)

RESOURCE_RE = re.compile(r"(https?://|www\.|\.org|\.html|isbn|textbook)", re.IGNORECASE)
CONTENT_HINT_RE = re.compile(
    r"("
    r"source|case|scenario|map|graph|table|diagram|data|investigation|experiment|"
    r"calculate|finance|measurement|probability|function|algebra|geometry|"
    r"weather|climate|synoptic|settlement|population|river|plate|tectonic|economic geography|"
    r"revolution|apartheid|war|nationalism|civil society|"
    r"cells|genetics|evolution|photosynthesis|biodiversity|"
    r"market|demand|supply|inflation|budget|ledger|journal|vat|inventory|"
    r"reading|viewing|writing|presenting|language structures|comprehension|"
    r"performance|composition|choreography|improvisation|portfolio|"
    r"design|prototype|constraints|materials|systems|control"
    r")",
    re.IGNORECASE,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean(value: str, limit: int = 220) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit].rstrip()


def has_bad_text(lines: list[str]) -> bool:
    blob = "\n".join(clean(line, 500) for line in lines if line)
    if not blob:
        return True
    return bool(GENERIC_OR_ADMIN_RE.search(blob) or RESOURCE_RE.search(blob))


def content_is_specific(lines: list[str]) -> bool:
    useful = [clean(line) for line in lines if clean(line)]
    if len(useful) < 2:
        return False
    long_enough = sum(1 for line in useful if len(line) >= 24)
    hinted = sum(1 for line in useful if CONTENT_HINT_RE.search(line))
    return long_enough >= 2 and hinted >= 1


def grade_or_term_leaks(row: dict[str, Any], lines: list[str]) -> list[str]:
    reasons: list[str] = []
    grade = int(row.get("grade") or 0)
    term = int(row.get("term") or 0)
    blob = "\n".join(clean(line, 500) for line in lines if line)
    grade_hits = {int(match) for match in re.findall(r"\bgrade\s+(10|11|12)\b", blob, flags=re.IGNORECASE)}
    wrong_grades = sorted(item for item in grade_hits if item != grade)
    if wrong_grades:
        reasons.append(f"content references other FET grade(s): {wrong_grades}")
    term_hits = {int(match) for match in re.findall(r"\bterm\s+([1-4])\b", blob, flags=re.IGNORECASE)}
    wrong_terms = sorted(item for item in term_hits if item != term)
    if wrong_terms:
        reasons.append(f"content references other term(s): {wrong_terms}")
    return reasons


def visual_alignment(row: dict[str, Any]) -> tuple[bool, list[str]]:
    family = str(row.get("assessment_family") or "")
    kinds = {str(item) for item in row.get("visual_kinds") or [] if item}
    expected = EXPECTED_VISUALS.get(family, set())
    reasons: list[str] = []
    if not kinds:
        reasons.append("no planned visual kinds")
    elif expected and not (kinds & expected):
        reasons.append(f"visual kind mismatch: expected one of {sorted(expected)}, got {sorted(kinds)}")
    for source_type in row.get("source_types") or (row.get("source_type_contract") or {}).get("source_types") or []:
        accepted = SOURCE_TYPE_VISUALS.get(str(source_type), set())
        if accepted and not (kinds & accepted):
            reasons.append(f"source type {source_type} is not satisfied by visuals {sorted(kinds)}")
    if family.startswith("source_based") and "geography" in str(row.get("subject") or "").lower():
        if not ({"map_extract", "data_table"} & kinds):
            reasons.append("geography source paper has no map/data stimulus")
    if family == "practical_performance_or_portfolio" and not {"performance_map", "rubric_observation_table"}.issubset(kinds):
        reasons.append("performance pack needs both performance map and rubric observation table")
    return not reasons, reasons


def shell_alignment(row: dict[str, Any]) -> tuple[bool, list[str]]:
    family = str(row.get("assessment_family") or "")
    expected = EXPECTED_SHELLS.get(family)
    actual = str(row.get("render_shell") or "")
    if expected and actual != expected:
        return False, [f"paper shell mismatch: expected {expected}, got {actual or 'missing'}"]
    return True, []


def duplicate_topic_notes(rows: list[dict[str, Any]]) -> dict[tuple[str, int, str], int]:
    groups: dict[tuple[str, int, str], set[int]] = defaultdict(set)
    for row in rows:
        topic = clean((row.get("topic_focus") or [""])[0]).lower()
        if topic:
            groups[(str(row.get("profile_id")), int(row.get("term") or 0), topic)].add(int(row.get("grade") or 0))
    return {key: len(grades) for key, grades in groups.items() if len(grades) >= 3}


def audit_row(row: dict[str, Any], duplicate_topics: dict[tuple[str, int, str], int]) -> dict[str, Any]:
    reasons: list[str] = []
    warnings: list[str] = []
    family = str(row.get("assessment_family") or "")
    topic_focus = [clean(line) for line in row.get("topic_focus") or [] if clean(line)]
    content_lines = [clean(line) for line in row.get("content_lines") or [] if clean(line)]
    source_types = list(row.get("source_types") or (row.get("source_type_contract") or {}).get("source_types") or [])
    all_content = topic_focus + content_lines

    if row.get("phase") != FET_PHASE:
        reasons.append("not FET")
    if row.get("status") != "content_ready" or not row.get("render_eligible"):
        reasons.append(f"not content-ready: {row.get('status')}")
    if int(row.get("candidate_count") or 0) <= 0:
        reasons.append("no CAPS source candidate")
    if row.get("extraction_error"):
        reasons.append(f"CAPS extraction failed: {row.get('extraction_error')}")
    if row.get("theme_confidence") != "high":
        reasons.append(f"theme confidence is {row.get('theme_confidence')}, not high")
    if not content_is_specific(content_lines):
        reasons.append("content lines are too thin for meaningful questions")
    if has_bad_text(all_content):
        reasons.append("topic/content contains admin, revision, exam, resource, or generic phase noise")
    reasons.extend(grade_or_term_leaks(row, all_content))

    visual_ok, visual_reasons = visual_alignment(row)
    if not visual_ok:
        reasons.extend(visual_reasons)
    shell_ok, shell_reasons = shell_alignment(row)
    if not shell_ok:
        reasons.extend(shell_reasons)

    topic_key = (
        str(row.get("profile_id")),
        int(row.get("term") or 0),
        clean(topic_focus[0] if topic_focus else "").lower(),
    )
    if duplicate_topics.get(topic_key, 0) >= 3:
        reasons.append("same first topic reused across all FET grades for this term; grade specificity is not stable")

    if family in {"practical_performance_or_portfolio", "practical_project_design_task"}:
        warnings.append("requires educator review of observable/practical evidence before classroom use")
    if family == "language_integrated_assessment":
        warnings.append("requires approved source text before final paper release")

    stable = not reasons
    contract = QUESTION_CONTRACT.get(family, {"must_do": ["answer"], "needs": ["subject evidence"]})
    return {
        "profile_id": row.get("profile_id"),
        "subject": row.get("subject"),
        "grade": row.get("grade"),
        "term": row.get("term"),
        "assessment_family": family,
        "render_shell": row.get("render_shell"),
        "stable": stable,
        "decision": "render_candidate" if stable else "curate_before_render",
        "reasons": reasons,
        "warnings": warnings,
        "topic_focus": topic_focus[:4],
        "content_lines": content_lines[:6],
        "source_types": source_types,
        "source_type_contract": row.get("source_type_contract") or {},
        "visual_kinds": row.get("visual_kinds") or [],
        "required_visuals": row.get("required_visuals") or [],
        "paper_contract": {
            "question_behaviour": contract["must_do"],
            "stimulus_must_provide": contract["needs"],
            "educator_approval_required": True,
        },
        "caps_source": row.get("caps_source"),
        "caps_path": row.get("caps_path"),
    }


def group_counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "unknown") for row in rows).items()))


def is_near_stable(row: dict[str, Any]) -> bool:
    critical_fragments = [
        "not content-ready",
        "theme confidence is low",
        "no CAPS source",
        "CAPS extraction failed",
        "visual kind mismatch",
        "paper shell mismatch",
        "no planned visual kinds",
    ]
    reasons = [str(reason) for reason in row.get("reasons") or []]
    if any(any(fragment in reason for fragment in critical_fragments) for reason in reasons):
        return False
    return len(reasons) <= 3 and bool(row.get("content_lines")) and bool(row.get("visual_kinds"))


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    stable = payload["stable_rows"]
    near_stable = payload["near_stable_rows"]
    unstable = payload["unstable_rows"]
    reason_counts = payload["reason_counts"]
    lines = [
        "# HOMS FET Stable Pack Audit",
        "",
        f"Created: {payload['created_at']}",
        f"FET rows audited: {payload['fet_rows_audited']}",
        f"Stable render candidates: {payload['stable_count']}",
        f"Near-stable curation candidates: {payload['near_stable_count']}",
        f"Curate before render: {payload['unstable_count']}",
        "",
        "## Stable Means",
        "",
        "- FET only: Grades 10-12.",
        "- CAPS source exists and extraction did not fail.",
        "- Theme confidence is high with at least two content-bearing lines.",
        "- Topic/content is not generic CAPS admin, revision, exam-prep, resource-only, or phase-header text.",
        "- Visual kind matches the assessment family.",
        "- Paper shell can ask questions that actually use the planned stimulus.",
        "- Educator approval remains required before real classroom use.",
        "",
        "## Top Failure Reasons",
    ]
    for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))[:18]:
        lines.append(f"- {count}: {reason}")

    lines.extend(["", "## Stable Candidates By Subject"])
    for subject, count in sorted(payload["stable_by_subject"].items()):
        lines.append(f"- {subject}: {count}")

    lines.extend(["", "## First Stable Candidates"])
    for row in stable[:40]:
        topic = row["topic_focus"][0] if row["topic_focus"] else "no topic"
        lines.append(f"- {row['profile_id']} / Grade {row['grade']} / Term {row['term']} / {row['assessment_family']}: {topic}")

    lines.extend(["", "## Near-Stable Curation Queue"])
    for row in near_stable[:40]:
        topic = row["topic_focus"][0] if row["topic_focus"] else "no topic"
        reason = "; ".join(row["reasons"][:3])
        lines.append(f"- {row['profile_id']} / Grade {row['grade']} / Term {row['term']} / {row['assessment_family']}: {topic} -- {reason}")

    lines.extend(["", "## First Curate-Before-Render Rows"])
    for row in unstable[:60]:
        topic = row["topic_focus"][0] if row["topic_focus"] else "no topic"
        reason = "; ".join(row["reasons"][:3])
        lines.append(f"- {row['profile_id']} / Grade {row['grade']} / Term {row['term']}: {topic} -- {reason}")

    lines.extend(
        [
            "",
            "## Next Build Rule",
            "",
            "Only rows in `fet_stable_rows.json` should be rendered into reusable visual asset packs.",
            "Rows in `fet_unstable_rows.json` need a curated subject+grade+term profile or better CAPS section anchoring first.",
        ]
    )
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit CAPS visual matrix rows and produce FET-only stable render candidates.")
    parser.add_argument("--matrix", default=str(DEFAULT_MATRIX))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    matrix_path = Path(args.matrix).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    payload = json.loads(matrix_path.read_text(encoding="utf-8"))
    fet_rows = [row for row in payload.get("rows") or [] if row.get("phase") == FET_PHASE]
    duplicate_topics = duplicate_topic_notes(fet_rows)
    audited = [audit_row(row, duplicate_topics) for row in fet_rows]
    stable = [row for row in audited if row["stable"]]
    unstable = [row for row in audited if not row["stable"]]
    near_stable = [row for row in unstable if is_near_stable(row)]

    reason_counts = Counter(reason for row in unstable for reason in row["reasons"])
    render_manifest = [
        {
            "profile_id": row["profile_id"],
            "subject": row["subject"],
            "grade": row["grade"],
            "term": row["term"],
            "assessment_family": row["assessment_family"],
            "visual_kinds": row["visual_kinds"],
            "topic_focus": row["topic_focus"],
        }
        for row in stable
    ]
    audit_payload = {
        "schema": "knowedge.homs_fet_stable_pack_audit.v1",
        "created_at": utc_now(),
        "source_matrix": str(matrix_path),
        "fet_rows_audited": len(fet_rows),
        "stable_count": len(stable),
        "near_stable_count": len(near_stable),
        "unstable_count": len(unstable),
        "stable_by_subject": group_counts(stable, "subject"),
        "near_stable_by_subject": group_counts(near_stable, "subject"),
        "unstable_by_subject": group_counts(unstable, "subject"),
        "stable_by_family": group_counts(stable, "assessment_family"),
        "near_stable_by_family": group_counts(near_stable, "assessment_family"),
        "unstable_by_family": group_counts(unstable, "assessment_family"),
        "reason_counts": dict(sorted(reason_counts.items())),
        "stable_rows": stable,
        "near_stable_rows": near_stable,
        "unstable_rows": unstable,
        "render_manifest": render_manifest,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "FET_STABLE_PACK_AUDIT.json").write_text(json.dumps(audit_payload, indent=2), encoding="utf-8")
    (out_dir / "fet_stable_rows.json").write_text(json.dumps(stable, indent=2), encoding="utf-8")
    (out_dir / "fet_near_stable_rows.json").write_text(json.dumps(near_stable, indent=2), encoding="utf-8")
    (out_dir / "fet_unstable_rows.json").write_text(json.dumps(unstable, indent=2), encoding="utf-8")
    (out_dir / "fet_stable_render_manifest.json").write_text(json.dumps(render_manifest, indent=2), encoding="utf-8")
    write_markdown(out_dir / "FET_STABLE_PACK_AUDIT.md", audit_payload)

    print(
        json.dumps(
            {
                "status": "completed",
                "fet_rows_audited": len(fet_rows),
                "stable_count": len(stable),
                "near_stable_count": len(near_stable),
                "unstable_count": len(unstable),
                "out": str(out_dir / "FET_STABLE_PACK_AUDIT.json"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
