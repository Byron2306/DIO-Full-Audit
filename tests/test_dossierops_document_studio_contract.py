from __future__ import annotations

from scripts.run_dossierops_native_pilot_checkpoint import _normalize_preferred_terms


def test_technical_edit_terms_move_to_protected_tokens_not_translation_glossary() -> None:
    request = {
        "service": "technical_edit",
        "protected_tokens": ["R426,000"],
        "preferred_terms": [
            "unsigned draft",
            "signed record",
            {"source": "customer-supplied", "target": "customer-supplied"},
        ],
    }

    normalized = _normalize_preferred_terms(request)

    assert normalized["preferred_terms"] == []
    assert normalized["protected_tokens"] == [
        "R426,000",
        "unsigned draft",
        "signed record",
        "customer-supplied",
    ]


def test_translation_terms_still_normalize_to_structured_rows() -> None:
    request = {
        "service": "translation",
        "preferred_terms": [
            "unsigned draft",
            {"source": "customer-supplied", "target": "customer-supplied"},
        ],
    }

    normalized = _normalize_preferred_terms(request)
    terms = normalized["preferred_terms"]

    assert all(isinstance(row, dict) for row in terms)
    assert [row["source"] for row in terms] == ["unsigned draft", "customer-supplied"]
    assert [row["target"] for row in terms] == ["unsigned draft", "customer-supplied"]


def test_normalization_does_not_mutate_original_request() -> None:
    request = {
        "service": "technical_edit",
        "protected_tokens": ["NEEDS_YOU"],
        "preferred_terms": ["open human review"],
    }

    normalized = _normalize_preferred_terms(request)

    assert request["preferred_terms"] == ["open human review"]
    assert request["protected_tokens"] == ["NEEDS_YOU"]
    assert normalized["preferred_terms"] == []
    assert normalized["protected_tokens"] == ["NEEDS_YOU", "open human review"]
