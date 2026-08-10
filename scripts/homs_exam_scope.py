from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def phase_name(value: Any) -> str:
    text = str(value or "").lower()
    if text.startswith("foundation"):
        return "foundation"
    if text.startswith("intermediate"):
        return "intermediate"
    if text.startswith("senior"):
        return "senior"
    if text.startswith("fet"):
        return "fet"
    return text or "unknown"


def fallback_cognitive_mix(grade: int) -> dict[str, int]:
    if grade <= 1:
        return {"remember": 60, "understand": 40}
    if grade <= 3:
        return {"remember": 40, "understand": 40, "apply": 20}
    if grade <= 4:
        return {"remember": 30, "understand": 35, "apply": 35}
    if grade <= 6:
        return {"remember": 20, "understand": 30, "apply": 30, "analyze": 20}
    if grade <= 7:
        return {"remember": 15, "understand": 30, "apply": 30, "analyze": 25}
    if grade <= 9:
        return {"understand": 20, "apply": 30, "analyze": 30, "evaluate": 20}
    if grade == 10:
        return {"understand": 15, "apply": 30, "analyze": 35, "evaluate": 20}
    if grade == 11:
        return {"apply": 25, "analyze": 35, "evaluate": 25, "create": 15}
    return {"apply": 20, "analyze": 35, "evaluate": 30, "create": 15}


def cognitive_contract(grade_profile: dict[str, Any], design_profile: dict[str, Any] | None) -> dict[str, Any]:
    design = design_profile or {}
    supplied = design.get("cognitive_distribution") or {}
    parsed: dict[str, int] = {}
    if isinstance(supplied, dict):
        for key, value in supplied.items():
            try:
                parsed[str(key)] = int(round(float(value)))
            except Exception:
                pass
    if parsed:
        return {
            "distribution": parsed,
            "source": "selected_caps_assessment_design_profile",
            "official_percentage_claim_allowed": True,
        }
    grade = int(grade_profile.get("grade") or 0)
    targets = list(grade_profile.get("bloom_targets") or [])
    mix = fallback_cognitive_mix(grade)
    if targets:
        mix = {key: value for key, value in mix.items() if key in targets} or mix
    return {
        "distribution": mix,
        "source": "homs_grade_ladder_guardrail",
        "official_percentage_claim_allowed": False,
    }


def build_scope_contract(
    subject_profile: dict[str, Any],
    grade_profile: dict[str, Any],
    caps_context: dict[str, Any],
    term: str | int,
    extract_term_lines: Callable[[str, int, str | int | None], list[str]],
    extract_source_text: Callable[[Path, int], str] | None = None,
) -> dict[str, Any]:
    grade = int(grade_profile.get("grade") or 0)
    phase = phase_name(grade_profile.get("phase") or caps_context.get("phase"))
    term_value = str(term or "").strip().lower()
    final_mode = grade == 12 and term_value in {"final", "final_exam", "annual", "nsc"}
    errors: list[str] = []
    selected = caps_context.get("selected") or {}
    if phase not in {"foundation", "intermediate", "senior", "fet"}:
        errors.append(f"unknown school phase: {phase}")
    if not selected:
        errors.append("no authoritative CAPS source resolved")
    if selected and not selected.get("sha256"):
        errors.append("selected CAPS source is not hash-bound")
    if not final_mode and term_value not in {"1", "2", "3", "4"}:
        errors.append("term 1-4 is required; Grade 12 may explicitly use final_exam")

    text = str(caps_context.get("full_text") or caps_context.get("extracted_excerpt") or "")
    if selected.get("path") and extract_source_text:
        try:
            text = extract_source_text(Path(selected["path"]), 180000)
        except Exception:
            pass
    term_lines: list[str] = []
    if not errors and not final_mode:
        term_lines = [line for line in extract_term_lines(text, grade, term_value) if len(str(line).strip()) >= 12]
        if not term_lines:
            errors.append(f"Grade {grade} Term {term_value} content could not be established from the selected CAPS source")

    contract = {
        "schema": "knowedge.homs_exam_scope.v1",
        "subject_id": subject_profile.get("subject_id"),
        "subject": subject_profile.get("display_name"),
        "grade": grade,
        "phase": phase,
        "term": "final_exam" if final_mode else term_value,
        "term_scope_state": "resolved" if not errors else "unresolved",
        "term_content": term_lines[:16],
        "caps_source": {
            "title": selected.get("title"),
            "path": selected.get("path"),
            "sha256": selected.get("sha256"),
        },
        "learner_level": grade_profile.get("learner_level"),
        "zpd_level": grade_profile.get("zpd_level"),
        "reading_load": grade_profile.get("reading_load"),
        "writing_load": grade_profile.get("writing_load"),
        "bloom_targets": list(grade_profile.get("bloom_targets") or []),
        "question_style": list(grade_profile.get("question_style") or []),
        "memo_style": grade_profile.get("memo_style"),
        "review_checks": list(grade_profile.get("review_checks") or []) + list(subject_profile.get("human_review_checks") or []),
        "cognitive": cognitive_contract(grade_profile, caps_context.get("assessment_design_profile")),
        "errors": errors,
        "generation_ready": not errors,
        "classroom_release_ready": False,
        "human_review_required": True,
    }
    return contract


def prompt_guard(contract: dict[str, Any]) -> str:
    if not contract.get("generation_ready"):
        raise ValueError("Exam scope is unresolved: " + "; ".join(contract.get("errors") or []))
    cognition = contract.get("cognitive") or {}
    dist = cognition.get("distribution") or {}
    source_note = (
        "The cognitive percentages came from the selected CAPS assessment-design profile."
        if cognition.get("official_percentage_claim_allowed")
        else "The cognitive percentages are HOMS grade-level guardrails because no exact official distribution was extracted; do not label them as official CAPS percentages."
    )
    return (
        f"C8 EXAM SCOPE: Grade {contract['grade']} / {contract['phase']} / term {contract['term']}. "
        f"CAPS source is hash-bound as {contract['caps_source'].get('sha256')}. "
        f"Use only this resolved term content unless an educator explicitly narrows it further: {'; '.join(contract.get('term_content') or [])}. "
        f"Bloom targets: {', '.join(contract.get('bloom_targets') or [])}. "
        f"Question styles: {', '.join(contract.get('question_style') or [])}. "
        f"Reading load: {contract.get('reading_load')}; writing load: {contract.get('writing_load')}; ZPD: {contract.get('zpd_level')}. "
        f"Cognitive mix: {', '.join(f'{k}={v}%' for k, v in dist.items())}. {source_note} "
        f"Memo style: {contract.get('memo_style')}. Human review remains mandatory."
    )
