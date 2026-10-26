from __future__ import annotations

from scripts.run_market_sensorium_ms6 import _apply_ms6_gate


def _receipt(**overrides):
    habitats = {
        "habitat_observations_examined": 10,
        "canonical_habitats": 10,
        "source_bound_habitats": 10,
        "public_observable_habitats": 10,
        "needs_you_habitats": 0,
        "refused_or_terms_restricted_habitats": 0,
        "habitat_type_diversity": 2,
        "habitat_kind_counts": {
            "YOUTUBE_CHANNEL_HABITAT": 5,
            "NEWS_OR_BLOG_HABITAT": 5,
        },
        "permission_state_counts": {"PUBLIC_OBSERVABLE": 10},
        "provider_associated_habitats": 2,
        "public_visibility_is_consent": False,
        "public_visibility_is_membership": False,
        "public_visibility_is_posting_authority": False,
        "public_visibility_is_dm_authority": False,
        "participant_inference_allowed": False,
        "member_scraping_allowed": False,
        "seller_association_is_target_identity": False,
        "habitat_is_demand": False,
        "market_demand_claimed": False,
        "authority_created": False,
        "outreach_authority_created": False,
        "posting_authority_created": False,
        "dm_authority_created": False,
        "membership_authority_created": False,
        "external_effects": False,
    }
    habitats.update(overrides)
    return {
        "ms5_acceptance": "DIO_MARKET_SENSORIUM_COMPETITIVE_OFFER_INTELLIGENCE_VERIFIED",
        "summary": {"market_habitats": habitats},
    }


def test_ms6_gate_verifies_source_bound_permission_safe_habitats() -> None:
    receipt = _apply_ms6_gate(_receipt())
    assert receipt["ms6_acceptance"] == "DIO_MARKET_SENSORIUM_MARKET_HABITAT_INTELLIGENCE_VERIFIED"
    truth = receipt["ms6_truth"]
    assert truth["public_visibility_is_consent"] is False
    assert truth["public_visibility_is_posting_authority"] is False
    assert truth["public_visibility_is_dm_authority"] is False
    assert truth["participant_inference_allowed"] is False
    assert truth["authority_created"] is False


def test_ms6_gate_requires_verified_ms5() -> None:
    receipt = _receipt()
    receipt["ms5_acceptance"] = "PENDING_COMPETITIVE_OFFER_EVIDENCE"
    assert _apply_ms6_gate(receipt)["ms6_acceptance"] == "PENDING_VERIFIED_MS5_RECEIPT"


def test_ms6_gate_requires_all_habitats_source_bound() -> None:
    assert _apply_ms6_gate(_receipt(source_bound_habitats=9))["ms6_acceptance"] == "PENDING_SOURCE_BOUND_MARKET_HABITATS"


def test_ms6_gate_requires_multiple_habitat_types() -> None:
    assert _apply_ms6_gate(_receipt(habitat_type_diversity=1))["ms6_acceptance"] == "PENDING_MARKET_HABITAT_TYPE_DIVERSITY"


def test_ms6_gate_refuses_visibility_to_permission_inflation() -> None:
    assert _apply_ms6_gate(_receipt(public_visibility_is_dm_authority=True))["ms6_acceptance"] == "REFUSE_HABITAT_PERMISSION_OR_TRUTH_INFLATION"
    assert _apply_ms6_gate(_receipt(member_scraping_allowed=True))["ms6_acceptance"] == "REFUSE_HABITAT_PERMISSION_OR_TRUTH_INFLATION"
    assert _apply_ms6_gate(_receipt(authority_created=True))["ms6_acceptance"] == "REFUSE_HABITAT_PERMISSION_OR_TRUTH_INFLATION"
