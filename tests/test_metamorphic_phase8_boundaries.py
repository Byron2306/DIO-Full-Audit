from pathlib import Path

import pytest

from adapters.arda.metamorphic_execution import bind_arda_execution_evidence
from adapters.seraph.metamorphic_egress import bind_seraph_egress
from adapters.vns.metamorphic_witness import build_vns_witness
from metamorphic.boundary_closure import (
    PHASE8_EXIT_TOKEN,
    phase8_boundary_closure_receipt,
    validate_required_witnesses,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def receipt(tmp_path_factory):
    return phase8_boundary_closure_receipt(
        REPO_ROOT,
        work_root=tmp_path_factory.mktemp("phase8-boundary"),
    )


def _clean_authority():
    return {
        "authority_widened": False,
        "external_effects_authorized": False,
        "learning_used_as_authority": False,
        "effect_decisions": {
            "external_publication": "REFUSE",
            "external_send": "REFUSE",
            "media_spend": "REFUSE",
            "payment": "REFUSE",
        },
    }


def _minimal_execution():
    return {
        "composition_digest": "sha256:" + "1" * 64,
        "effect_hash": "sha256:" + "2" * 64,
        "all_native_nodes_passed": True,
        "sensorium_episode_complete": True,
        "authority_widened": False,
        "external_effects": False,
        "sensorium_episode": {"episode_hash": "sha256:" + "3" * 64},
    }


def test_phase8_receipt_passes(receipt):
    assert receipt["passed"] is True, receipt
    assert receipt["acceptance"] == PHASE8_EXIT_TOKEN
    assert receipt["composition_name"] == "Funding Proposal Studio"


def test_phase8_required_witnesses_are_explicit_and_complete(receipt):
    assert receipt["required_witnesses_complete"] is True
    assert receipt["witness_validation"]["missing"] == []
    assert receipt["witness_validation"]["failed_or_silent"] == []
    assert receipt["witness_validation"]["states"] == {
        "vns": "NOT_APPLICABLE",
        "seraph": "ARMED",
        "arda": "ARMED",
    }


def test_phase8_vns_explicitly_declares_not_applicable_for_artifact_only_run(receipt):
    assert receipt["vns_witness_explicit"] is True
    assert receipt["vns_witness_state"] == "NOT_APPLICABLE"
    vns = next(row for row in receipt["witnesses"] if row["organ"] == "vns")
    assert vns["network_effect_observed"] is False
    assert vns["vns_can_mint_authority"] is False


def test_phase8_vns_silence_is_not_accepted_when_network_effect_is_expected():
    witness = build_vns_witness(
        REPO_ROOT,
        execution=_minimal_execution(),
        external_network_effect_expected=True,
    )
    assert witness["state"] == "MISSING"
    assert validate_required_witnesses(
        [witness, {"organ": "seraph", "state": "ARMED", "explicit": True}, {"organ": "arda", "state": "ARMED", "explicit": True}]
    )["valid"] is False


def test_phase8_seraph_is_bound_and_refuses_external_effects(receipt):
    assert receipt["seraph_egress_bound"] is True
    assert receipt["seraph_witness_state"] == "ARMED"
    assert receipt["seraph_verdict"] == "REFUSE"
    assert receipt["seraph_operational_gate_executed"] is False


def test_phase8_seraph_fails_closed_if_authority_widens():
    authority = _clean_authority()
    authority["authority_widened"] = True
    witness = bind_seraph_egress(
        REPO_ROOT,
        authority=authority,
        world_lease_digest="sha256:" + "4" * 64,
        effect_hash="sha256:" + "5" * 64,
    )
    assert witness["state"] == "FAILED"
    assert witness["seraph_egress_bound"] is False
    assert witness["adapter_can_issue_allow"] is False


def test_phase8_seraph_fails_closed_if_any_effect_is_allowed():
    authority = _clean_authority()
    authority["effect_decisions"]["external_send"] = "ALLOW"
    witness = bind_seraph_egress(
        REPO_ROOT,
        authority=authority,
        world_lease_digest="sha256:" + "6" * 64,
        effect_hash="sha256:" + "7" * 64,
    )
    assert witness["state"] == "FAILED"
    assert witness["verdict"] == "REFUSE"


def test_phase8_arda_is_armed_and_native_execution_evidence_is_bound(receipt):
    assert receipt["arda_witness_state"] == "ARMED"
    assert receipt["arda_execution_evidence_bound"] is True
    arda = next(row for row in receipt["witnesses"] if row["organ"] == "arda")
    assert arda["reverse_evidence_contract_available"] is True
    assert arda["general_execution_authority_allowed"] is False


def test_phase8_arda_missing_if_execution_evidence_is_incomplete():
    execution = _minimal_execution()
    execution["effect_hash"] = "not-a-digest"
    witness = bind_arda_execution_evidence(REPO_ROOT, execution=execution)
    assert witness["state"] == "MISSING"
    assert witness["arda_execution_evidence_bound"] is False


def test_phase8_required_witness_silence_fails_closed():
    validation = validate_required_witnesses(
        [
            {"organ": "vns", "state": "NOT_APPLICABLE", "explicit": True},
            {"organ": "seraph", "state": "ARMED", "explicit": True},
        ]
    )
    assert validation["valid"] is False
    assert validation["missing"] == ["arda"]


def test_phase8_duplicate_witness_identity_fails_closed():
    validation = validate_required_witnesses(
        [
            {"organ": "vns", "state": "NOT_APPLICABLE", "explicit": True},
            {"organ": "seraph", "state": "ARMED", "explicit": True},
            {"organ": "arda", "state": "ARMED", "explicit": True},
            {"organ": "arda", "state": "ARMED", "explicit": True},
        ]
    )
    assert validation["valid"] is False
    assert validation["duplicates"] == ["arda"]


def test_phase8_learning_and_harmonics_remain_non_authoritative(receipt):
    assert receipt["learning_candidate_only"] is True
    assert receipt["direct_learning_to_execution"] is False
    assert receipt["learning_used_as_authority"] is False
    assert receipt["harmonics_executed"] is True
    assert receipt["harmonic_state_is_authority"] is False
    assert receipt["authority_widened"] is False


def test_phase8_does_not_fake_operational_seraph_or_arda_physical_execution(receipt):
    assert receipt["seraph_operational_gate_executed"] is False
    assert receipt["arda_bounded_replay_executed"] is False
    assert receipt["arda_physical_transport_executed"] is False
    assert receipt["external_effects"] is False
    assert receipt["external_effects_authorized"] is False


def test_phase8_does_not_jump_to_settlement_crystallisation_or_market(receipt):
    assert receipt["world_settlement_performed"] is False
    assert receipt["beast_crystallization_executed"] is False
    assert receipt["market_feedback_learning_executed"] is False
    assert receipt["new_engine_created"] is False
