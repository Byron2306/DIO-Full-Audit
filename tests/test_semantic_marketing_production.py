from __future__ import annotations

from portfolio_runtime import load_portfolio
from semantic_marketing import semantic_marketing_brief


def test_all_canonical_incarnations_receive_a_semantic_marketing_brief_without_demand_inflation() -> None:
    portfolio = load_portfolio()
    rows = portfolio["incarnations"]
    assert len(rows) == 53
    assert portfolio["candidate_incarnations_imported"] == 0

    for row in rows:
        brief = semantic_marketing_brief(row["Incarnation"])
        fields = brief["brief"]
        assert brief["truth_class"] == "SEMANTIC_MARKETING_HYPOTHESIS"
        assert fields["audience_name"].strip()
        assert fields["pain"].strip()
        assert fields["outcome"].strip()
        assert fields["cta"].strip()
        assert fields["marketing_statement"].strip()
        assert brief["observed_market_demand"] is False
        assert brief["best_audience_proved"] is False
        assert brief["willingness_to_pay_proved"] is False
        assert brief["commercial_success_proved"] is False
        assert brief["publication_authorized"] is False
        assert brief["spend_authorized"] is False
        assert brief["authority_created"] is False


def test_known_product_uses_configured_profile_and_selects_audience_automatically() -> None:
    brief = semantic_marketing_brief("Evidex EvidenceOps")
    assert brief["generation_mode"] == "CONFIGURED_MARKETING_PROFILE"
    assert brief["profile_id"] == "EVIDEX_PACK"
    assert brief["audience_id"]
    assert brief["proof_asset"]
    assert brief["source_image"]


def test_unprofiled_product_uses_atlas_sensorium_semantics_not_manual_market_claims() -> None:
    brief = semantic_marketing_brief("TenderProof")
    assert brief["generation_mode"] == "ATLAS_SENSORIUM_SEMANTIC_BRIEF"
    assert brief["profile_id"] == ""
    assert brief["evidence_basis"]["atlas_domain_ids"]
    assert brief["evidence_basis"]["work_patterns"]
    assert brief["observed_market_demand"] is False
    assert brief["best_audience_proved"] is False
