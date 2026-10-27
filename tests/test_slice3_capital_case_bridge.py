from pathlib import Path

from market_capital.engagement import attach_real_engagement_to_case


def test_discovery_candidate_does_not_create_customer_case(tmp_path: Path):
    result = attach_real_engagement_to_case(tmp_path, {"opportunity_id": "opp1"}, {"state": "DISCOVERED"})
    assert result is None
    assert not (tmp_path / "customer_cases").exists()


def test_real_response_may_enter_existing_slice2_case_spine(tmp_path: Path):
    result = attach_real_engagement_to_case(tmp_path, {
        "opportunity_id": "opp1",
        "opportunity_type": "INVESTOR",
        "organisation_id": "org1",
    }, {
        "state": "RESPONSE_OBSERVED",
        "channel": "outlook",
        "external_user_id": "investor@example.org",
        "conversation_id": "capital-opp1",
        "contact_email": "investor@example.org",
        "evidence_ref": "mail:123",
    })
    assert result is not None
    assert result["authority_created"] is False
    assert result["capital_support"]["opportunity_id"] == "opp1"
    assert "mail:123" in result["capital_support"]["engagement_evidence_refs"]


def test_draft_ready_is_not_real_engagement(tmp_path: Path):
    result = attach_real_engagement_to_case(tmp_path, {"opportunity_id": "opp2"}, {"state": "DRAFT_READY"})
    assert result is None
