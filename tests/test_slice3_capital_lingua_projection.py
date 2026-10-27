from market_capital.outreach import build_outreach_bundle


def _opportunity(kind="INVESTOR"):
    return {
        "opportunity_id": "CAP-001",
        "opportunity_type": kind,
        "organisation_name": "Example Capital",
        "source_url": "https://example.org/public-mandate",
    }


def _fit():
    return {
        "primary_products": ["Evidex", "HOMS"],
        "proof_bundle": ["proof-a", "proof-b"],
        "recommended_pitch_family": "governed_ai_infrastructure",
    }


def _hypothesis():
    return {
        "family": "governed_ai_infrastructure",
        "statement": "The target may value evidence-first governed AI infrastructure.",
        "state": "TEST",
    }


def test_outreach_exposes_lingua_hook_and_approach_projection():
    bundle = build_outreach_bundle(_opportunity(), _fit(), _hypothesis())

    lingua = bundle["lingua_projection"]
    assert lingua["schema"] == "dio.lingua.capital_outreach_projection.v1"
    assert lingua["semantic_law_hash"].startswith("sha256:")
    assert lingua["selected_hook_family"]
    assert lingua["selected_approach"]
    assert len(lingua["hook_variants"]) >= 3
    assert len(lingua["approach_variants"]) >= 3
    assert lingua["meaning_preserved"] is True
    assert lingua["market_validation_claimed"] is False
    assert lingua["authority_created"] is False


def test_lingua_can_pivot_style_without_mutating_claim_truth():
    investor = build_outreach_bundle(_opportunity("INVESTOR"), _fit(), _hypothesis())
    grant = build_outreach_bundle(_opportunity("GRANT"), _fit(), _hypothesis())

    assert investor["lingua_projection"]["selected_approach"] != grant["lingua_projection"]["selected_approach"]
    assert investor["safe_claims"] == grant["safe_claims"]
    assert investor["claims_to_avoid"] == grant["claims_to_avoid"]
    assert investor["send_authority"] is False
    assert grant["send_authority"] is False


def test_outreach_uses_selected_lingua_hook_in_draft():
    bundle = build_outreach_bundle(_opportunity(), _fit(), _hypothesis())
    selected_hook = bundle["lingua_projection"]["selected_hook"]
    assert selected_hook
    assert bundle["draft_opening"] == selected_hook
    assert bundle["draft_outreach"].startswith(selected_hook)
