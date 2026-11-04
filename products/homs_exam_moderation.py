"""Mechanical HOMS assessment pre-moderation checks with explicit human gates."""
from __future__ import annotations

import json
import re
from typing import Any, Mapping


def _rendered_prompt(question: Mapping[str, Any], index: int) -> str:
    """Remove presentation labels already emitted by the document renderer."""
    label = str(question.get("number") or f"1.{index}")
    prompt = str(question.get("prompt") or "").strip()
    prompt = re.sub(r"^\s*" + re.escape(label) + r"\s*[.)]?\s*", "", prompt, count=1)
    try:
        marks = int(question.get("marks"))
    except (TypeError, ValueError):
        marks = -1
    if marks >= 0:
        prompt = re.sub(r"\s*\[\s*" + str(marks) + r"\s*\]\s*$", "", prompt, count=1)
        prompt = re.sub(r"\s*\(\s*" + str(marks) + r"\s+marks?\s*\)\s*$", "", prompt, count=1, flags=re.IGNORECASE)
    return prompt.strip()


def moderate_assessment_sources(
    *,
    assessment: Mapping[str, Any],
    paper_text: str,
    memo_text: str,
    expected_grade: int,
    expected_subject: str,
    expected_total_marks: int,
    source_hash: str,
    caps_alignment: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Check structural consistency only; do not issue a moderation decision."""
    questions = [q for section in assessment.get("sections") or [] for q in section.get("questions") or []]
    marks = [int(q.get("marks") or 0) for q in questions]
    memo_errors = []
    for index, question in enumerate(questions, 1):
        points = question.get("memo") or []
        try:
            point_marks = [int(point.get("marks") or 0) for point in points]
        except (AttributeError, TypeError, ValueError):
            point_marks = []
        if sum(point_marks) != int(question.get("marks") or 0):
            memo_errors.append(f"Question {index}: memo mark sum differs from question marks.")
        if len(point_marks) != int(question.get("marks") or 0) or any(value != 1 for value in point_marks):
            memo_errors.append(f"Question {index}: memo does not contain one explicit one-mark point per mark.")
        prompt = _rendered_prompt(question, index)
        if prompt and prompt not in paper_text:
            memo_errors.append(f"Question {index}: prompt is missing from the rendered learner paper.")
        if prompt and prompt not in memo_text:
            memo_errors.append(f"Question {index}: prompt is missing from the rendered memo.")
        for point in points:
            text = str(point.get("point") or "").strip()
            if text and text not in memo_text:
                memo_errors.append(f"Question {index}: a marking point is missing from the rendered memo.")
                break

    total = sum(marks)
    grade_match = int(assessment.get("grade") or 0) == int(expected_grade)
    subject_match = str(assessment.get("subject") or "").strip().casefold() == expected_subject.strip().casefold()
    declared_total_match = int(assessment.get("total_marks") or 0) == expected_total_marks
    paper_total_visible = f"{expected_total_marks} marks" in paper_text
    memo_total_visible = f"{expected_total_marks} marks" in memo_text
    visual_references = [
        str(q.get("prompt") or "") for q in questions
        if re.search(r"\b(look at the picture|see the diagram|in the map|shown below)\b", str(q.get("prompt") or ""), re.I)
    ]
    checks = [
        {"check": "question_mark_sum", "state": "PASS" if total == expected_total_marks and declared_total_match else "FAIL", "detail": f"Question marks sum to {total}; expected {expected_total_marks}."},
        {"check": "grade_identity", "state": "PASS" if grade_match else "FAIL", "detail": f"Assessment grade {assessment.get('grade')}; requested grade {expected_grade}."},
        {"check": "subject_identity", "state": "PASS" if subject_match else "FAIL", "detail": f"Assessment subject {assessment.get('subject')}; requested subject {expected_subject}."},
        {"check": "memo_mark_reconciliation", "state": "PASS" if not memo_errors else "FAIL", "detail": "; ".join(memo_errors) if memo_errors else "Each question has one explicit memo point per mark and its prompt/points occur in the rendered documents."},
        {"check": "rendered_total_visibility", "state": "PASS" if paper_total_visible and memo_total_visible else "FAIL", "detail": f"Expected total is visible in exam={paper_total_visible}, memo={memo_total_visible}."},
        {"check": "unprovided_visual_reference", "state": "FAIL" if visual_references else "PASS", "detail": "; ".join(visual_references) if visual_references else "No detected prompt depends on an unprovided visual."},
        {"check": "caps_source_hash_present", "state": "PASS" if re.fullmatch(r"[0-9a-f]{64}", source_hash) else "FAIL", "detail": "CAPS source hash is recorded; curriculum scope still requires an educator."},
    ]
    if caps_alignment is not None:
        mapped_questions = caps_alignment.get("question_mappings") or []
        by_id = {str(row.get("question_id") or ""): row for row in mapped_questions}
        question_ids = [str(question.get("number") or "") for question in questions]
        id_set_matches = (len(question_ids) == len(set(question_ids))
                          and len(by_id) == len(mapped_questions)
                          and set(question_ids) == set(by_id))
        prompt_matches = id_set_matches and all(
            str(question.get("prompt") or "").strip() == str(by_id[qid].get("prompt") or "").strip()
            for question, qid in zip(questions, question_ids)
        )
        citations_valid = bool(mapped_questions) and all(
            mapping.get("caps_pages") and all(
                int(page.get("physical_pdf_page") or 0) > 0
                and re.fullmatch(r"[0-9a-f]{64}", str(page.get("page_text_sha256") or ""))
                for page in mapping.get("caps_pages") or []
            )
            for mapping in mapped_questions
        )
        source_matches = caps_alignment.get("caps_source_sha256") == source_hash
        exact_binding = id_set_matches and prompt_matches and citations_valid and source_matches
        checks.append({
            "check": "caps_question_alignment_binding",
            "state": "PASS" if exact_binding else "FAIL",
            "detail": (f"Exact question ID set={id_set_matches}; prompt-to-map matches={prompt_matches}; "
                       f"physical-page/text-hash references={citations_valid}; CAPS PDF hash agrees={source_matches}. "
                       "This checks source binding only, not subject correctness or term fit."),
        })
    return {
        "schema": "dio.homs.assessment_pre_moderation.v1",
        "grade": expected_grade,
        "subject": expected_subject,
        "mechanical_state": "PASS" if all(row["state"] == "PASS" for row in checks) else "CORRECTION_REQUIRED",
        "question_count": len(questions),
        "question_marks": marks,
        "declared_total_marks": expected_total_marks,
        "source_caps_sha256": source_hash,
        **({"caps_question_alignment": dict(caps_alignment)} if caps_alignment is not None else {}),
        "checks": checks,
        "human_review": {
            "subject_scope_and_term_fit": "REQUIRED",
            "content_accuracy_and_alternative_answers": "REQUIRED",
            "language_accessibility_and_difficulty": "REQUIRED",
            "independent_moderation_decision": "NOT_ISSUED",
            "classroom_release": "NOT_AUTHORIZED",
        },
        "authority_created": False,
        "release_authorized": False,
        "commercial_validation": "UNPROVED",
    }


def render_moderation_blocks(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [[row["check"], row["state"], row["detail"]] for row in report.get("checks") or []]
    human = report.get("human_review") or {}
    return [
        {"type": "heading", "level": 1, "text": "Assessment pre-moderation checks"},
        {"type": "paragraph", "text": f"Mechanical state: {report.get('mechanical_state')}. These checks inspect internal consistency and rendered-document correspondence; they do not assess subject correctness or issue a moderation decision."},
        {"type": "table", "headers": ["Check", "State", "Finding"], "rows": rows},
        {"type": "heading", "level": 1, "text": "Required educator decisions"},
        {"type": "table", "headers": ["Review area", "Status"], "rows": [[key.replace('_', ' '), value] for key, value in human.items()]},
    ]
