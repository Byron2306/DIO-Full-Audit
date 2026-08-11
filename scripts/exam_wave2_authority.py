from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from dio_epistemic_spine import curriculum_binding, distribution_contract, epistemic_tokens


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _subject_id(request: dict[str, Any]) -> str:
    return str((request.get("subject_profile") or {}).get("subject_id") or "").strip().lower()


def _grade(request: dict[str, Any]) -> int:
    return int((request.get("grade_profile") or {}).get("grade") or request.get("grade") or 0)


def _term(request: dict[str, Any]) -> str:
    return str(request.get("term") or "auto")


def _curriculum_elements(caps_context: dict[str, Any], request: dict[str, Any]) -> list[str]:
    elements = []
    for key in ["term_theme_lines", "caps_theme_candidates", "curriculum_elements"]:
        for item in caps_context.get(key) or []:
            text = _norm(item)
            if text and text not in elements:
                elements.append(text)
    excerpt = str(caps_context.get("extracted_excerpt") or "")
    grade = _grade(request)
    term = _term(request)
    for raw in re.split(r"[\r\n]+|•|;", excerpt):
        line = _norm(raw)
        low = line.casefold()
        if len(line) < 12:
            continue
        if any(token in low for token in [f"grade {grade}", f"graad {grade}", f"term {term}", f"kwartaal {term}", "topic", "content", "number", "count", "shape", "measurement", "pattern"]):
            if line not in elements:
                elements.append(line[:260])
    return elements[:60]


def caps_authority_provenance(caps_context: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    selected = caps_context.get("selected") or {}
    excerpt = str(caps_context.get("extracted_excerpt") or "")
    material = excerpt.encode("utf-8", errors="ignore")
    title_blob = " ".join([str(selected.get("title") or ""), str(selected.get("path") or "")]).casefold()
    grade = _grade(request)
    grade_tokens = [f"grade {grade}", f"graad {grade}", f"grade{grade}", f"gr{grade}"]
    phase_coverage = grade <= 3 and any(token in title_blob for token in ["r-3", "r 3", "1-3", "1 3", "foundation"])
    grade_coverage = phase_coverage or any(token in excerpt.casefold() for token in grade_tokens)
    return {
        "schema": "dio.exam_studio.caps_authority_provenance.v1",
        "canonical_subject": (request.get("subject_profile") or {}).get("display_name"),
        "subject_id": _subject_id(request),
        "language_or_edition": caps_context.get("preferred_language") or request.get("preferred_language"),
        "requested_grade": grade,
        "requested_term": _term(request),
        "document_title": selected.get("title"),
        "document_path": selected.get("path"),
        "document_sha256": selected.get("sha256"),
        "exact_excerpt_sha256": hashlib.sha256(material).hexdigest() if excerpt else None,
        "exact_excerpt_chars": len(excerpt),
        "grade_coverage_proven": bool(grade_coverage),
        "curriculum_elements": _curriculum_elements(caps_context, request),
        "generated_text_is_authoritative_quote": False,
    }


def _questions(pack: dict[str, Any]) -> list[dict[str, Any]]:
    return [q for section in pack.get("sections") or [] for q in section.get("questions") or [] if isinstance(q, dict)]


def foundation_curriculum_gate(pack: dict[str, Any], request: dict[str, Any], caps_context: dict[str, Any]) -> dict[str, Any]:
    if _grade(request) > 3:
        return {"schema": "dio.exam_studio.foundation_curriculum_gate.v1", "passed": True, "applicable": False, "bindings": []}
    provenance = caps_authority_provenance(caps_context, request)
    elements = provenance.get("curriculum_elements") or []
    bindings = []
    for question in _questions(pack):
        text = " ".join([str(question.get("question") or ""), str(question.get("source_reference") or "")])
        if not text.strip():
            continue
        binding = curriculum_binding(text, elements, minimum_overlap=2)
        bindings.append({"question_number": question.get("number"), "question": text, **binding})
    passed = bool(provenance.get("grade_coverage_proven")) and bool(bindings) and all(row.get("passed") for row in bindings)
    return {
        "schema": "dio.exam_studio.foundation_curriculum_gate.v1",
        "applicable": True,
        "passed": passed,
        "grade_coverage_proven": provenance.get("grade_coverage_proven"),
        "bindings": bindings,
        "curriculum_element_count": len(elements),
    }


def _resource_assumptions(pack: dict[str, Any]) -> list[str]:
    blob = json.dumps(pack, ensure_ascii=False).casefold()
    patterns = {
        "recording_device": ["recording", "record your", "video recording", "camera", "phone"],
        "learner_device": ["device", "tablet", "smartphone", "laptop"],
        "internet": ["internet", "online", "website", "web access"],
        "music_playback": ["music", "speaker", "audio playback"],
        "audience": ["audience", "peer audience"],
        "specialist_space": ["studio", "laboratory", "workshop"],
        "large_floor_area": ["10 m x 10 m", "10m x 10m", "10 m × 10 m"],
        "printer": ["printer", "printed copy"],
    }
    found = []
    for key, needles in patterns.items():
        if any(needle in blob for needle in needles):
            found.append(key)
    return found


def environment_contract_gate(pack: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    assumptions = _resource_assumptions(pack)
    declared = set(str(x) for x in ((request.get("environment_contract") or {}).get("available_resources") or []))
    unresolved = [item for item in assumptions if item not in declared]
    return {
        "schema": "dio.exam_studio.environment_contract.v1",
        "passed": not unresolved,
        "assumptions": assumptions,
        "declared_resources": sorted(declared),
        "unresolved_assumptions": unresolved,
        "policy": "Undeclared resource assumptions require educator configuration or resource-neutral wording.",
    }


def _dimension_for_text(text: str, required_keys: list[str]) -> str | None:
    tokens = epistemic_tokens(text)
    scored = []
    for key in required_keys:
        overlap = len(tokens & epistemic_tokens(key.replace("_", " ")))
        scored.append((overlap, key))
    scored.sort(reverse=True)
    return scored[0][1] if scored and scored[0][0] > 0 else None


def assessment_family_distribution_gate(pack: dict[str, Any], request: dict[str, Any], caps_context: dict[str, Any]) -> dict[str, Any]:
    ontology = caps_context.get("assessment_ontology_profile") or {}
    required = ontology.get("required_distribution") or {}
    if not required:
        return {"schema": "dio.exam_studio.assessment_family_distribution.v1", "passed": True, "applicable": False}
    marks_by = {str(key): 0.0 for key in required}
    mapped = 0.0
    total = 0.0
    for section in pack.get("sections") or []:
        section_blob = " ".join([str(section.get("title") or ""), str(section.get("mode") or ""), str(section.get("instructions") or "")])
        for q in section.get("questions") or []:
            marks = float(q.get("marks") or 0)
            total += marks
            dim = _dimension_for_text(section_blob + " " + str(q.get("question") or ""), list(required))
            if dim:
                marks_by[dim] += marks
                mapped += marks
    if total <= 0 or mapped / total < 0.60:
        return {
            "schema": "dio.exam_studio.assessment_family_distribution.v1",
            "passed": False,
            "applicable": True,
            "reason": "insufficient_semantic_mapping_to_verify_required_distribution",
            "mapped_fraction": round(mapped / total, 4) if total else 0.0,
            "required": required,
        }
    observed = {key: round(value / total * 100.0, 2) for key, value in marks_by.items()}
    result = distribution_contract(observed, required, tolerance_percentage_points=15.0)
    return {"schema": "dio.exam_studio.assessment_family_distribution.v1", "applicable": True, "observed": observed, "required": required, **result}


def wave2_pack_errors(pack: dict[str, Any], request: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    caps_context = request.get("caps_context") or {}
    provenance = caps_authority_provenance(caps_context, request)
    foundation = foundation_curriculum_gate(pack, request, caps_context)
    environment = environment_contract_gate(pack, request)
    distribution = assessment_family_distribution_gate(pack, request, caps_context)
    errors = []
    if not provenance.get("grade_coverage_proven"):
        errors.append("CAPS authority provenance does not prove requested-grade coverage")
    if foundation.get("applicable") and not foundation.get("passed"):
        errors.append("Foundation curriculum-content coverage gate failed")
    if not environment.get("passed"):
        errors.append("environment contract unresolved: " + ", ".join(environment.get("unresolved_assumptions") or []))
    if distribution.get("applicable") and not distribution.get("passed"):
        errors.append("assessment-family distribution gate failed")
    return errors, {
        "caps_authority_provenance": provenance,
        "foundation_curriculum_gate": foundation,
        "environment_contract": environment,
        "assessment_family_distribution": distribution,
    }


def opportunity_equivalence_gate(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    p1 = first.get("assessment_pack") or {}
    p2 = second.get("assessment_pack") or {}
    checks = {
        "total_marks_equal": int(first.get("total_marks") or 0) == int(second.get("total_marks") or 0),
        "render_shell_equal": str(first.get("render_shell") or "") == str(second.get("render_shell") or ""),
        "section_count_equal": len(p1.get("sections") or []) == len(p2.get("sections") or []),
        "resource_burden_equal": set(_resource_assumptions(p1)) == set(_resource_assumptions(p2)),
    }
    return {
        "schema": "dio.exam_studio.opportunity_equivalence.v1",
        "passed": all(checks.values()),
        "checks": checks,
        "first_resources": _resource_assumptions(p1),
        "second_resources": _resource_assumptions(p2),
    }
