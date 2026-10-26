from __future__ import annotations

from scripts.run_market_sensorium_cycle import _apply_ms4_gate


def _receipt(**overrides):
    phoenix = {
        "movement_events_examined": 2,
        "hypothesis_sets_created": 2,
        "hypotheses_created": 10,
        "rival_sets_with_3plus": 2,
        "source_bound_hypotheses": 10,
        "michael_validated_hypotheses": 10,
        "loki_challenged_hypotheses": 10,
        "metatron_synthesized_hypotheses": 10,
        "selected_bounded_tests": 2,
        "unbounded_or_authority_tests": 0,
        "sets_without_source_evidence": 0,
        "truth_claims_created": 0,
        "hypothesis_type_counts": {
            "BUYER": 2,
            "CHANNEL": 2,
            "TIMING": 2,
            "COMPETITION": 2,
            "PRODUCT": 2,
        },
        "authority_created": False,
        "outreach_authority_created": False,
        "publication_authority_created": False,
        "spend_authority_created": False,
        "commerce_authority_created": False,
    }
    phoenix.update(overrides)
    return {
        "ms3_acceptance": "DIO_MARKET_SENSORIUM_DYNAMIC_RANK_MOVEMENT_VERIFIED",
        "summary": {"store": {"commercial_phoenix": phoenix}},
    }


def test_ms4_gate_verifies_rival_source_bound_bounded_research() -> None:
    receipt = _apply_ms4_gate(_receipt())
    assert receipt["ms4_acceptance"] == "DIO_MARKET_SENSORIUM_HIVENANCE_COMMERCIAL_PHOENIX_V2_VERIFIED"
    truth = receipt["ms4_truth"]
    assert truth["hypothesis_is_fact"] is False
    assert truth["selected_hypothesis_is_truth"] is False
    assert truth["selected_test_is_execution_authority"] is False
    assert truth["authority_created"] is False
    assert truth["market_demand_claimed"] is False


def test_ms4_gate_refuses_single_story_without_rival_hypotheses() -> None:
    receipt = _apply_ms4_gate(
        _receipt(hypotheses_created=2, rival_sets_with_3plus=0)
    )
    assert receipt["ms4_acceptance"] == "REFUSE_NON_RIVAL_COMMERCIAL_HYPOTHESIS_SET"


def test_ms4_gate_requires_all_hypotheses_to_be_source_bound() -> None:
    receipt = _apply_ms4_gate(
        _receipt(source_bound_hypotheses=9, sets_without_source_evidence=1)
    )
    assert receipt["ms4_acceptance"] == "PENDING_SOURCE_BOUND_COMMERCIAL_HYPOTHESES"


def test_ms4_gate_refuses_incomplete_triune_challenge() -> None:
    receipt = _apply_ms4_gate(_receipt(loki_challenged_hypotheses=9))
    assert receipt["ms4_acceptance"] == "REFUSE_INCOMPLETE_HIVENANCE_TRIUNE_CHALLENGE"


def test_ms4_gate_refuses_authority_or_truth_promotion() -> None:
    receipt = _apply_ms4_gate(_receipt(truth_claims_created=1))
    assert receipt["ms4_acceptance"] == "REFUSE_HYPOTHESIS_TRUTH_OR_AUTHORITY_PROMOTION"
    receipt = _apply_ms4_gate(_receipt(outreach_authority_created=True))
    assert receipt["ms4_acceptance"] == "REFUSE_HYPOTHESIS_TRUTH_OR_AUTHORITY_PROMOTION"


def test_ms4_gate_waits_for_verified_ms3_input() -> None:
    receipt = _receipt()
    receipt["ms3_acceptance"] = "PENDING_DYNAMIC_RANK_MOVEMENT"
    receipt = _apply_ms4_gate(receipt)
    assert receipt["ms4_acceptance"] == "PENDING_MS3_DYNAMIC_RANK_INPUT"
