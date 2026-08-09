#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ONTOLOGY = ROOT / "deliverables" / "caps_assessment_ontology" / "caps_assessment_ontology.json"
DEFAULT_OUT = ROOT / "deliverables" / "caps_assessment_design"


SHELL_BY_FAMILY = {
    "foundation_activity_assessment": "activity_sheet",
    "practical_project_design_task": "project_task_sheet",
    "practical_performance_or_portfolio": "performance_task_sheet",
    "calculation_problem_solving": "question_paper",
    "data_diagram_practical_investigation": "investigation_task_sheet",
    "case_study_structured_questions": "structured_case_paper",
    "language_integrated_assessment": "language_integrated_task",
    "source_based_plus_extended_response": "source_response_paper",
    "source_based_plus_essay": "source_essay_paper",
    "structured_test_or_task": "question_paper",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def text_path_for_pdf(pdf_path: str) -> Path | None:
    path = Path(pdf_path)
    try:
        marker = path.parts.index("pdf")
    except ValueError:
        return None
    parts = list(path.parts)
    parts[marker] = "text"
    return Path(*parts).with_suffix(".txt")


def read_profile_text(profile: dict[str, Any]) -> str:
    chunks: list[str] = []
    for evidence in profile.get("supporting_caps_evidence") or []:
        text_path = text_path_for_pdf(str(evidence.get("path") or ""))
        if text_path and text_path.exists():
            chunks.append(text_path.read_text(encoding="utf-8", errors="ignore"))
    return "\n\n".join(chunks)


def compact(value: str, limit: int = 700) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    return value[:limit].rstrip()


def excerpt_near(text: str, patterns: list[str], limit: int = 900) -> list[str]:
    lower = text.lower()
    snippets: list[str] = []
    for pattern in patterns:
        idx = lower.find(pattern.lower())
        if idx >= 0:
            start = max(0, idx - 220)
            snippets.append(compact(text[start : start + limit], limit))
    seen: set[str] = set()
    deduped = []
    for snippet in snippets:
        key = snippet[:100]
        if key not in seen:
            seen.add(key)
            deduped.append(snippet)
    return deduped[:5]


def percent_after(text: str, label: str) -> int | None:
    match = re.search(label + r"[^0-9]{0,40}([0-9]{1,3})\s*%", text, flags=re.I)
    return int(match.group(1)) if match else None


def base_design(profile: dict[str, Any], text: str) -> dict[str, Any]:
    family = profile.get("assessment_family") or "structured_test_or_task"
    profile_id = profile.get("profile_id")
    design = {
        "profile_id": profile_id,
        "subject": profile.get("subject"),
        "phase": profile.get("phase"),
        "phase_group": profile.get("phase_group"),
        "assessment_family": family,
        "render_shell": SHELL_BY_FAMILY.get(family, "question_paper"),
        "confidence": "medium",
        "assessment_forms": [],
        "annual_weightings": {},
        "task_requirements": [],
        "paper_structure": [],
        "cognitive_distribution": profile.get("required_distribution") or {},
        "marking_instruments": ["memorandum", "rubric"],
        "generation_constraints": list(profile.get("generation_constraints") or []),
        "validation_rules": [
            "Choose the render shell from assessment design before rendering learner-facing material.",
            "Do not render practical performance tasks as written answer-question papers.",
            "Marks in the learner pack must reconcile with the assessment instrument.",
            "Keep educator approval as the final gate.",
        ],
        "supporting_evidence": excerpt_near(
            text,
            ["formal assessment", "programme of assessment", "minimum requirements", "cognitive levels", "assessment tasks"],
        ),
    }
    allowed = set(profile.get("allowed") or [])
    if "rubric_levels" in allowed and "rubric" not in design["marking_instruments"]:
        design["marking_instruments"].append("rubric")
    return design


def dance_design(profile: dict[str, Any], text: str) -> dict[str, Any]:
    design = base_design(profile, text)
    design.update(
        {
            "render_shell": "performance_task_sheet",
            "confidence": "high",
            "assessment_forms": [
                "theory_test",
                "practical_test",
                "practical_exam",
                "theory_exam",
                "research_assignment",
                "performance_assessment_task",
            ],
            "annual_weightings": {"sba": 25, "performance_assessment_tasks": 25, "final_examinations": 50},
            "task_requirements": [
                {"name": "Grade 10 PAT 1", "type": "composition_sequence", "term": 2, "marks": 50},
                {"name": "Grade 10 PAT 2", "type": "indigenous_or_cross_cultural_dance", "term": 3, "marks": 50},
                {"name": "Grade 10/11 practical exam", "type": "practical_performance", "marks": 100},
                {"name": "Grade 10/11 theory exam", "type": "written_theory", "marks": 100},
            ],
            "paper_structure": [
                {"name": "Theory Paper 1", "marks": 100, "time": "3 hours"},
                {"name": "Safe dance practice and health care", "marks": 40},
                {"name": "Dance history and literacy", "marks": 60},
                {"name": "Practical instrument", "components": [{"set_class": 50}, {"solo": 30}, {"improvisation": 20}], "marks": 100},
            ],
            "cognitive_distribution": {"lower_order_knowledge": 30, "middle_order_application": 50, "higher_order_analysis_evaluation_creativity": 20},
            "marking_instruments": ["performance_rubric", "teacher_observation_record", "moderation_evidence", "memorandum_for_theory_only"],
            "generation_constraints": [
                "For PATs and practical exams, render an assessment instrument with task brief, conditions, observable criteria, and rubric.",
                "Do not present physical performance requirements as answer-line questions.",
                "Use written question-paper structure only for Dance theory papers.",
                "Film or retain evidence where the educator requires moderation support.",
            ],
        }
    )
    design["supporting_evidence"] = excerpt_near(
        text,
        ["SBA 25", "PAT 1: Composition", "the theory examination must cater", "Dance Studies Paper 1 Marks", "PAT TASK"],
        1000,
    )
    return design


def mathematics_design(profile: dict[str, Any], text: str) -> dict[str, Any]:
    design = base_design(profile, text)
    phase_group = profile.get("phase_group")
    if phase_group == "intermediate":
        design.update(
            {
                "render_shell": "question_paper",
                "confidence": "high",
                "assessment_forms": ["test", "examination", "project", "assignment", "investigation"],
                "annual_weightings": {"school_based_assessment": 75, "end_of_year_examination": 25},
                "task_requirements": [
                    {"name": "tests", "minimum_per_year": 3},
                    {"name": "examinations", "minimum_per_year": 2},
                    {"name": "assignments", "minimum_per_year": 2},
                    {"name": "investigation", "minimum_per_year": 1},
                    {"name": "project", "minimum_per_year": 1},
                ],
                "cognitive_distribution": {"knowledge": 25, "routine_procedures": 45, "complex_procedures": 20, "problem_solving": 10},
                "marking_instruments": ["memorandum", "rubric_for_projects_or_investigations"],
                "generation_constraints": [
                    "For tests and exams, use concise calculation/problem-solving items with method marks.",
                    "For projects and investigations, use a task sheet plus rubric, not a generic written exam.",
                    "Do not turn calculation assessment into essay assessment.",
                ],
            }
        )
        design["supporting_evidence"] = excerpt_near(
            text,
            ["Minimum requirements for formal assessment", "SBA component may take various forms", "cognitive levels", "contributes 75"],
            1000,
        )
    elif phase_group == "foundation":
        design.update(
            {
                "render_shell": "activity_sheet",
                "confidence": "high",
                "assessment_forms": ["teacher_observation", "oral_prompt", "concrete_activity", "short_recorded_response"],
                "marking_instruments": ["teacher_observation_checklist", "simple_memo"],
                "generation_constraints": [
                    "Use teacher-led observable activities and concrete prompts.",
                    "Keep learner reading load low.",
                    "Use short recorded responses only where age-appropriate.",
                ],
            }
        )
    return design


def coding_robotics_design(profile: dict[str, Any], text: str) -> dict[str, Any]:
    design = base_design(profile, text)
    design.update(
        {
            "render_shell": "project_task_sheet",
            "confidence": "medium",
            "assessment_forms": ["practical_task", "design_project", "structured_theory", "oral_explanation", "portfolio_evidence"],
            "marking_instruments": ["project_rubric", "design_log", "test_log", "teacher_observation_record"],
            "generation_constraints": [
                "State design challenge, constraints, materials, safety, deliverables, and testing evidence.",
                "Use questions only for theory or reflection sub-parts.",
                "Require a rubric and visible evidence log for the educator.",
            ],
        }
    )
    design["supporting_evidence"] = excerpt_near(
        text,
        ["Minimum formal assessment requirements for Coding and Robotics", "assessment", "practical", "project"],
        1000,
    )
    return design


def refine_design(profile: dict[str, Any]) -> dict[str, Any]:
    text = read_profile_text(profile)
    profile_id = str(profile.get("profile_id") or "")
    subject = str(profile.get("subject") or "")
    if profile_id == "fet.dance_studies" or subject == "Dance Studies":
        return dance_design(profile, text)
    if subject == "Mathematics":
        return mathematics_design(profile, text)
    if subject == "Coding and Robotics":
        return coding_robotics_design(profile, text)
    return base_design(profile, text)


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# CAPS Assessment Design Profiles",
        "",
        f"Created: {payload['created_at']}",
        "",
        "This layer converts canonical subject/phase profiles into assessment-design rules: valid assessment forms, mark weightings, render shells, and validation constraints. It sits between CAPS evidence and generation.",
        "",
        "## Summary",
        "",
        f"- Profiles analysed: {payload['profile_count']}",
        f"- Render shells: {', '.join(f'{k}={v}' for k, v in payload['render_shell_counts'].items())}",
        f"- Confidence: {', '.join(f'{k}={v}' for k, v in payload['confidence_counts'].items())}",
        "",
        "## High-Confidence Examples",
        "",
    ]
    for profile_id in ["fet.dance_studies", "intermediate.mathematics", "foundation.mathematics", "intermediate.coding_and_robotics"]:
        design = payload["profiles_by_id"].get(profile_id)
        if not design:
            continue
        lines.extend(
            [
                f"### {profile_id}",
                "",
                f"- Subject: {design['subject']}",
                f"- Shell: `{design['render_shell']}`",
                f"- Forms: {', '.join(design['assessment_forms'])}",
                f"- Weightings: {', '.join(f'{k}={v}%' for k, v in design['annual_weightings'].items()) or 'profile-specific / educator-set'}",
                f"- Cognitive distribution: {', '.join(f'{k}={v}%' for k, v in design['cognitive_distribution'].items()) or 'not extracted'}",
                "",
            ]
        )
    lines.extend(
        [
            "## Gate Rule",
            "",
            "PDF keyword evidence may suggest possible signals, but learner-facing packs must follow this assessment-design shell before rendering. Practical performance tasks are rendered as assessment instruments, not answer-line question papers.",
        ]
    )
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build CAPS assessment-design profiles from canonical ontology.")
    parser.add_argument("--ontology", default=str(DEFAULT_ONTOLOGY))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    ontology_path = Path(args.ontology).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    ontology = json.loads(ontology_path.read_text(encoding="utf-8"))
    designs = [refine_design(profile) for profile in ontology.get("profiles", [])]
    payload = {
        "schema": "knowedge.caps_assessment_design.v1",
        "created_at": utc_now(),
        "source_ontology": str(ontology_path),
        "profile_count": len(designs),
        "render_shell_counts": dict(Counter(design["render_shell"] for design in designs)),
        "confidence_counts": dict(Counter(design["confidence"] for design in designs)),
        "profiles": designs,
        "profiles_by_id": {design["profile_id"]: design for design in designs},
    }
    (out_dir / "caps_assessment_design.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_markdown(out_dir / "CAPS_ASSESSMENT_DESIGN.md", payload)
    print(json.dumps({"status": "completed", "profiles": len(designs), "out": str(out_dir)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
