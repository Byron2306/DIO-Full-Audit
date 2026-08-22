from __future__ import annotations

from products.homs_history_output_policy import (
    history_pack_errors,
    hydrate_history_grade,
    normalise_history_pack,
)


def _pack() -> dict:
    return {
        "assessment_title": "Grade None History Examination — Second Opportunity",
        "subject": "History",
        "grade": 11,
        "sections": [
            {
                "title": "QUESTION 1: Source B — customer-supplied teaching extract summarising a parliamentary defence of apartheid, 1948",
                "stimulus": (
                    "The language of the extract places emphasis on administration, community difference and political control. "
                    "The speaker rejects political and social integration."
                ),
                "source_provenance": {
                    "title": "customer-supplied teaching extract summarising a parliamentary defence of apartheid, 1948"
                },
                "questions": [
                    {
                        "question": "How useful is Source B for understanding the apartheid government's justification for its policies?",
                        "marks": 4,
                        "memo": ["It presents the official argument in favour of apartheid."],
                    },
                    {
                        "question": "Quote from Source B to show that the speaker focuses on administration rather than rights.",
                        "marks": 2,
                        "memo": [
                            "The language of the extract places emphasis on administration, community difference and political control.",
                            "The speaker presents separate development as a way to organise administration.",
                        ],
                    },
                ],
            }
        ],
    }


def test_grade_hydration_uses_module_name() -> None:
    request = hydrate_history_grade({"module_name": "Grade 11 History"})
    assert request["grade"] == 11


def test_output_policy_removes_grade_none_and_teaching_extract_authority_upgrade() -> None:
    pack = normalise_history_pack(_pack())
    assert pack["assessment_title"].startswith("Grade 11 History")
    blob = str(pack).casefold()
    assert "official argument in favour of apartheid" not in blob
    assert "apartheid government's justification" not in blob
    assert history_pack_errors(pack) == []


def test_quote_memo_keeps_only_exact_source_text() -> None:
    pack = normalise_history_pack(_pack())
    memo = pack["sections"][0]["questions"][1]["memo"]
    assert memo == [
        "The language of the extract places emphasis on administration, community difference and political control."
    ]
