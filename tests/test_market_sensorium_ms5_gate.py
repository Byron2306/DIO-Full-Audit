from __future__ import annotations

from scripts.run_market_sensorium_ms5 import _apply_ms5_gate


def _receipt(**overrides):
    offers = {
        "source_bound_offer_observations": 3,
        "canonical_competitive_offers": 3,
        "unique_sellers_observed_this_run": 2,
        "explicit_advertised_price_observations": 1,
        "price_state_counts": {
            "EXPLICIT_FREE_ADVERTISED": 1,
            "PRICE_NOT_OBSERVED": 2,
        },
        "price_normalization_errors": 0,
        "provider_role_confusion": 0,
        "multi_source_dedupe_groups": 0,
        "persisted_competitive_offer_events": 3,
        "legacy_offer_observation_count": 3,
        "source_bound": True,
        "publisher_auto_promoted_to_seller": False,
        "advertised_price_is_market_price": False,
        "advertised_price_is_realised_price": False,
        "willingness_to_pay_proved": False,
        "market_demand_claimed": False,
        "authority_created": False,
        "external_effects": False,
    }
    offers.update(overrides)
    return {
        "ms4_acceptance": "DIO_MARKET_SENSORIUM_HIVENANCE_COMMERCIAL_PHOENIX_V2_VERIFIED",
        "summary": {"competitive_offers": offers},
    }


def test_ms5_gate_verifies_source_bound_multi_seller_offer_and_price_evidence() -> None:
    receipt = _apply_ms5_gate(_receipt())
    assert receipt["ms5_acceptance"] == "DIO_MARKET_SENSORIUM_COMPETITIVE_OFFER_INTELLIGENCE_VERIFIED"
    truth = receipt["ms5_truth"]
    assert truth["advertised_offer_is_demand"] is False
    assert truth["advertised_price_is_market_price"] is False
    assert truth["advertised_price_is_realised_price"] is False
    assert truth["willingness_to_pay_proved"] is False
    assert truth["authority_created"] is False


def test_ms5_gate_requires_verified_ms4_receipt() -> None:
    receipt = _receipt()
    receipt["ms4_acceptance"] = "PENDING_COMMERCIAL_HYPOTHESIS_DIVERSITY"
    result = _apply_ms5_gate(receipt)
    assert result["ms5_acceptance"] == "PENDING_VERIFIED_MS4_RECEIPT"


def test_ms5_gate_requires_real_offer_evidence() -> None:
    result = _apply_ms5_gate(_receipt(source_bound_offer_observations=0, canonical_competitive_offers=0))
    assert result["ms5_acceptance"] == "PENDING_COMPETITIVE_OFFER_EVIDENCE"


def test_ms5_gate_requires_multiple_sellers_for_competitive_claim() -> None:
    result = _apply_ms5_gate(_receipt(unique_sellers_observed_this_run=1))
    assert result["ms5_acceptance"] == "PENDING_MULTI_SELLER_COMPETITIVE_EVIDENCE"


def test_ms5_gate_refuses_seller_source_role_confusion() -> None:
    result = _apply_ms5_gate(_receipt(provider_role_confusion=1))
    assert result["ms5_acceptance"] == "REFUSE_SELLER_SOURCE_ROLE_CONFUSION"
    result = _apply_ms5_gate(_receipt(publisher_auto_promoted_to_seller=True))
    assert result["ms5_acceptance"] == "REFUSE_SELLER_SOURCE_ROLE_CONFUSION"


def test_ms5_gate_waits_for_explicit_price_evidence() -> None:
    result = _apply_ms5_gate(_receipt(explicit_advertised_price_observations=0))
    assert result["ms5_acceptance"] == "PENDING_EXPLICIT_ADVERTISED_PRICE_EVIDENCE"


def test_ms5_gate_refuses_price_or_authority_inflation() -> None:
    result = _apply_ms5_gate(_receipt(advertised_price_is_market_price=True))
    assert result["ms5_acceptance"] == "REFUSE_OFFER_PRICE_TRUTH_OR_AUTHORITY_INFLATION"
    result = _apply_ms5_gate(_receipt(willingness_to_pay_proved=True))
    assert result["ms5_acceptance"] == "REFUSE_OFFER_PRICE_TRUTH_OR_AUTHORITY_INFLATION"
    result = _apply_ms5_gate(_receipt(authority_created=True))
    assert result["ms5_acceptance"] == "REFUSE_OFFER_PRICE_TRUTH_OR_AUTHORITY_INFLATION"
