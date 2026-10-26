from pathlib import Path

import pytest

from adapters.beast.metamorphic_learning import load_beast_learning_classes
from adapters.harmonics.metamorphic_state import load_harmonic_inference
from metamorphic.learning import PHASE7_EXIT_TOKEN, phase7_learning_receipt


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def receipt(tmp_path_factory):
    return phase7_learning_receipt(REPO_ROOT, work_root=tmp_path_factory.mktemp("phase7"))


def test_phase7_receipt_passes(receipt):
    assert receipt["passed"] is True, receipt
    assert receipt["acceptance"] == PHASE7_EXIT_TOKEN
    assert receipt["composition_name"] == "Funding Proposal Studio"


def test_phase7_records_real_beast_learning_candidate(receipt):
    assert receipt["beast_learning_event_count"] == 1
    assert str(receipt["beast_learning_event_digest"]).startswith("sha256:")
    assert receipt["learning_candidate_only"] is True


def test_phase7_learning_never_becomes_execution_authority(receipt):
    assert receipt["direct_learning_to_execution"] is False
    assert receipt["learning_used_as_authority"] is False
    assert receipt["authority_widened"] is False


def test_phase7_success_does_not_create_false_negative_capability(receipt):
    assert receipt["negative_capability_store_reused"] is True
    assert receipt["active_negative_capability_count"] == 0


def test_phase7_negative_capability_activates_only_after_three_repeated_failures(tmp_path):
    _, NegativeCapabilityStore, OutcomeEvidence = load_beast_learning_classes(REPO_ROOT)
    store = NegativeCapabilityStore(tmp_path / "negative.json")
    scope = {"route": "Funding Proposal Studio", "tool": "native"}
    states = []
    for index in range(3):
        row = OutcomeEvidence.create(
            capability_id="hostile_unit",
            task_class="metamorphic_node_execution",
            outcome="failure",
            failure_category="controlled_failure",
            failure_code="X1",
            detail="same controlled failure",
            scope=scope,
            evidence_id=f"failure-{index}",
        )
        record = store.record(row)
        states.append(record.state)
    assert states[:2] == ["observing", "observing"]
    assert states[2] == "active"
    assert len(store.active_matches({"capability_id": "hostile_unit", "task_class": "metamorphic_node_execution", "scope": scope})) == 1


def test_phase7_negative_capability_can_enter_revalidation_after_clean_successes(tmp_path):
    _, NegativeCapabilityStore, OutcomeEvidence = load_beast_learning_classes(REPO_ROOT)
    store = NegativeCapabilityStore(tmp_path / "negative.json")
    scope = {"route": "Funding Proposal Studio", "tool": "native"}
    for index in range(3):
        store.record(OutcomeEvidence.create(
            capability_id="recovering_unit", task_class="metamorphic_node_execution", outcome="failure",
            failure_category="controlled_failure", detail="same", scope=scope, evidence_id=f"failure-{index}",
        ))
    for index in range(2):
        record = store.record(OutcomeEvidence.create(
            capability_id="recovering_unit", task_class="metamorphic_node_execution", outcome="success",
            scope=scope, evidence_id=f"success-{index}",
        ))
    assert record.state == "revalidation"


def test_phase7_harmonics_executes_canonical_inference_policy(receipt):
    assert receipt["harmonics_executed"] is True
    assert receipt["harmonic_mode"] == "normal_flow"
    assert receipt["harmonic_state"]["harmonic_state_is_authority"] is False


def test_phase7_harmonic_projection_does_not_claim_live_cadence(receipt):
    assert receipt["harmonic_projection_kind"] == "sensorium_structural_projection"
    assert receipt["live_cadence_scoring_claimed"] is False


def test_phase7_canonical_harmonics_low_confidence_fails_to_observe_and_review():
    inference = load_harmonic_inference(REPO_ROOT)
    mode, rationale = inference.mode_recommendation(1.0, 0.0, 0.2)
    assert mode == "observe_and_review"
    assert rationale


def test_phase7_learning_is_bound_to_sensorium_and_effect(receipt):
    assert str(receipt["sensorium_episode_hash"]).startswith("sha256:")
    assert str(receipt["effect_hash"]).startswith("sha256:")
    assert str(receipt["composition_digest"]).startswith("sha256:")


def test_phase7_does_not_crystallize_candidate_yet(receipt):
    assert receipt["beast_crystallization_executed"] is False


def test_phase7_does_not_jump_to_seraph_arda_settlement_or_market(receipt):
    assert receipt["seraph_egress_executed"] is False
    assert receipt["arda_execution_performed"] is False
    assert receipt["world_settlement_performed"] is False
    assert receipt["market_feedback_learning_executed"] is False
    assert receipt["new_engine_created"] is False
