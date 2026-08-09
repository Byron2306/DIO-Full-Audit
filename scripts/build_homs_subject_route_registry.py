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
DEFAULT_SOURCE_CATALOGUE = ROOT / "deliverables" / "exam_source_catalogue_fet_2024_november" / "FET_EXAM_SOURCE_CATALOGUE.json"
DEFAULT_SUPPLEMENTARY_GEOGRAPHY_MATRIX = ROOT / "deliverables" / "exam_source_matrix" / "exam_source_matrix.json"
DEFAULT_ASSESSMENT_DESIGN = ROOT / "deliverables" / "caps_assessment_design" / "caps_assessment_design.json"
DEFAULT_SUBJECT_PROFILE_DIR = ROOT / "config" / "homs_subject_profiles"
DEFAULT_OUT_DIR = ROOT / "deliverables" / "homs_subject_route_registry"


SOURCE_TO_VISUAL_KIND = {
    "data_table": "data_table",
    "graph_or_chart": "graph",
    "diagram_or_model": "labelled_diagram",
    "map_extract": "map_or_spatial_extract",
    "cartoon": "cartoon_or_visual_text",
    "photograph_or_image": "photo_or_real_world_image",
    "text_extract": "text_source_extract",
    "unclassified_stimulus": "scenario_or_mixed_stimulus",
    "image_rendered_or_scanned_pages": "source_page_image",
}

FAMILY_ROUTE = {
    "data_diagram_practical_investigation": {
        "route": "caps_science_data_diagram_route",
        "minimum_sections": ["concepts", "diagram_interpretation", "data_response", "investigation_or_method"],
        "template_status": "partly_curated",
    },
    "case_study_structured_questions": {
        "route": "caps_case_study_structured_route",
        "minimum_sections": ["short_concepts", "case_stimulus", "applied_questions", "recommendation_or_evaluation"],
        "template_status": "generic_supported",
    },
    "calculation_problem_solving": {
        "route": "caps_calculation_problem_route",
        "minimum_sections": ["procedural_items", "word_problems", "data_or_formula_interpretation", "worked_memo"],
        "template_status": "needs_subject_curves",
    },
    "language_integrated_assessment": {
        "route": "caps_language_integrated_route",
        "minimum_sections": ["reading_viewing", "language_structures", "writing_presenting"],
        "template_status": "needs_language_shell",
    },
    "source_based_plus_essay": {
        "route": "caps_source_based_history_route",
        "minimum_sections": ["source_analysis", "source_comparison", "extended_response_or_essay"],
        "template_status": "curated_for_history",
    },
    "source_based_plus_extended_response": {
        "route": "caps_source_based_extended_route",
        "minimum_sections": ["source_analysis", "source_comparison", "extended_response"],
        "template_status": "generic_supported",
    },
    "practical_performance_or_portfolio": {
        "route": "caps_practical_performance_route",
        "minimum_sections": ["performance_brief", "observable_criteria", "rubric", "educator_record"],
        "template_status": "needs_human_task_design",
    },
    "practical_project_design_task": {
        "route": "caps_project_design_route",
        "minimum_sections": ["design_brief", "planning", "build_or_investigate", "test_and_reflect"],
        "template_status": "generic_supported",
    },
}

HIGH_TOUCH_SOURCES = {"cartoon", "photograph_or_image", "map_extract", "image_rendered_or_scanned_pages"}
HAND_AUTHORED_ROUTE_SUBJECTS = {
    "accounting",
    "agricultural_sciences",
    "afrikaans_language",
    "business_studies",
    "english_language",
    "economics",
    "geography",
    "history",
    "life_orientation",
    "life_sciences",
    "mathematics",
    "physical_sciences",
}
SUBJECT_PROFILE_ALIASES = {
    "afrikaans_first_additional_language": "afrikaans_language",
    "afrikaans_home_language": "afrikaans_language",
    "english_first_additional_language": "english_language",
    "english_home_language": "english_language",
    "life_science": "life_sciences",
}
CORE_ROUTE_TARGETS = [
    "English Language",
    "Afrikaans Language",
    "Economics",
    "Geography",
    "History",
    "Life Orientation",
    "Life Sciences",
    "Mathematics",
    "Physical Sciences",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def load_subject_profiles(path: Path) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for item in sorted(path.glob("*.json")):
        profile = load_json(item)
        subject_id = profile.get("subject_id") or slug(profile.get("display_name", item.stem))
        profiles[str(subject_id)] = profile
    return profiles


def assessment_profiles_by_subject(design: dict[str, Any]) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for profile in design.get("profiles", []):
        profiles[slug(str(profile.get("subject") or ""))] = profile
    return profiles


def source_visual_kinds(source_types: list[str]) -> list[str]:
    kinds = [SOURCE_TO_VISUAL_KIND.get(item, "custom_source") for item in source_types]
    return sorted(set(kinds), key=kinds.index)


def supplementary_subject_contracts() -> dict[str, dict[str, Any]]:
    contracts: dict[str, dict[str, Any]] = {}
    if DEFAULT_SUPPLEMENTARY_GEOGRAPHY_MATRIX.exists():
        matrix = load_json(DEFAULT_SUPPLEMENTARY_GEOGRAPHY_MATRIX)
        if slug(str(matrix.get("subject") or "")) == "geography":
            counts = matrix.get("aggregate", {}).get("source_type_counts", {})
            observed = [item for item, _count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True)]
            contracts["Geography"] = {
                "paper_count": matrix.get("paper_count", 0),
                "unique_source_object_count": sum(int(value or 0) for value in counts.values()),
                "embedded_image_count": None,
                "observed_contract": observed,
                "examples": {},
                "supplementary_source_matrix": str(DEFAULT_SUPPLEMENTARY_GEOGRAPHY_MATRIX.relative_to(ROOT)),
            }
    return contracts


def readiness_for_route(
    subject_id: str,
    source_types: list[str],
    assessment_family: str,
    has_caps_design: bool,
    has_hand_profile: bool,
) -> tuple[str, list[str], list[str]]:
    blockers: list[str] = []
    next_steps: list[str] = []

    if not has_caps_design:
        blockers.append("missing_caps_assessment_design_profile")
        next_steps.append("Create or map the canonical CAPS assessment profile before generation.")
    source_optional = assessment_family in {"practical_performance_or_portfolio", "language_integrated_assessment"}
    if not source_types and not source_optional:
        blockers.append("missing_exam_source_contract")
        next_steps.append("Add official-paper source examples before visual/source generation.")
    elif not source_types and source_optional:
        next_steps.append("Add official-paper/source exemplars when available; route can still produce supervised school-based tasks.")

    route = FAMILY_ROUTE.get(assessment_family, {})
    template_status = route.get("template_status", "unknown")
    high_touch = sorted(set(source_types) & HIGH_TOUCH_SOURCES)

    if template_status.startswith("needs") and not has_hand_profile:
        blockers.append(f"{template_status}_for_{assessment_family or 'unknown_family'}")
        next_steps.append("Create a curated visual/source template for this assessment family.")
    if high_touch and not has_hand_profile:
        blockers.append("high_touch_source_assets:" + ",".join(high_touch))
        next_steps.append("Use extracted official-paper exemplars to curate the first visual/source pack.")
    elif high_touch:
        next_steps.append("Prefer extracted official-paper exemplars for high-touch assets: " + ", ".join(high_touch) + ".")
    if not has_hand_profile:
        next_steps.append("Promote this subject into config/homs_subject_profiles once the first pack passes review.")

    if not blockers and has_hand_profile:
        status = "ready_to_generate"
    elif not blockers:
        status = "pilot_ready"
    elif has_caps_design and (source_types or source_optional):
        status = "curation_required"
    else:
        status = "blocked_until_profiled"
    return status, blockers, next_steps


def route_from_contract(
    subject_name: str,
    contract: dict[str, Any],
    design_by_subject: dict[str, dict[str, Any]],
    subject_profiles: dict[str, dict[str, Any]],
    core_target: bool = False,
) -> dict[str, Any]:
    subject_id = slug(subject_name)
    design_key = SUBJECT_PROFILE_ALIASES.get(subject_id, subject_id)
    design_profile = design_by_subject.get(design_key, {})
    assessment_family = str(design_profile.get("assessment_family") or "")
    source_types = list(contract.get("observed_contract") or [])
    has_hand_profile = subject_id in subject_profiles or design_key in subject_profiles or design_key in HAND_AUTHORED_ROUTE_SUBJECTS
    status, blockers, next_steps = readiness_for_route(
        subject_id=subject_id,
        source_types=source_types,
        assessment_family=assessment_family,
        has_caps_design=bool(design_profile),
        has_hand_profile=has_hand_profile,
    )
    family_route = FAMILY_ROUTE.get(assessment_family, {})
    examples = contract.get("examples") or {}
    exemplar_refs = []
    for source_type in source_types[:4]:
        if examples.get(source_type):
            exemplar_refs.append(
                {
                    "source_type": source_type,
                    "paper": examples[source_type][0].get("paper"),
                    "page": examples[source_type][0].get("page"),
                    "snippet": examples[source_type][0].get("snippet"),
                }
            )
    return {
        "subject": subject_name,
        "subject_id": subject_id,
        "assessment_design_subject_id": design_key,
        "core_target": core_target,
        "status": status,
        "canonical_profile_id": design_profile.get("profile_id"),
        "assessment_family": assessment_family or None,
        "render_shell": design_profile.get("render_shell"),
        "route": family_route.get("route"),
        "paper_count": contract.get("paper_count", 0),
        "source_object_count": contract.get("unique_source_object_count", 0),
        "embedded_image_count": contract.get("embedded_image_count", 0),
        "source_matrix": contract.get("supplementary_source_matrix"),
        "observed_source_types": source_types,
        "required_visual_kinds": source_visual_kinds(source_types),
        "minimum_sections": family_route.get("minimum_sections", []),
        "has_hand_authored_subject_profile": has_hand_profile,
        "blockers": blockers,
        "next_steps": next_steps,
        "exemplar_refs": exemplar_refs,
    }


def build_registry(source_catalogue: dict[str, Any], assessment_design: dict[str, Any], subject_profiles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    design_by_subject = assessment_profiles_by_subject(assessment_design)
    routes: list[dict[str, Any]] = []
    subjects = source_catalogue.get("subjects") or {}
    subjects = {**subjects, **supplementary_subject_contracts()}
    for subject_name, contract in sorted(subjects.items()):
        routes.append(
            route_from_contract(
                subject_name=subject_name,
                contract=contract,
                design_by_subject=design_by_subject,
                subject_profiles=subject_profiles,
                core_target=slug(subject_name) in {slug(item) for item in CORE_ROUTE_TARGETS},
            )
        )

    existing_design_keys = {route["assessment_design_subject_id"] for route in routes}
    for subject_name in CORE_ROUTE_TARGETS:
        subject_id = slug(subject_name)
        design_key = SUBJECT_PROFILE_ALIASES.get(subject_id, subject_id)
        if design_key in existing_design_keys:
            for route in routes:
                if route["assessment_design_subject_id"] == design_key:
                    route["core_target"] = True
            continue
        routes.append(
            route_from_contract(
                subject_name=subject_name,
                contract={"paper_count": 0, "unique_source_object_count": 0, "embedded_image_count": 0, "observed_contract": [], "examples": {}},
                design_by_subject=design_by_subject,
                subject_profiles=subject_profiles,
                core_target=True,
            )
        )

    status_counts = Counter(route["status"] for route in routes)
    family_counts = Counter(route["assessment_family"] or "unmapped" for route in routes)
    return {
        "schema": "knowedge.homs_subject_route_registry.v1",
        "created_at": utc_now(),
        "source_catalogue": str(DEFAULT_SOURCE_CATALOGUE.relative_to(ROOT)),
        "assessment_design": str(DEFAULT_ASSESSMENT_DESIGN.relative_to(ROOT)),
        "route_count": len(routes),
        "status_counts": dict(status_counts),
        "assessment_family_counts": dict(family_counts),
        "routes": routes,
    }


def write_markdown(path: Path, registry: dict[str, Any]) -> None:
    lines = [
        "# HOMS Subject Route Registry",
        "",
        "Purpose: join the official-paper source catalogue to the CAPS assessment design profile so each FET subject has an explicit generation route.",
        "",
        "## Summary",
        "",
        f"- Routes: {registry['route_count']}",
        "- Status counts: " + ", ".join(f"{key}={value}" for key, value in registry["status_counts"].items()),
        "- Assessment families: " + ", ".join(f"{key}={value}" for key, value in registry["assessment_family_counts"].items()),
        "",
        "## Core Targets",
        "",
        "| Subject | Status | Family | Route | Source catalogue | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for route in [item for item in registry["routes"] if item.get("core_target")]:
        source_state = f"{route['paper_count']} paper(s), {route['source_object_count']} source object(s)" if route["paper_count"] else "not yet catalogued"
        notes = "; ".join(route["next_steps"][:2]) if route["next_steps"] else "Ready for pilot generation."
        lines.append(
            "| {subject} | `{status}` | `{family}` | `{route_name}` | {source_state} | {notes} |".format(
                subject=route["subject"],
                status=route["status"],
                family=route["assessment_family"] or "unmapped",
                route_name=route["route"] or "unmapped",
                source_state=source_state,
                notes=notes.replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
        "## Route Table",
        "",
        "| Subject | Status | Family | Route | Source contract | Next move |",
        "|---|---|---|---|---|---|",
        ]
    )
    for route in registry["routes"]:
        next_move = route["next_steps"][0] if route["next_steps"] else "Generate pilot pack and run educator review."
        lines.append(
            "| {subject} | `{status}` | `{family}` | `{route_name}` | {sources} | {next_move} |".format(
                subject=route["subject"],
                status=route["status"],
                family=route["assessment_family"] or "unmapped",
                route_name=route["route"] or "unmapped",
                sources=", ".join(f"`{item}`" for item in route["observed_source_types"]) or "none",
                next_move=next_move.replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## Operating Rule",
            "",
            "A subject should not go from CAPS keyword extraction straight to exam generation. The stable route is:",
            "",
            "`official paper source contract -> CAPS assessment design profile -> subject route -> source/visual pack -> assessment pack -> validation -> educator approval`",
            "",
            "This is the route that got the Life Sciences pack close: the questions came from the CAPS theme and the source types came from real DBE papers.",
        ]
    )
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the HOMS FET subject route registry.")
    parser.add_argument("--source-catalogue", default=str(DEFAULT_SOURCE_CATALOGUE))
    parser.add_argument("--assessment-design", default=str(DEFAULT_ASSESSMENT_DESIGN))
    parser.add_argument("--subject-profile-dir", default=str(DEFAULT_SUBJECT_PROFILE_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    source_catalogue = load_json(Path(args.source_catalogue).expanduser().resolve())
    assessment_design = load_json(Path(args.assessment_design).expanduser().resolve())
    subject_profiles = load_subject_profiles(Path(args.subject_profile_dir).expanduser().resolve())
    registry = build_registry(source_catalogue, assessment_design, subject_profiles)

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "HOMS_SUBJECT_ROUTE_REGISTRY.json").write_text(json.dumps(registry, indent=2), encoding="utf-8")
    write_markdown(out_dir / "HOMS_SUBJECT_ROUTE_REGISTRY.md", registry)
    print(json.dumps({"status": "completed", "out_dir": str(out_dir), "routes": registry["route_count"], "status_counts": registry["status_counts"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
