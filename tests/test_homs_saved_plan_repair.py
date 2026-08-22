from __future__ import annotations

from pathlib import Path

from scripts import repair_homs_second_from_saved_plan as repair


def _question(text: str, marks: int, memo_count: int = 2) -> dict:
    return {
        "question": text,
        "marks": marks,
        "memo": [f"specific memo point {text}-{index}" for index in range(1, memo_count + 1)],
    }


def test_affected_labels_extracts_only_named_source_sections() -> None:
    errors = [
        "Source A has 11 subquestions, expected 5-10",
        "Source B questions total 28, expected 30",
    ]
    assert repair._affected_labels(errors) == ["Source A", "Source B"]


def test_section_lookup_keeps_untouched_blocks_addressable() -> None:
    plan = {
        "source_sections": [
            {"source_label": "Source A", "questions": [{"question": "A", "marks": 30, "memo": ["A"]}]},
            {"source_label": "Source B", "questions": [{"question": "B", "marks": 30, "memo": ["B"]}]},
            {"source_label": "Source C", "questions": [{"question": "C", "marks": 30, "memo": ["C"]}]},
        ],
        "essay": {
            "option_a": "Essay A wording remains fixed and unchanged for the learner.",
            "option_b": "Essay B wording remains fixed and unchanged for the learner.",
            "memo_option_a": ["1", "2", "3", "4", "5", "6", "7", "8"],
            "memo_option_b": ["1", "2", "3", "4", "5", "6", "7", "8"],
            "marking_guidance": ["argument", "evidence", "analysis", "structure"],
        },
    }
    source_c = repair._section_by_label(plan, "Source C")
    essay_before = dict(plan["essay"])

    assert source_c["questions"][0]["question"] == "C"
    assert plan["essay"] == essay_before


def test_deterministic_repair_merges_excess_question_and_fills_two_mark_gap(tmp_path: Path) -> None:
    source_a_questions = [_question(f"A{index}", 3 if index <= 8 else 2, 3) for index in range(1, 12)]
    # 8*3 + 3*2 = 30 marks across 11 questions.
    source_b_questions = [_question(f"B{index}", 4, 4) for index in range(1, 8)]
    # 7*4 = 28 marks, leaving a two-mark gap.
    source_c_questions = [_question(f"C{index}", 5, 5) for index in range(1, 7)]
    plan = {
        "source_sections": [
            {"source_label": "Source A", "questions": source_a_questions},
            {"source_label": "Source B", "questions": source_b_questions},
            {"source_label": "Source C", "questions": source_c_questions},
        ],
        "essay": {
            "option_a": "Explain the development of resistance using a sustained historical argument and relevant evidence.",
            "option_b": "Evaluate the impact of apartheid policy using a sustained historical argument and relevant evidence.",
            "memo_option_a": ["a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8"],
            "memo_option_b": ["b1", "b2", "b3", "b4", "b5", "b6", "b7", "b8"],
            "marking_guidance": ["argument", "evidence", "analysis", "structure"],
        },
    }
    sources = [
        {"label": "Source A", "content": "A sufficiently detailed locked source sentence one. Another grounded sentence follows."},
        {"label": "Source B", "content": "The speaker presents racial separation as administrative order. The speaker also argues that communities should preserve distinct identities. A third sentence provides further source context."},
        {"label": "Source C", "content": "A third locked source remains completely untouched by repair."},
    ]
    original_source_c = plan["source_sections"][2]
    original_essay = plan["essay"]

    repaired, actions = repair._deterministic_repair(
        plan=plan,
        sources=sources,
        labels=["Source A", "Source B"],
        out_dir=tmp_path,
    )

    a_questions = repaired["source_sections"][0]["questions"]
    b_questions = repaired["source_sections"][1]["questions"]
    assert len(a_questions) == 10
    assert sum(row["marks"] for row in a_questions) == 30
    assert len(b_questions) == 8
    assert sum(row["marks"] for row in b_questions) == 30
    assert repaired["source_sections"][2] == original_source_c
    assert repaired["essay"] == original_essay
    assert any(action.startswith("Source A:merged_smallest_adjacent_question_pair") for action in actions)
    assert any(action.startswith("Source B:added_source_grounded_2_mark_question") for action in actions)
    assert (tmp_path / "HOMS_SOURCE_FIRST_DETERMINISTIC_SECTION_REPAIR.json").is_file()
