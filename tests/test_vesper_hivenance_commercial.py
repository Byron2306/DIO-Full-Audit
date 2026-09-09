from copy import deepcopy
from pathlib import Path

from products.commercial_pricing_registry import build_commercial_pricing_registry
from products.hivenance_commercial_pricing import (
    admit_pricing_hypothesis,
    assess_pricing_hypothesis,
)


ROOT = Path(__file__).resolve().parents[1]


def _profile(name: str):
    registry = build_commercial_pricing_registry(ROOT)
    return next(row for row in registry["products"] if row["name"] == name)


def _paid(amount: int, *, quote: int | None = None, scope_units: int = 1):
    return {
        "kind": "commercial_outcome",
        "quote_amount": quote if quote is not None else amount,
        "final_invoice_amount": amount,
        "payment_state": "verified",
        "quote_state": "accepted",
        "scope_units": scope_units,
        "simulated": False,
    }


def _rejected(quote: int, *, scope_units: int = 1):
    return {
        "kind": "commercial_outcome",
        "quote_amount": quote,
        "final_invoice_amount": None,
        "payment_state": "unverified",
        "quote_state": "rejected",
        "scope_units": scope_units,
        "simulated": False,
    }


def test_hivenance_pricing_lane_has_full_challenge_council_and_no_authority():
    receipt = assess_pricing_hypothesis(_profile("Sophia Integrity"), [])

    assert receipt["schema"] == "dio.hivenance.commercial_pricing_hypothesis.v1"
    assert receipt["council"]["decision"] == "TEST"
    assert receipt["oracle"]["regime"] == "UNTESTED"
    assert receipt["michael"]["role"] == "evidence_validator"
    assert receipt["loki"]["role"] == "adversarial_challenger"
    assert receipt["metatron"]["role"] == "synthesizer"
    assert receipt["ainur"]["role"] == "strategy_council"
    assert receipt["authority_created"] is False
    assert receipt["external_effects"] is False
    assert receipt["pricing_registry_mutated"] is False


def test_search_or_attention_signals_cannot_promote_price_without_paid_settlement():
    profile = _profile("Evidex EvidenceOps")
    observations = [
        {
            "kind": "market_signal",
            "signal": "high_search_attention",
            "score": 0.93,
            "simulated": False,
        }
        for _ in range(20)
    ]
    receipt = assess_pricing_hypothesis(profile, observations)

    assert receipt["settlement"]["verified_payments"] == 0
    assert receipt["council"]["decision"] in {"TEST", "REFINE", "HOLD"}
    assert receipt["council"]["decision"] != "PROMOTE"
    assert receipt["customers_will_pay"] == "UNPROVED"


def test_repeated_verified_paid_response_can_recommend_promotion_but_not_mutate_registry():
    profile = _profile("Evidex EvidenceOps")
    observations = [
        _paid(950),
        _paid(1100),
        _paid(1200),
        _paid(1150),
        _paid(1250),
        _paid(1000),
        _paid(1300),
        _paid(1200),
        _rejected(1450),
        _rejected(1500),
    ]
    receipt = assess_pricing_hypothesis(profile, observations)

    assert receipt["settlement"]["verified_payments"] == 8
    assert receipt["settlement"]["accepted_quotes"] == 8
    assert receipt["settlement"]["rejected_quotes"] == 2
    assert receipt["oracle"]["regime"] == "MEASURED_RESPONSE"
    assert receipt["council"]["decision"] == "PROMOTE"
    assert receipt["customers_will_pay"] == "OBSERVED_BOUNDED_RESPONSE"
    assert receipt["pricing_registry_mutated"] is False
    assert receipt["authority_created"] is False


def test_price_resistance_refines_instead_of_declaring_failure_or_success():
    profile = _profile("Sophia Integrity")
    high = profile["reference_band_zar"]["max"]
    observations = [_rejected(high) for _ in range(7)] + [_paid(profile["reference_band_zar"]["min"]) for _ in range(2)]
    receipt = assess_pricing_hypothesis(profile, observations)

    assert receipt["oracle"]["regime"] == "PRICE_RESISTANCE"
    assert receipt["council"]["decision"] == "REFINE"
    assert receipt["council"]["selected_family"] == "lower_or_repackage"
    assert receipt["commercial_validation"] != "PROVEN_MARKET_FIT"


def test_simulated_outcomes_are_excluded_from_settlement():
    profile = _profile("VAMP Performance")
    observations = [dict(_paid(1500), simulated=True) for _ in range(12)]
    receipt = assess_pricing_hypothesis(profile, observations)

    assert receipt["settlement"]["eligible_observations"] == 0
    assert receipt["settlement"]["verified_payments"] == 0
    assert receipt["council"]["decision"] == "TEST"


def test_no_direct_learning_to_quote_authority_operator_admission_is_required():
    profile = _profile("Evidex EvidenceOps")
    observations = [_paid(1100 + (i % 3) * 50) for i in range(8)]
    receipt = assess_pricing_hypothesis(profile, observations)
    original = deepcopy(profile)

    held = admit_pricing_hypothesis(profile, receipt, operator_approved=False)
    assert held["admission_state"] == "PROPOSED"
    assert held["pricing_profile"] == original
    assert held["quote_authority_created"] is False

    admitted = admit_pricing_hypothesis(profile, receipt, operator_approved=True)
    assert admitted["admission_state"] == "ADMITTED"
    assert admitted["pricing_profile"]["pricing_state"] == "PROMOTED_HYPOTHESIS"
    assert admitted["pricing_profile"]["commercial_validation"] == "BOUNDED_PAID_RESPONSE_OBSERVED"
    assert admitted["quote_authority_created"] is False
    assert admitted["external_action_executed"] is False
