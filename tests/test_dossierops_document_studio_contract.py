from __future__ import annotations

from scripts.run_dossierops_native_pilot_checkpoint import _normalize_preferred_terms


def test_normalize_preferred_terms_converts_legacy_strings_to_structured_rows() -> None:
    request = {
        "preferred_terms": [
            "unsigned draft",
            "signed record",
            {"source": "customer-supplied", "target": "customer-supplied"},
        ]
    }

    normalized = _normalize_preferred_terms(request)
    terms = normalized["preferred_terms"]

    assert all(isinstance(row, dict) for row in terms)
    assert [row["source"] for row in terms] == [
        "unsigned draft",
        "signed record",
        "customer-supplied",
    ]
    assert [row["target"] for row in terms] == [
        "unsigned draft",
        "signed record",
        "customer-supplied",
    ]


def test_normalize_preferred_terms_does_not_mutate_original_request() -> None:
    request = {"preferred_terms": ["open human review"]}

    normalized = _normalize_preferred_terms(request)

    assert request["preferred_terms"] == ["open human review"]
    assert normalized["preferred_terms"][0]["source"] == "open human review"
