from adapters.sophia.review_pipeline import (
    _allowed_citation_keys,
    extract_in_text_citations,
    parse_reference_entries,
    reference_key,
    split_reference_section,
    validate_gemini_commentary,
)


def test_reference_section_and_entries() -> None:
    body, references = split_reference_section(
        "A claim (Smith, 2020).\n\n## References\n\nSmith, J. (2020). A title. Journal, 1(2), 1-4."
    )
    assert "A claim" in body
    entries = parse_reference_entries(references)
    assert len(entries) == 1
    assert reference_key(entries[0]) == "smith:2020"


def test_in_text_citation_keys_are_deduplicated() -> None:
    rows = extract_in_text_citations(
        "Smith and Patel (2020) found one result. A later review agreed (Smith & Patel, 2020; Jones et al., 2021)."
    )
    assert [row["key"] for row in rows] == ["jones:2021", "smith:2020"]


def test_gemini_commentary_validation_accepts_grounded_lane_output() -> None:
    result = {
        "source": "reasoned_integrity_lane",
        "reasoned_provider": "gemini",
        "reasoned_provider_status": "ok",
        "mandos_judgment": {"passed": True},
        "article_conformity": {"summary": {"all_passed": True}},
    }
    validation = validate_gemini_commentary(
        "## Major revisions\nThe method is unspecified in [P2]; narrow the causal claim in [C1].",
        result,
        {"P1", "P2", "C1"},
        {"smith:2020"},
        set(),
    )
    assert validation["passed"] is True


def test_gemini_commentary_validation_rejects_invented_citation() -> None:
    result = {
        "source": "reasoned_integrity_lane",
        "reasoned_provider": "gemini",
        "reasoned_provider_status": "ok",
        "mandos_judgment": {"passed": True},
        "article_conformity": {"summary": {"all_passed": True}},
    }
    validation = validate_gemini_commentary(
        "[P1] should be compared with Invented (2026), doi:10.9999/not-real.",
        result,
        {"P1"},
        set(),
        set(),
    )
    assert validation["passed"] is False
    assert validation["unknown_citations"] == ["invented:2026"]
    assert validation["unknown_dois"] == ["10.9999/not-real"]


def test_allowed_citation_keys_include_reference_coauthors() -> None:
    audit = {
        "in_text_citations": [],
        "reference_entries": [{
            "key": "carless:2018",
            "entry": "Carless, D., & Boud, D. (2018). The development of student feedback literacy.",
        }],
    }
    assert _allowed_citation_keys(audit, []) >= {"carless:2018", "boud:2018"}
