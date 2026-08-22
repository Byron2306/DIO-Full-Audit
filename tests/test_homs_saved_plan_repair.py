from __future__ import annotations

from scripts import repair_homs_second_from_saved_plan as repair


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
