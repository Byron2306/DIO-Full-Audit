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
DEFAULT_MATRIX = ROOT / "deliverables" / "caps_matrix_analysis" / "caps_matrix_analysis.json"
DEFAULT_OUT = ROOT / "deliverables" / "caps_assessment_ontology"
SIGNAL_FIELDS = [
    "signals_source_based",
    "signals_essay_or_extended_response",
    "signals_case_study",
    "signals_data_graph_diagram",
    "signals_practical_investigation",
    "signals_project_or_sba",
    "signals_oral_or_performance",
    "signals_calculation_problem",
    "signals_formal_test_or_exam",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "_", value.strip().lower())
    return re.sub(r"_+", "_", value).strip("_") or "unknown"


def phase_group(phase: str) -> str:
    return {
        "foundation_grade_r_3": "foundation",
        "intermediate_grade_4_6": "intermediate",
        "senior_grade_7_9": "senior",
        "fet_grade_10_12": "fet",
    }.get(phase, phase or "unknown")


def phase_grades(phase: str) -> list[int]:
    return {
        "foundation_grade_r_3": [1, 2, 3],
        "intermediate_grade_4_6": [4, 5, 6],
        "senior_grade_7_9": [7, 8, 9],
        "fet_grade_10_12": [10, 11, 12],
    }.get(phase, [])


def language_from_text(text: str) -> str | None:
    languages = [
        ("Afrikaans", ["afrikaans"]),
        ("English", ["english"]),
        ("isiNdebele", ["isindebele"]),
        ("isiXhosa", ["isixhosa"]),
        ("isiZulu", ["isizulu"]),
        ("Sepedi", ["sepedi"]),
        ("Sesotho", ["sesotho"]),
        ("Setswana", ["setswana"]),
        ("Siswati", ["siswati"]),
        ("Tshivenda", ["tshivenda", "venda"]),
        ("Xitsonga", ["xitsonga"]),
        ("French", ["french"]),
        ("German", ["german"]),
        ("Mandarin", ["mandarin"]),
        ("Serbian", ["serbian"]),
        ("South African Sign Language", ["sasignlanguage", "sign language"]),
    ]
    for language, hints in languages:
        if any(hint in text for hint in hints):
            return language
    return None


def canonical_subject(row: dict[str, Any]) -> tuple[str, str, str | None]:
    haystack = norm(f"{Path(row.get('path') or '').name} {row.get('title') or ''}")
    language = language_from_text(haystack)

    if language == "South African Sign Language":
        return "South African Sign Language", "language", language

    rules: list[tuple[str, str, list[str]]] = [
        ("Technical Mathematics", "mathematics", ["technical mathematics", "tegniese wiskunde"]),
        ("Mathematical Literacy", "mathematics", ["mathematical literacy", "maths literacy"]),
        ("Mathematics", "mathematics", ["maths", "mathematics", "wiskunde"]),
        ("Natural Sciences and Technology", "science", ["natural sciences technology", "natural_sciences_technology", "natuurwetenskappe en tegnologie"]),
        ("Natural Sciences", "science", ["natural science", "natural sciences", "natuurwetenskappe"]),
        ("Physical Sciences", "science", ["physical science", "physical sciences", "fisiese wetenskap"]),
        ("Life Sciences", "science", ["life sciences", "lewenswetenskappe"]),
        ("Marine Sciences", "science", ["marine sciences"]),
        ("Technical Sciences", "science", ["technical sciences", "tegniese wetenskappe"]),
        ("Nautical Science", "science", ["nautical science"]),
        ("Sport and Exercise Science", "science", ["sport and exercise science"]),
        ("Equine Studies", "science", ["equine studies", "perdestudie"]),
        ("Agricultural Sciences", "science", ["agricultural science", "landbouwetenskappe"]),
        ("Agricultural Management Practices", "commerce", ["agri management practices", "agricultural management practices", "landboubestuurspraktyk"]),
        ("Accounting", "commerce", ["accounting", "rekeningkunde"]),
        ("Business Studies", "commerce", ["business studies", "besigheidstudies", "besigheid studies"]),
        ("Economics", "commerce", ["economics", "ekonomie"]),
        ("Economic and Management Sciences", "commerce", ["ems", "economics management", "ekonomiese en bestuurs"]),
        ("Consumer Studies", "commerce", ["consumer studies"]),
        ("Tourism", "commerce", ["tourism", "toerisme"]),
        ("Hospitality Studies", "commerce", ["hospitality studies", "gasvryheid"]),
        ("History", "social_sciences", ["history", "geskiedenis"]),
        ("Geography", "social_sciences", ["geography", "geografie"]),
        ("Religion Studies", "social_sciences", ["religion studies", "religie studies", "religiestudies"]),
        ("Social Sciences", "social_sciences", ["social sciences", "social science"]),
        ("Life Skills", "life_skills", ["life skills", "lewensvaardighede"]),
        ("Life Orientation", "life_skills", ["life orientation", "lewensorientering"]),
        ("Coding and Robotics", "technology", ["coding and robotics"]),
        ("Technology", "technology", ["technology", "tegnologie"]),
        ("Computer Applications Technology", "technology", ["computer applications technology", "rekenaartoepassingtegnologie"]),
        ("Information Technology", "technology", ["information technology", "inligtingstegnologie"]),
        ("Engineering Graphics and Design", "technology", ["engineering graphics", "ingenieursgrafika"]),
        ("Civil Technology", "technology", ["civil technology", "siviele tegnologie"]),
        ("Electrical Technology", "technology", ["electrical technology", "elektriese tegnologie"]),
        ("Mechanical Technology", "technology", ["mechanical technology", "meganiese tegnologie"]),
        ("Agricultural Technology", "technology", ["agricultural technology", "landboutegnologie"]),
        ("Visual Arts", "arts", ["visual arts", "visuele kunste"]),
        ("Creative Arts", "arts", ["creative arts", "skeppende kunste"]),
        ("Dramatic Arts", "arts", ["dramatic arts", "dramatiese kunste"]),
        ("Dance Studies", "arts", ["dance studies"]),
        ("Design Studies", "arts", ["design studies", "ontwerp"]),
        ("Music", "arts", ["music", "musiek"]),
    ]
    for subject, family, hints in rules:
        if any(norm(hint) in haystack for hint in hints):
            return subject, family, language

    title = str(row.get("title") or "").strip()
    detected_language = language or row.get("language_guess")
    if detected_language and title and norm(title) == norm(detected_language):
        return f"{detected_language} Language", "language", detected_language
    if detected_language and any(term in haystack for term in [" fal ", " sal ", " home ", " hl ", "language", "taal"]):
        return f"{detected_language} Language", "language", detected_language
    return title or "Unclassified CAPS Subject", str(row.get("subject_family") or "other"), language


def ontology_blueprint(subject: str, family: str, phase: str) -> str:
    subject_n = norm(subject)
    if phase == "foundation_grade_r_3":
        return "foundation_activity_assessment"
    if family == "language":
        return "language_integrated_assessment"
    if family == "mathematics":
        return "calculation_problem_solving"
    if family == "science":
        return "data_diagram_practical_investigation"
    if family == "commerce":
        return "case_study_structured_questions"
    if family == "technology":
        return "practical_project_design_task"
    if family == "arts":
        return "practical_performance_or_portfolio"
    if family == "life_skills":
        return "practical_performance_or_portfolio"
    if subject_n == "history":
        return "source_based_plus_essay"
    if family == "social_sciences":
        return "source_based_plus_extended_response"
    return "structured_test_or_task"


def capability_policy(subject: str, family: str, phase: str, blueprint: str) -> dict[str, Any]:
    if phase == "foundation_grade_r_3":
        return {
            "allowed": ["concrete_activity", "teacher_observation", "oral_prompt", "picture_prompt", "short_constructed_response"],
            "default_off": ["essay", "long_source_based_response", "case_study", "formal_exam_pressure"],
            "required_distribution": {"observable_activity": 50, "oral_or_practical_response": 30, "short_recorded_response": 20},
            "generation_constraints": [
                "Use teacher-facing prompts and observable learner actions.",
                "Keep reading load minimal and grade appropriate.",
                "Do not create a long written paper unless the educator explicitly asks for it.",
            ],
        }
    if family == "language":
        return {
            "allowed": ["reading_viewing", "writing_presenting", "language_structures", "listening_speaking", "short_source_or_text_response"],
            "default_off": ["calculation_heavy_questions", "generic_case_study", "science_practical", "business_ledger_task"],
            "required_distribution": {"reading_viewing": 35, "writing_presenting": 30, "language_structures": 20, "listening_speaking": 15},
            "generation_constraints": [
                "Use language-skills integration instead of a generic content subject exam.",
                "Scale text length, vocabulary, and writing load to the phase.",
            ],
        }
    if family == "mathematics":
        return {
            "allowed": ["calculations", "problem_solving", "diagrams", "patterns", "short_reasoning"],
            "default_off": ["essay", "long_source_based_response", "generic_case_study"],
            "required_distribution": {"calculation_and_procedure": 55, "problem_solving": 30, "reasoning_or_representation": 15},
            "generation_constraints": [
                "Show memo steps and mark allocations for methods.",
                "Avoid essay-style rubrics unless requested by a human educator.",
            ],
        }
    if family == "science":
        return {
            "allowed": ["structured_concepts", "data_or_diagram_interpretation", "practical_investigation", "application_questions"],
            "default_off": ["essay_as_default", "business_case_study", "creative_portfolio_only"],
            "required_distribution": {"conceptual_understanding": 30, "data_diagram_work": 25, "practical_investigation": 25, "application_reasoning": 20},
            "generation_constraints": [
                "Use diagrams, data, observations, or investigation contexts where appropriate.",
                "Keep practical tasks safe and feasible for the grade band.",
            ],
        }
    if family == "commerce":
        return {
            "allowed": ["case_study", "structured_questions", "calculation_or_data", "recommendation_with_reason"],
            "default_off": ["history_source_essay", "science_practical", "art_portfolio"],
            "required_distribution": {"scenario_or_case": 35, "structured_content": 30, "calculation_or_data": 25, "justified_recommendation": 10},
            "generation_constraints": [
                "Use realistic learner-appropriate scenarios.",
                "Separate memo facts from acceptable alternative recommendations.",
            ],
        }
    if family == "social_sciences":
        source_weight = 45 if norm(subject) == "history" else 30
        return {
            "allowed": ["source_or_stimulus_analysis", "map_graph_or_data_interpretation", "structured_context_questions", "extended_response"],
            "default_off": ["calculation_heavy_questions", "generic_business_case", "science_experiment"],
            "required_distribution": {"source_or_stimulus": source_weight, "contextual_knowledge": 30, "extended_or_explanatory_response": 70 - source_weight},
            "generation_constraints": [
                "Use source, map, data, or contextual stimulus according to the specific subject.",
                "Only use a full essay when the phase and subject profile justify it.",
            ],
        }
    if family == "technology":
        return {
            "allowed": ["design_brief", "practical_task", "technical_diagram", "structured_theory", "project_deliverable"],
            "default_off": ["history_essay", "language_comprehension_only", "unbounded_build_project"],
            "required_distribution": {"design_or_practical": 40, "technical_knowledge": 30, "diagrams_or_specifications": 20, "reflection_or_safety": 10},
            "generation_constraints": [
                "Define constraints, materials, safety notes, and deliverables.",
                "Keep projects assessable within realistic classroom time.",
            ],
        }
    if family == "arts":
        return {
            "allowed": ["performance_or_product", "portfolio", "reflection", "technique_vocabulary", "rubric_levels"],
            "default_off": ["calculation_heavy_questions", "generic_case_study", "formal_source_essay"],
            "required_distribution": {"performance_or_product": 50, "technique_and_process": 25, "reflection_or_context": 25},
            "generation_constraints": [
                "Use observable criteria and clear rubric levels.",
                "Preserve space for educator judgement and local resources.",
            ],
        }
    return {
        "allowed": ["structured_questions", "short_response", "applied_task"],
        "default_off": ["essay", "long_source_based_response", "practical_project"],
        "required_distribution": {"structured_items": 70, "applied_response": 30},
        "generation_constraints": ["Use the canonical profile and evidence snippets; require educator review before classroom use."],
    }


def build_profiles(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    enriched = []
    for row in rows:
        if row.get("phase") == "policy_and_support":
            continue
        subject, family, language = canonical_subject(row)
        current = dict(row)
        current["canonical_subject"] = subject
        current["canonical_family"] = family
        current["document_language"] = language or row.get("language_guess") or "Unknown"
        current["phase_group"] = phase_group(str(row.get("phase") or ""))
        grouped[(str(row.get("phase")), subject)].append(current)
        enriched.append(current)

    profiles = []
    for (phase, subject), docs in sorted(grouped.items(), key=lambda item: (phase_group(item[0][0]), item[0][1])):
        families = Counter(doc["canonical_family"] for doc in docs)
        family = families.most_common(1)[0][0]
        blueprint = ontology_blueprint(subject, family, phase)
        policy = capability_policy(subject, family, phase, blueprint)
        signal_counts = {field: sum(1 for doc in docs if doc.get(field)) for field in SIGNAL_FIELDS}
        noisy_docs = [
            doc for doc in docs
            if sum(1 for field in SIGNAL_FIELDS if doc.get(field)) >= 6
        ]
        evidence = [
            {
                "title": doc.get("title"),
                "path": doc.get("path"),
                "sha256": doc.get("sha256"),
                "language": doc.get("document_language"),
                "document_blueprint": doc.get("recommended_blueprint"),
                "signals": {field: bool(doc.get(field)) for field in SIGNAL_FIELDS},
                "snippets": (doc.get("snippets") or [])[:2],
            }
            for doc in docs
        ]
        profiles.append(
            {
                "profile_id": f"{phase_group(phase)}.{slug(subject)}",
                "subject": subject,
                "phase": phase,
                "phase_group": phase_group(phase),
                "grades": phase_grades(phase),
                "subject_family": family,
                "assessment_family": blueprint,
                **policy,
                "validation_rules": [
                    "Generated packs must declare this profile_id and assessment_family.",
                    "Generated packs may not use default_off modes unless the human request explicitly overrides them.",
                    "Generated packs must cite at least one supporting CAPS evidence document.",
                    "Teacher memo, mark allocation, and learner instructions must be present.",
                    "Educator approval remains a required terminal gate before delivery or classroom use.",
                ],
                "evidence_summary": {
                    "document_count": len(docs),
                    "languages": dict(Counter(doc.get("document_language") or "Unknown" for doc in docs)),
                    "document_blueprints": dict(Counter(doc.get("recommended_blueprint") or "unknown" for doc in docs)),
                    "signal_counts": signal_counts,
                    "noisy_document_count": len(noisy_docs),
                },
                "supporting_caps_evidence": evidence,
            }
        )
    return profiles


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Canonical CAPS Assessment Ontology",
        "",
        f"Created: {payload['created_at']}",
        "",
        "This ontology turns noisy document-level CAPS observations into cleaner subject + phase assessment profiles. PDF keyword evidence remains underneath the profile; it no longer directly decides the assessment shape.",
        "",
        "## Summary",
        "",
        f"- Source documents observed: {payload['source_document_count']}",
        f"- Canonical profiles: {payload['profile_count']}",
        f"- Phases: {', '.join(f'{k}={v}' for k, v in payload['phase_profile_counts'].items())}",
        f"- Assessment families: {', '.join(f'{k}={v}' for k, v in payload['assessment_family_counts'].items())}",
        "",
        "## Profiles",
        "",
        "| Profile | Subject | Phase | Family | Assessment | Evidence Docs | Noisy Docs | Default Off |",
        "| --- | --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for profile in payload["profiles"]:
        default_off = ", ".join(profile.get("default_off", []))
        lines.append(
            "| "
            + " | ".join(
                [
                    profile["profile_id"],
                    profile["subject"].replace("|", "/"),
                    profile["phase_group"],
                    profile["subject_family"],
                    profile["assessment_family"],
                    str(profile["evidence_summary"]["document_count"]),
                    str(profile["evidence_summary"]["noisy_document_count"]),
                    default_off.replace("|", "/"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Gate Rule",
            "",
            "Generation must flow: CAPS source documents -> document evidence -> canonical profile -> assessment blueprint -> generation constraints -> validation -> educator approval.",
        ]
    )
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build canonical CAPS subject/phase assessment ontology from matrix evidence.")
    parser.add_argument("--matrix", default=str(DEFAULT_MATRIX))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    matrix_path = Path(args.matrix).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    profiles = build_profiles(matrix.get("rows", []))
    payload = {
        "schema": "knowedge.caps_assessment_ontology.v1",
        "created_at": utc_now(),
        "source_matrix": str(matrix_path),
        "source_document_count": len(matrix.get("rows", [])),
        "profile_count": len(profiles),
        "phase_profile_counts": dict(Counter(profile["phase_group"] for profile in profiles)),
        "assessment_family_counts": dict(Counter(profile["assessment_family"] for profile in profiles)),
        "profiles": profiles,
    }
    json_path = out_dir / "caps_assessment_ontology.json"
    md_path = out_dir / "CAPS_ASSESSMENT_ONTOLOGY.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_markdown(md_path, payload)
    print(json.dumps({"status": "completed", "profiles": len(profiles), "out": str(out_dir)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
