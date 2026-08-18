from pathlib import Path

import pytest

from adapters.beast.metamorphic_crystallisation import (
    MetamorphicCrystallisationError,
    crystallize_settled_composition,
)
from metamorphic.boundary_closure import phase8_boundary_closure_receipt
from metamorphic.contracts import MetamorphicRole, SettlementState
from metamorphic.crystallisation import PHASE9_EXIT_TOKEN, phase9_m1_receipt
from metamorphic.registry import build_reference_registry
from metamorphic.settlement import settle_boundary_episode
from products.funding_proposal_studio import (
    COMPOSITE_CAPABILITY,
    COMPOSITE_UNIT_ID,
    build_funding_proposal_metamorphic_unit,
    run_funding_proposal_studio,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def receipt(tmp_path_factory):
    return phase9_m1_receipt(
        REPO_ROOT,
        work_root=tmp_path_factory.mktemp("phase9-m1"),
    )


@pytest.fixture(scope="module")
def boundary(tmp_path_factory):
    return phase8_boundary_closure_receipt(
        REPO_ROOT,
        work_root=tmp_path_factory.mktemp("phase9-boundary-hostile"),
    )


def test_phase9_m1_receipt_passes(receipt):
    assert receipt["passed"] is True, receipt
    assert receipt["acceptance"] == PHASE9_EXIT_TOKEN
    assert receipt["composition_name"] == "Funding Proposal Studio"


def test_phase9_all_frozen_m1_acceptance_gates_are_green(receipt):
    assert receipt["acceptance_gate_count"] == 23
    assert receipt["acceptance_gate_pass_count"] == 23
    assert all(receipt["acceptance_gates"].values())


def test_phase9_world_settlement_is_complete_before_crystallisation(receipt):
    settlement = receipt["world_settlement"]
    assert receipt["world_settlement_complete"] is True
    assert settlement["passed"] is True
    assert settlement["settlement"]["settlement_state"] == "SETTLED"
    assert settlement["red_gates"] == []


def test_phase9_world_fact_drift_fractures_settlement(boundary):
    hostile = dict(boundary)
    hostile["world_facts_digest"] = "sha256:" + "0" * 64
    result = settle_boundary_episode(REPO_ROOT, boundary_receipt=hostile)
    assert result.passed is False
    assert result.settlement.settlement_state is SettlementState.FRACTURED
    assert "world_facts_stable" in result.red_gates
    assert "world_facts_drift" in result.settlement.unexpected_effects


def test_phase9_crystallisation_refuses_unsettled_episode(boundary, tmp_path):
    hostile = dict(boundary)
    hostile["world_facts_digest"] = "sha256:" + "f" * 64
    result = settle_boundary_episode(REPO_ROOT, boundary_receipt=hostile)
    with pytest.raises(MetamorphicCrystallisationError, match="SETTLED"):
        crystallize_settled_composition(
            REPO_ROOT,
            settlement_result=result,
            boundary_receipt=hostile,
            state_root=tmp_path / "blocked-crystal",
        )
    assert not (tmp_path / "blocked-crystal" / "crystal_chain.jsonl").exists()


def test_phase9_beast_crystal_is_hash_chained_and_evidence_only(receipt):
    crystal = receipt["beast_crystal"]
    assert crystal["beast_crystallization_executed"] is True
    assert crystal["crystal_chain_valid"] is True
    assert crystal["crystal_chain_block_count"] == 1
    assert str(crystal["crystal_block_hash"]).startswith("sha256:")
    assert crystal["authority"] == "evidence_only"
    assert crystal["authority_created"] is False


def test_phase9_crystal_is_bound_to_exact_settlement(receipt):
    assert receipt["beast_crystal"]["settlement_digest"] == receipt["settlement_digest"]
    assert receipt["acceptance_gates"]["CRYSTALLISATION_GATED"] is True


def test_phase9_composite_reenters_registry_as_same_object(receipt):
    assert receipt["registry_count_before"] == 3
    assert receipt["registry_count_after"] == 4
    assert receipt["same_composite_identity_across_roles"] is True
    assert receipt["composite_provider_reentry"] is True


def test_phase9_composite_unit_digest_is_stable_across_builds():
    first = build_funding_proposal_metamorphic_unit(REPO_ROOT)
    second = build_funding_proposal_metamorphic_unit(REPO_ROOT)
    assert first.unit_digest == second.unit_digest
    assert first.unit_id == second.unit_id == COMPOSITE_UNIT_ID


def test_phase9_composite_unit_has_product_and_capability_roles():
    unit = build_funding_proposal_metamorphic_unit(REPO_ROOT)
    assert unit.roles == (MetamorphicRole.PRODUCT, MetamorphicRole.CAPABILITY)
    assert unit.provides == (COMPOSITE_CAPABILITY,)


def test_phase9_composite_requires_the_three_existing_capabilities():
    unit = build_funding_proposal_metamorphic_unit(REPO_ROOT)
    assert set(unit.requires) == {
        "finance_readiness",
        "article_publication",
        "professional_correspondence",
    }


def test_phase9_expanded_registry_indexes_composite_capability():
    registry = build_reference_registry(REPO_ROOT)
    unit = registry.register(build_funding_proposal_metamorphic_unit(REPO_ROOT))
    providers = registry.providers_for(COMPOSITE_CAPABILITY)
    assert providers == (unit,)
    assert registry.as_role(COMPOSITE_UNIT_ID, "product") is unit
    assert registry.as_role(COMPOSITE_UNIT_ID, "capability") is unit


def test_phase9_product_wrapper_reuses_existing_resolver_and_native_execution(tmp_path):
    execution = run_funding_proposal_studio(
        REPO_ROOT,
        output_dir=tmp_path / "funding-proposal-wrapper",
    )
    assert execution["composition_name"] == "Funding Proposal Studio"
    assert execution["all_native_nodes_passed"] is True
    assert execution["native_executors_only"] is True
    assert execution["same_unit_identity_preserved"] is True
    assert execution["new_engine_created"] is False


def test_phase9_does_not_overclaim_content_transform_dataflow(receipt):
    assert receipt["content_transform_dataflow_proved"] is False
    unit = build_funding_proposal_metamorphic_unit(REPO_ROOT)
    assert unit.output_contract["content_transform_dataflow_proved"] is False


def test_phase9_never_widens_authority_or_creates_external_effects(receipt):
    assert receipt["authority_widened"] is False
    assert receipt["external_effects"] is False
    assert receipt["new_engine_created"] is False
    assert receipt["acceptance_gates"]["NO_AUTHORITY_ESCALATION"] is True


def test_phase9_m1_is_not_the_end_of_required_programme(receipt):
    assert receipt["m2_required_next"] is True
    assert receipt["m2_required_acceptance"] == "DIO_METAMORPHIC_COMMERCIAL_METABOLISM_VERIFIED"
    assert receipt["m2_verified"] is False
    assert receipt["programme_complete"] is False
