from __future__ import annotations

from scripts import run_hymark_history_source_first as source_first


def _sources():
    return [
        {"label": "Source A", "title": "A", "content": "locked source A"},
        {"label": "Source B", "title": "B", "content": "locked source B"},
        {"label": "Source C", "title": "C", "content": "locked source C"},
    ]


def _plan(question_count: int = 10, essay_points: int = 8):
    sections = []
    for label in ("Source A", "Source B", "Source C"):
        marks = [3] * question_count
        if question_count != 10:
            marks = [30 // question_count] * question_count
            marks[-1] += 30 - sum(marks)
        sections.append(
            {
                "source_label": label,
                "questions": [
                    {
                        "question": f"Use {label} to answer item {index + 1}.",
                        "marks": mark,
                        "memo": [f"Specific source-grounded answer {index + 1}."],
                    }
                    for index, mark in enumerate(marks)
                ],
            }
        )
    return {
        "source_sections": sections,
        "essay": {
            "option_a": "Assess the extent to which organised resistance challenged apartheid controls during the period in the question.",
            "option_b": "Evaluate how apartheid policy and resistance interacted to reshape political mobilisation during the period in the question.",
            "memo_option_a": [f"Substantive A point {i}." for i in range(essay_points)],
            "memo_option_b": [f"Substantive B point {i}." for i in range(essay_points)],
            "marking_guidance": ["argument", "evidence", "analysis", "factual accuracy", "structure"],
        },
    }


def test_ten_source_subquestions_are_valid_when_each_section_reconciles_to_thirty_marks():
    errors = source_first._plan_errors(_plan(question_count=10), _sources())
    assert not [error for error in errors if "subquestions" in error]
    assert not [error for error in errors if "questions total" in error]


def test_eleven_source_subquestions_are_still_rejected():
    errors = source_first._plan_errors(_plan(question_count=11), _sources())
    assert any("expected 5-10" in error for error in errors)


def test_thin_essay_memorandum_remains_a_real_failure():
    errors = source_first._plan_errors(_plan(question_count=10, essay_points=5), _sources())
    assert any("memo_option_a needs at least 6" in error for error in errors)
    assert any("memo_option_b needs at least 6" in error for error in errors)


def test_visual_invention_is_still_refused():
    plan = _plan()
    plan["source_sections"][0]["questions"][0]["question"] = "Study the photograph and explain its message."
    errors = source_first._plan_errors(plan, _sources())
    assert any("visual" in error for error in errors)
