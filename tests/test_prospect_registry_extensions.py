from __future__ import annotations

from scripts.prospect_registry_extensions import governance_gate, lead_score, load_registry_extensions, ranked_records


def test_registry_extension_loads_and_scores() -> None:
    payload = load_registry_extensions()
    rows = ranked_records(payload)
    assert rows
    assert rows[0]["lead_score"] <= 100
    assert all(0 <= lead_score(row) <= 100 for row in rows)


def test_public_source_never_grants_sales_permission() -> None:
    row = {
        "outreach_class": "CONSENT_REQUEST_ONLY",
        "permission_state": "unknown",
        "do_not_contact": False,
    }
    gate = governance_gate(row)
    assert gate["public_source_is_permission"] is False
    assert gate["consent_request_allowed"] is True
    assert gate["sales_outreach_allowed"] is False


def test_channel_route_is_not_sales_permission() -> None:
    row = {
        "outreach_class": "CHANNEL_OK",
        "permission_state": "channel_terms_apply",
        "do_not_contact": False,
    }
    gate = governance_gate(row)
    assert gate["channel_submission_allowed"] is True
    assert gate["sales_outreach_allowed"] is False


def test_consent_unlocks_sales_without_removing_review() -> None:
    row = {
        "outreach_class": "CONSENT_REQUEST_ONLY",
        "permission_state": "consented",
        "do_not_contact": False,
    }
    gate = governance_gate(row)
    assert gate["sales_outreach_allowed"] is True
    assert gate["operator_review_required"] is True


def test_do_not_contact_is_hard_block() -> None:
    row = {
        "outreach_class": "BLOCKED",
        "permission_state": "consented",
        "do_not_contact": True,
    }
    gate = governance_gate(row)
    assert gate["research_allowed"] is False
    assert gate["sales_outreach_allowed"] is False
    assert gate["consent_request_allowed"] is False
