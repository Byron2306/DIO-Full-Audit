#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BANK = ROOT / "deliverables" / "homs_core_source_bank_curated" / "HOMS_CORE_SOURCE_BANK_CURATED.json"
DEFAULT_OUT = ROOT / "deliverables" / "homs_senior_phase_spine"


BLOOM_BY_GRADE = {
    7: {
        "remember": 20,
        "understand": 30,
        "apply": 30,
        "analyse": 15,
        "evaluate": 5,
        "create": 0,
        "stance": "high scaffold, short sources, explicit steps, limited open-ended judgement",
    },
    8: {
        "remember": 15,
        "understand": 25,
        "apply": 30,
        "analyse": 20,
        "evaluate": 8,
        "create": 2,
        "stance": "moderate scaffold, longer source handling, early comparison and justified choices",
    },
    9: {
        "remember": 10,
        "understand": 20,
        "apply": 30,
        "analyse": 25,
        "evaluate": 10,
        "create": 5,
        "stance": "transition to FET, multi-step reasoning, short controlled extended responses",
    },
}

BLOOM_VERBS = {
    "remember": ["name", "list", "identify", "define", "match"],
    "understand": ["describe", "summarise", "explain", "classify", "give a reason"],
    "apply": ["use", "calculate", "complete", "draw", "solve", "show"],
    "analyse": ["compare", "distinguish", "organise", "interpret", "find the pattern"],
    "evaluate": ["justify", "recommend", "decide", "assess with evidence"],
    "create": ["design", "plan", "produce", "write a short response"],
}

PROMPT_SHAPES = {
    "remember": "Identify or name key facts from a Grade {grade} {subject} stimulus or task.",
    "understand": "Describe or explain the meaning of evidence in a Grade {grade} {subject} stimulus or task.",
    "apply": "Use supplied values, evidence or concepts to complete a Grade {grade} {subject} task.",
    "analyse": "Compare, sort or interpret parts of a Grade {grade} {subject} stimulus or task.",
    "evaluate": "Justify a short conclusion using evidence from a Grade {grade} {subject} stimulus or task.",
    "create": "Plan or produce a short Grade {grade} {subject} response from the supplied brief.",
}

SUBJECTS = [
    {
        "subject_id": "english_language",
        "display_name": "English Language",
        "senior_subject": "English Home Language / First Additional Language",
        "caps_bridge": [
            "corpora/caps/pdf/senior_grade_7_9/caps_sp_hl_english_gr_7-9_web.pdf",
            "corpora/caps/pdf/senior_grade_7_9/caps_sp_fal_english_gr_7-9_web.pdf",
        ],
        "assessment_family": "language_integrated_assessment",
        "source_grammar": ["text_extract", "cartoon", "photograph_or_image", "data_table"],
        "grade_focus": {
            7: "short comprehension, vocabulary in context, paragraph writing and simple visual literacy",
            8: "multi-paragraph comprehension, language-in-context, summary and guided transactional writing",
            9: "FET bridge: comprehension, visual literacy, language structures and controlled extended writing",
        },
        "sections": ["reading_viewing", "language_structures", "writing_presenting"],
    },
    {
        "subject_id": "afrikaans_language",
        "display_name": "Afrikaans Language",
        "senior_subject": "Afrikaans Home Language / First Additional Language",
        "caps_bridge": [
            "corpora/caps/pdf/senior_grade_7_9/caps_sp_home_afrikaans_gr_7-9_web.pdf",
            "corpora/caps/pdf/senior_grade_7_9/caps_sp_fal_afrikaans_gr_7-9_web.pdf",
        ],
        "assessment_family": "language_integrated_assessment",
        "source_grammar": ["text_extract", "cartoon", "photograph_or_image", "graph_or_chart"],
        "grade_focus": {
            7: "kort leesbegrip, woordeskat, eenvoudige visuele teks en paragraafskryf",
            8: "leesbegrip, taal-in-konteks, opsomming en begeleide transaksionele skryfwerk",
            9: "FET-brug: leesbegrip, visuele geletterdheid, taalstrukture en beheerde skryfwerk",
        },
        "sections": ["lees_en_kyk", "taalstrukture", "skryf_en_aanbied"],
    },
    {
        "subject_id": "mathematics",
        "display_name": "Mathematics",
        "senior_subject": "Mathematics",
        "caps_bridge": ["corpora/caps/pdf/senior_grade_7_9/caps_sp_mathematics_gr_7-9.pdf"],
        "assessment_family": "calculation_problem_solving",
        "source_grammar": ["diagram_or_model", "graph_or_chart", "data_table", "number_line_or_grid"],
        "grade_focus": {
            7: "procedures, number operations, simple graphs, measurement and visible working",
            8: "multi-step procedures, algebraic reasoning, geometry and data handling",
            9: "FET bridge: algebra, functions, geometry, data and integrated problem solving",
        },
        "sections": ["short_procedures", "problem_solving", "data_geometry_or_measurement"],
    },
    {
        "subject_id": "life_orientation",
        "display_name": "Life Orientation",
        "senior_subject": "Life Orientation",
        "caps_bridge": ["corpora/caps/pdf/senior_grade_7_9/caps_sp_life_orientation_web.pdf"],
        "assessment_family": "practical_performance_or_portfolio",
        "source_grammar": ["scenario", "case_extract", "rubric_checklist", "reflection_prompt"],
        "grade_focus": {
            7: "personal wellbeing, relationships, study habits and guided reflection",
            8: "wellbeing, citizenship, decision-making and short scenario responses",
            9: "FET bridge: careers, rights, social responsibility and structured reflection",
        },
        "sections": ["scenario_response", "reflection", "educator_observation_rubric"],
    },
    {
        "subject_id": "life_sciences",
        "display_name": "Natural Sciences: Life And Living Strand",
        "senior_subject": "Natural Sciences",
        "caps_bridge": ["corpora/caps/pdf/senior_grade_7_9/caps_sp_natural_sciences_gr_7-9_web.pdf"],
        "assessment_family": "data_diagram_practical_investigation",
        "source_grammar": ["diagram_or_model", "data_table", "graph_or_chart", "investigation_sheet"],
        "grade_focus": {
            7: "classification, ecosystems, body systems and guided diagram interpretation",
            8: "cells, reproduction, ecology and simple practical investigation evidence",
            9: "FET bridge: life processes, systems, data interpretation and controlled investigation reasoning",
        },
        "sections": ["concepts", "diagram_or_data", "practical_investigation"],
    },
    {
        "subject_id": "physical_sciences",
        "display_name": "Natural Sciences: Matter, Energy, Planet Earth Strand",
        "senior_subject": "Natural Sciences",
        "caps_bridge": ["corpora/caps/pdf/senior_grade_7_9/caps_sp_natural_sciences_gr_7-9_web.pdf"],
        "assessment_family": "data_diagram_practical_investigation",
        "source_grammar": ["diagram_or_model", "data_table", "graph_or_chart", "calculation_values"],
        "grade_focus": {
            7: "materials, forces, energy and short observable investigation questions",
            8: "matter, reactions, electricity, energy transfer and data handling",
            9: "FET bridge: particles, chemical reactions, circuits, forces and graph-based reasoning",
        },
        "sections": ["concepts", "data_or_calculation", "practical_investigation"],
    },
    {
        "subject_id": "geography",
        "display_name": "Social Sciences: Geography",
        "senior_subject": "Social Sciences",
        "caps_bridge": ["corpora/caps/pdf/senior_grade_7_9/caps_sp_social_science_gr_7-9.pdf"],
        "assessment_family": "source_based_plus_extended_response",
        "source_grammar": ["map_extract", "photograph_or_image", "graph_or_chart", "data_table"],
        "grade_focus": {
            7: "basic maps, settlements, resources and direct source observation",
            8: "maps, climate, population and comparison of source evidence",
            9: "FET bridge: development, resource use, maps, data and short justified responses",
        },
        "sections": ["map_or_source_skills", "context_questions", "short_explanation"],
    },
    {
        "subject_id": "history",
        "display_name": "Social Sciences: History",
        "senior_subject": "Social Sciences",
        "caps_bridge": ["corpora/caps/pdf/senior_grade_7_9/caps_sp_social_science_gr_7-9.pdf"],
        "assessment_family": "source_based_plus_essay",
        "source_grammar": ["text_extract", "photograph_or_image", "cartoon", "timeline"],
        "grade_focus": {
            7: "sequence, cause and effect, simple source extraction and paragraph answers",
            8: "source comparison, perspective, cause and consequence and short evidence paragraphs",
            9: "FET bridge: reliability, usefulness, comparison and controlled extended paragraph response",
        },
        "sections": ["source_extraction", "source_comparison", "short_paragraph_response"],
    },
]

EXTENSIONS = [
    {
        "subject_id": "economics",
        "display_name": "EMS / Economics Extension",
        "senior_subject": "Economic and Management Sciences",
        "caps_bridge": ["corpora/caps/pdf/senior_grade_7_9/caps_sp_ems_web.pdf"],
        "reason": "Economics carries downward mainly through EMS in Grades 7-9, then becomes a FET elective.",
        "assessment_family": "case_study_structured_questions",
        "source_grammar": ["case_extract", "data_table", "graph_or_chart", "basic_accounting_record"],
    }
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def file_exists(path: str) -> bool:
    return (ROOT / path).exists()


def source_bank_counts() -> dict[str, int]:
    bank = load_json(DEFAULT_BANK)
    return dict(Counter(asset["subject_id"] for asset in bank.get("assets") or []))


def mark_allocation(grade: int) -> dict[str, int]:
    return {7: {"marks": 50, "duration_minutes": 60}, 8: {"marks": 60, "duration_minutes": 75}, 9: {"marks": 70, "duration_minutes": 90}}[grade]


def section_question(subject: dict[str, Any], grade: int, section: str, index: int) -> dict[str, Any]:
    bloom = BLOOM_BY_GRADE[grade]
    if index == 1:
        level = "remember" if grade == 7 else "understand"
    elif index == 2:
        level = "apply"
    else:
        level = "analyse" if grade < 9 else "evaluate"
    return {
        "number": f"{index}.1",
        "section": section,
        "bloom_level": level,
        "prompt_shape": PROMPT_SHAPES[level].format(grade=grade, subject=subject["display_name"]),
        "scaffold": scaffold_for(grade, level),
        "marks": 6 if index < 3 else 8,
    }


def scaffold_for(grade: int, level: str) -> list[str]:
    scaffolds = {
        7: ["single source or short task", "keywords supplied", "answer frame or labelled steps"],
        8: ["one or two linked sources", "guided comparison", "show evidence from the task"],
        9: ["two linked sources or multi-step task", "learner chooses relevant evidence", "short justified conclusion"],
    }
    if level in {"evaluate", "create"}:
        return scaffolds[grade] + ["educator-approved rubric required"]
    return scaffolds[grade]


def sample_blueprint(subject: dict[str, Any], grade: int) -> dict[str, Any]:
    allocation = mark_allocation(grade)
    return {
        "schema": "knowedge.homs_senior_phase_assessment_blueprint.v1",
        "subject_id": subject["subject_id"],
        "display_name": subject["display_name"],
        "senior_subject": subject["senior_subject"],
        "grade": grade,
        "phase": "senior_grade_7_9",
        "assessment_family": subject["assessment_family"],
        "marks": allocation["marks"],
        "duration_minutes": allocation["duration_minutes"],
        "bloom_distribution": BLOOM_BY_GRADE[grade],
        "source_grammar": subject["source_grammar"],
        "caps_focus": subject["grade_focus"][grade],
        "sections": [
            {
                "title": section,
                "questions": [section_question(subject, grade, section, index)]
            }
            for index, section in enumerate(subject["sections"], start=1)
        ],
        "generation_constraints": [
            "Use Senior Phase reading load and vocabulary, not FET wording.",
            "Keep each task answerable from the supplied stimulus, worked values or classroom content.",
            "Use Bloom distribution as a hard planning gate before generation.",
            "Require educator approval before learner use.",
        ],
    }


def build_payload() -> dict[str, Any]:
    bank_counts = source_bank_counts()
    subjects = []
    for subject in SUBJECTS:
        missing_caps = [path for path in subject["caps_bridge"] if not file_exists(path)]
        source_assets = bank_counts.get(subject["subject_id"], 0)
        status = "senior_blueprint_ready_release_blocked" if not missing_caps else "blocked_missing_senior_caps"
        subjects.append(
            {
                **subject,
                "status": status,
                "source_assets_from_fet_spine": source_assets,
                "missing_caps_bridge": missing_caps,
                "release_gate": "blocked_until_senior_phase_source_and_educator_review",
                "blueprints": [sample_blueprint(subject, grade) for grade in [7, 8, 9]],
            }
        )
    extensions = []
    for extension in EXTENSIONS:
        missing_caps = [path for path in extension["caps_bridge"] if not file_exists(path)]
        extensions.append({**extension, "status": "extension_ready" if not missing_caps else "blocked_missing_senior_caps", "missing_caps_bridge": missing_caps})
    return {
        "schema": "knowedge.homs_senior_phase_spine.v1",
        "created_at": utc_now(),
        "phase": "senior_grade_7_9",
        "principle": "Translate FET source grammar downward, but reduce cognitive load using grade-specific Bloom distributions and scaffolds.",
        "bloom_by_grade": BLOOM_BY_GRADE,
        "subjects": subjects,
        "extensions": extensions,
        "status_counts": dict(Counter(subject["status"] for subject in subjects)),
    }


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_blueprints(out_dir: Path, payload: dict[str, Any]) -> None:
    blueprint_dir = out_dir / "sample_blueprints"
    for subject in payload["subjects"]:
        for blueprint in subject["blueprints"]:
            path = blueprint_dir / subject["subject_id"] / f"grade_{blueprint['grade']}_blueprint.json"
            write_json(path, blueprint)


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# HOMS Senior Phase Spine",
        "",
        "This is the Grade 7-9 descent from the tight-8 FET spine. It keeps the source grammar but lowers cognitive complexity with explicit Bloom distributions and scaffolds.",
        "",
        f"- Created: {payload['created_at']}",
        f"- Status counts: " + ", ".join(f"`{key}`={value}" for key, value in payload["status_counts"].items()),
        "",
        "## Bloom Gate By Grade",
        "",
        "| Grade | Remember | Understand | Apply | Analyse | Evaluate | Create | Stance |",
        "|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for grade, bloom in payload["bloom_by_grade"].items():
        lines.append(
            f"| {grade} | {bloom['remember']} | {bloom['understand']} | {bloom['apply']} | {bloom['analyse']} | {bloom['evaluate']} | {bloom['create']} | {bloom['stance']} |"
        )
    lines.extend([
        "",
        "## Tight 8 Senior Phase Mapping",
        "",
        "| Lane | Senior Subject | Status | FET Source Assets | Missing CAPS | Grade 7 Focus | Grade 8 Focus | Grade 9 Focus |",
        "|---|---|---|---:|---|---|---|---|",
    ])
    for subject in payload["subjects"]:
        missing = ", ".join(f"`{item}`" for item in subject["missing_caps_bridge"]) or "none"
        lines.append(
            f"| {subject['display_name']} | {subject['senior_subject']} | `{subject['status']}` | {subject['source_assets_from_fet_spine']} | {missing} | {subject['grade_focus'][7]} | {subject['grade_focus'][8]} | {subject['grade_focus'][9]} |"
        )
    lines.extend([
        "",
        "## Assessment Descent Law",
        "",
        "- Grade 7: direct source reading, labelled diagrams, explicit calculation steps, short answers.",
        "- Grade 8: linked sources, guided comparison, short explanations and evidence selection.",
        "- Grade 9: FET bridge, multi-step reasoning, source comparison and short justified conclusions.",
        "- Full essays, open-ended synthesis and high-stakes judgement stay gated unless the subject route explicitly requires them.",
        "- Every generated pack remains blocked until senior-phase source review and educator approval are recorded.",
        "",
        "## Extension Lane",
        "",
    ])
    for extension in payload["extensions"]:
        missing = ", ".join(f"`{item}`" for item in extension["missing_caps_bridge"]) or "none"
        lines.append(f"- {extension['display_name']}: `{extension['status']}`; CAPS missing: {missing}; {extension['reason']}")
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    out_dir = DEFAULT_OUT
    write_json(out_dir / "HOMS_SENIOR_PHASE_SPINE.json", payload)
    write_blueprints(out_dir, payload)
    write_markdown(out_dir / "HOMS_SENIOR_PHASE_SPINE.md", payload)
    print(json.dumps({"status": "completed", "out_dir": str(out_dir), "subjects": len(payload["subjects"]), "status_counts": payload["status_counts"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
