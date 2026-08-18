from dataclasses import replace
from pathlib import Path

import pytest

from commercial_metabolism.contracts import MarketObservation, MarketObservationKind
from commercial_metabolism.observation import (
    M2_PHASE5_EXIT_TOKEN,
    exercise_controlled_observation_scenarios,
    phase5_market_observation_receipt,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def phase_receipt():
    return phase5_market_observation_receipt(REPO_ROOT)


@pytest.fixture(scope="module")
def observed(tmp_path_factory):
    episodes, evidence = exercise_controlled_observation_scenarios(
        REPO_ROOT,
        work_root=tmp_path_factory.mktemp("m2_phase5_observation"),
    )
    return {row.scenario_id: row for row in episodes}, evidence


def test_m2_phase5_gate_passes(phase_receipt):
    assert phase_receipt["passed"] is True, phase_receipt
    assert phase_receipt["acceptance"] == M2_PHASE5_EXIT_TOKEN
    assert phase_receipt["phase"] == "M2-5"


def test_phase5_requires_verified_m2_phase4_parent(phase_receipt):
    assert phase_receipt["parent_acceptance"] == "DIO_M2_MARKET_EPISODE_READY"
    assert phase_receipt["parent_verified"] is True


def test_all_three_controlled_response_paths_are_exercised(phase_receipt, observed):
    episodes, _evidence = observed
    assert set(episodes) == {"positive_response", "negative_response", "no_response"}
    assert {row.outcome_class for row in episodes.values()} == {
        "POSITIVE_RESPONSE",
        "NEGATIVE_RESPONSE",
        "NO_RESPONSE",
    }
    assert phase_receipt["controlled_market_response_paths_exercised"] is True


def test_observation_scope_is_explicitly_controlled_not_real_market(phase_receipt, observed):
    episodes, _evidence = observed
    assert phase_receipt["observation_mode"] == "source_bound_controlled_fixture"
    assert phase_receipt["real_market_exposure_observed"] is False
    assert phase_receipt["real_market_response_observed"] is False
    assert all(row.controlled_fixture is True for row in episodes.values())
    assert all(row.real_market_exposure_observed is False for row in episodes.values())


def test_positive_response_is_an_enquiry_observation(observed):
    _episodes, evidence = observed
    row = evidence["rows"]["positive_response"]["observation"]
    assert row["kind"] == "ENQUIRY"
    assert row["context_digest"] == evidence["plan"].context_digest


def test_negative_response_is_a_rejection_observation(observed):
    _episodes, evidence = observed
    row = evidence["rows"]["negative_response"]["observation"]
    assert row["kind"] == "REJECTION"
    assert row["context_digest"] == evidence["plan"].context_digest


def test_no_response_requires_and_has_closed_window(observed, phase_receipt):
    _episodes, evidence = observed
    row = evidence["rows"]["no_response"]["observation"]
    assert row["kind"] == "NO_RESPONSE"
    assert row["window_closed"] is True
    assert phase_receipt["no_response_window_closed"] is True
    assert phase_receipt["no_response_scope"] == "exact_commercial_context_only"


def test_market_command_scenario_worlds_are_isolated_draft_and_held(observed, phase_receipt):
    _episodes, evidence = observed
    base = evidence["base_campaign"]
    assert base["state"] == "draft"
    assert base["publication_state"] == "held"
    for row in evidence["rows"].values():
        assert row["campaign"]["state"] == "draft"
        assert row["campaign"]["publication_state"] == "held"
    assert phase_receipt["market_command_existing_organ_reused"] is True
    assert phase_receipt["market_command_scenario_worlds_isolated"] is True
    assert phase_receipt["market_command_scenario_campaigns_held"] is True
    assert phase_receipt["activation_performed"] is False


def test_sensorium_closes_evidence_only_episode_for_each_path(observed, phase_receipt):
    episodes, evidence = observed
    assert phase_receipt["sensorium_existing_organ_reused"] is True
    assert phase_receipt["sensorium_complete"] is True
    assert phase_receipt["sensorium_episode_count"] == 3
    for scenario_id, episode in episodes.items():
        sensorium = evidence["rows"][scenario_id]["sensorium"]
        assert sensorium["authority"] == "evidence_only"
        assert episode.sensorium_episode_hash.startswith("sha256:")
        assert len(episode.sensorium_event_ids) >= 3


def test_all_observations_bind_exact_market_episode_context(observed):
    episodes, evidence = observed
    plan = evidence["plan"]
    assert all(row.episode_plan_digest == plan.plan_digest for row in episodes.values())
    assert all(row.context_digest == plan.context_digest for row in episodes.values())


def test_stable_observation_truth_excludes_volatile_sensorium_receipt_identity(observed):
    episodes, _evidence = observed
    original = episodes["positive_response"]
    twin = replace(
        original,
        sensorium_episode_hash="sha256:" + "a" * 64,
        sensorium_event_ids=("different-event-1", "different-event-2", "different-event-3"),
    )
    assert twin.observation_truth_digest == original.observation_truth_digest
    assert twin.episode_evidence_digest != original.episode_evidence_digest


def test_no_response_cannot_be_constructed_for_open_window(observed):
    _episodes, evidence = observed
    row = evidence["rows"]["no_response"]["observation"]
    with pytest.raises(ValueError):
        MarketObservation(
            observation_id="OBS-OPEN-SILENCE",
            context_digest=row["context_digest"],
            observed_at=row["observed_at"],
            kind=MarketObservationKind.NO_RESPONSE,
            source=row["source"],
            source_ref=row["source_ref"],
            window_start=row["window_start"],
            window_end=row["window_end"],
            window_closed=False,
            evidence_refs=tuple(row["evidence_refs"]),
        )


def test_positive_response_does_not_prove_payment_acceptance_wtp_or_validation(phase_receipt):
    assert phase_receipt["payment_verified"] is False
    assert phase_receipt["customer_acceptance_observed"] is False
    assert phase_receipt["willingness_to_pay_proved"] is False
    assert phase_receipt["commercial_validation_proved"] is False
    assert phase_receipt["repeatability_proved"] is False


def test_negative_response_does_not_globally_invalidate_product(phase_receipt, observed):
    episodes, _evidence = observed
    assert episodes["negative_response"].product_globally_invalidated is False
    assert phase_receipt["negative_response_globally_invalidates_product"] is False


def test_silence_is_context_scoped_not_global_product_failure(phase_receipt, observed):
    episodes, _evidence = observed
    assert episodes["no_response"].product_globally_invalidated is False
    assert phase_receipt["silence_globally_invalidates_product"] is False
    assert phase_receipt["no_response_scope"] == "exact_commercial_context_only"


def test_phase5_does_not_settle_or_crystallise_market_truth(phase_receipt):
    assert phase_receipt["commercial_settlement_performed"] is False
    assert phase_receipt["market_crystal_created"] is False


def test_observation_episode_refuses_overclaiming_or_external_effects(observed):
    episodes, _evidence = observed
    row = episodes["positive_response"]
    with pytest.raises(ValueError):
        replace(row, commercial_validation_proved=True)
    with pytest.raises(ValueError):
        replace(row, authority_created=True)
    with pytest.raises(ValueError):
        replace(row, external_effects=True)


def test_phase5_schema_and_no_runtime_or_authority_widening(phase_receipt):
    assert phase_receipt["passed"] is True
    assert phase_receipt["authority_created"] is False
    assert phase_receipt["authority_widened"] is False
    assert phase_receipt["external_effects"] is False
    assert phase_receipt["seraph_operational_gate_executed"] is False
    assert phase_receipt["new_runtime_engine_created"] is False
    assert phase_receipt["m2_final_verified"] is False
