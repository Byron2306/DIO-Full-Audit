from pathlib import Path

from market_capital.outreach import build_outreach_bundle

ROOT = Path(__file__).resolve().parents[1]


def test_market_command_bundle_is_tailored_and_draft_only():
    bundle = build_outreach_bundle(
        {"opportunity_id": "opp1", "opportunity_type": "INVESTOR", "organisation_name": "Example Ventures"},
        {
            "primary_products": ["DIO AI Assurance", "Agent Authority"],
            "proof_bundle": ["T25 proof stack"],
            "recommended_pitch_family": "GOVERNED_AI_INFRASTRUCTURE",
        },
        {"hypothesis_id": "h1", "state": "TEST", "statement": "Governed AI infrastructure may fit their thesis."},
    )
    assert bundle["truth_class"] == "DRAFT_RECOMMENDATION"
    assert bundle["send_authority"] is False
    assert bundle["authority_created"] is False
    assert bundle["recommended_product_wedge"] == ["DIO AI Assurance", "Agent Authority"]
    assert bundle["safe_claims"]
    assert bundle["claims_to_avoid"]
    assert bundle["draft_outreach"]


def test_market_command_exposes_read_only_capital_draft_route():
    source = (ROOT / "scripts/serve_market_command_ms10.py").read_text(encoding="utf-8")
    assert '"/api/market/capital-support/draft"' in source
    assert "CAPITAL_SUPPORT_DRAFTS" in source
    assert "send_authority" in source
