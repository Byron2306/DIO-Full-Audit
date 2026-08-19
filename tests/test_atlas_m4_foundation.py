from pathlib import Path

import pytest

from atlas import (
    ATLAS_FOUNDATION_TOKEN,
    ATLAS_PIVOT_TOKEN,
    AtlasRegistry,
    atlas_foundation_receipt,
    atlas_pivot_foundation_receipt,
    compile_negative_learning_pivot,
    evaluate_pivot_gauntlet,
    pivot_candidates,
    resolve_task,
)
from commercial_metabolism.learning import phase8_projection_adaptation_receipt


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def registry():
    return AtlasRegistry.load(REPO_ROOT)


@pytest.fixture(scope="module")
def foundation():
    return atlas_foundation_receipt(REPO_ROOT)


@pytest.fixture(scope="module")
def pivot_receipt():
    return atlas_pivot_foundation_receipt(REPO_ROOT)


def test_atlas_foundation_gate_passes(foundation):
    assert foundation["passed"] is True, foundation
    assert foundation["acceptance"] == ATLAS_FOUNDATION_TOKEN
    assert foundation["phase"] == "M4-0"


def test_atlas_reverifies_verified_m1_m2_parent_and_preserves_m3_boundary(foundation):
    assert foundation["parent_acceptance"] == "DIO_METAMORPHIC_COMMERCIAL_METABOLISM_VERIFIED"
    assert foundation["m1_verified"] is True
    assert foundation["m2_verified"] is True
    assert foundation["m3_boundary_preserved"] is True
    assert foundation["content_transform_dataflow_proved"] is False


def test_source_federation_is_broad_but_knowledge_only(registry, foundation):
    assert foundation["source_federation_count"] >= 12
    assert foundation["all_external_taxonomy_knowledge_capability_effect_none"] is True
    assert all(row["capability_effect"] == "NONE" for row in registry.sources)


def test_universal_work_primitive_vocabulary_is_material(registry, foundation):
    assert foundation["work_primitive_count"] >= 50
    assert {"P003", "P006", "P017", "P038", "P048", "P056"} <= registry.primitive_ids


def test_twelve_dio_meta_work_patterns_remain_canonical_and_learning_gap_is_explicit(foundation, registry):
    assert foundation["canonical_work_pattern_count"] == 12
    assert foundation["candidate_work_pattern_count"] == 1
    assert foundation["learning_gap_preserved"] is True
    wp13 = next(row for row in registry.work_patterns if row["work_pattern_id"] == "WP13")
    assert wp13["canonical_status"] == "CANDIDATE_EXTENSION"


def test_all_53_existing_portfolio_incarnations_are_crosswalked(foundation, registry):
    assert foundation["portfolio_incarnation_crosswalk_count"] == 53
    assert len(registry.incarnations) == 53
    assert len({row["incarnation"] for row in registry.incarnations}) == 53


def test_capability_cost_is_first_class_and_derived_from_original_burdens(registry):
    for row in registry.incarnations:
        score = (float(row["build_burden"]) + float(row["validation_burden"])) / 2.0
        assert float(row["capability_cost_score"]) == score
        assert row["capability_cost"] in {"LOW", "LOW_MEDIUM", "MEDIUM", "HIGH", "VERY_HIGH"}


def test_domain_registry_spans_broad_federation_and_keeps_unknown_domain_probe(registry, foundation):
    assert foundation["domain_seed_count"] >= 120
    families = {row["domain_family"] for row in registry.domains}
    assert {
        "PRIMARY", "INDUSTRY", "INFRASTRUCTURE", "COMMERCE", "INFORMATION",
        "FINANCE", "PROFESSIONAL", "PUBLIC", "EDUCATION", "HEALTH", "SCIENCE",
        "ENGINEERING", "SOCIAL", "HUMANITIES", "ORGANISATION", "CIVIL", "CROSSCUTTING",
    } <= families
    assert registry.domain("D1800")["atlas_status"] == "UNKNOWN_DOMAIN_TEST_ONLY"


def test_atlas_execution_truth_is_only_four_m1_bound_capability_signatures(registry, foundation):
    assert foundation["capability_signature_count"] == 4
    assert foundation["execution_signature_binding_count"] == 4
    assert registry.capability_ids == {
        "professional_correspondence",
        "finance_readiness",
        "article_publication",
        "funding_proposal_pack",
    }


def test_signatures_bind_back_to_current_exact_metamorphic_units(registry):
    bindings = registry.bind_execution_signatures()
    assert bindings["professional_correspondence"]["unit_id"] == "professional_correspondence_studio"
    assert bindings["finance_readiness"]["unit_id"] == "finance_readiness_studio"
    assert bindings["article_publication"]["unit_id"] == "article_publication_studio"
    assert bindings["funding_proposal_pack"]["unit_id"] == "funding_proposal_studio"
    assert all(row["unit_digest"].startswith("sha256:") for row in bindings.values())
    assert all(row["authority_ceiling"] == "controlled_artifact_only" for row in bindings.values())
    assert all(row["authority_created"] is False for row in bindings.values())


def test_pivot_gauntlet_all_33_cross_domain_and_false_analogy_cases_match(registry):
    gauntlet = evaluate_pivot_gauntlet(registry)
    assert gauntlet["case_count"] == 33
    assert gauntlet["passed_case_count"] == 33
    assert gauntlet["all_cases_passed"] is True


def test_reference_funding_morphology_is_composable_from_verified_capabilities(registry):
    resolution = resolve_task(registry, "T000")
    assert resolution.verdict == "COMPOSABLE"
    assert resolution.missing_primitive_ids == ()
    assert resolution.missing_specialized_capabilities == ()
    assert resolution.capability_created is False
    assert resolution.execution_performed is False


def test_remote_procurement_tender_can_be_mechanically_composable_without_becoming_submission_authority(registry):
    resolution = resolve_task(registry, "T001")
    assert resolution.domain_id == "D1702"
    assert resolution.verdict == "COMPOSABLE"
    assert resolution.external_effect_intent == "NONE"
    assert resolution.authority_created is False
    assert resolution.external_effects is False


def test_unknown_domain_name_does_not_block_work_morphology_resolution(registry, pivot_receipt):
    resolution = resolve_task(registry, "T014")
    assert resolution.domain_id == "D1800"
    assert resolution.verdict == "COMPOSABLE"
    assert resolution.missing_primitive_ids == ()
    assert pivot_receipt["unknown_domain_morphology_resolved"] is True


def test_medical_false_analogy_is_not_laundered_into_clinical_capability(registry, pivot_receipt):
    resolution = resolve_task(registry, "T016")
    assert resolution.verdict == "PARTIALLY_COMPOSABLE"
    assert "clinical_diagnosis" in resolution.missing_specialized_capabilities
    assert "medical_professional_authority" in resolution.missing_specialized_capabilities
    assert pivot_receipt["medical_specialized_capability_missing"] is True


def test_aircraft_release_false_analogy_is_refused(registry, pivot_receipt):
    resolution = resolve_task(registry, "T018")
    assert resolution.verdict == "UNSUPPORTED"
    assert "airworthiness_release" in resolution.missing_specialized_capabilities
    assert "licensed_aircraft_engineer_authority" in resolution.missing_specialized_capabilities
    assert pivot_receipt["aircraft_false_analogy_verdict"] == "UNSUPPORTED"


def test_external_effect_tasks_cannot_become_composable_from_similarity(registry):
    for task_id in ("T020", "T021", "T022", "T027"):
        resolution = resolve_task(registry, task_id)
        assert resolution.external_effect_intent != "NONE"
        assert resolution.verdict == "UNSUPPORTED"
        assert resolution.authority_created is False
        assert resolution.execution_performed is False


def test_pivot_ranking_uses_work_morphology_not_same_domain_bonus(registry):
    first = pivot_candidates(registry, source_task_id="T000", excluded_domain_ids=("D1701",), top_k=10)
    second = pivot_candidates(registry, source_task_id="T000", excluded_domain_ids=("D1701",), top_k=10)
    assert first == second
    assert len(first) == 10
    assert all(row.target_domain_id != "D1701" for row in first)
    assert all(row.relation_state == "ANALOGICAL_CANDIDATE" for row in first)
    assert len({row.target_domain_id for row in first}) >= 5


def test_negative_market_learning_can_compile_cross_domain_pivot_hypothesis_without_execution():
    parent = phase8_projection_adaptation_receipt(REPO_ROOT)
    hypothesis = compile_negative_learning_pivot(
        REPO_ROOT,
        m2_learning_receipt=parent,
        source_task_id="T000",
        top_k=10,
    )
    assert hypothesis["source_domain_excluded_from_targets"] is True
    assert hypothesis["candidate_count"] == 10
    assert len(hypothesis["negative_learning_record_ids"]) == 2
    assert all(row["target_domain_id"] != hypothesis["source_domain_id"] for row in hypothesis["candidates"])
    assert all(row["relation_state"] == "ANALOGICAL_CANDIDATE" for row in hypothesis["candidates"])
    assert hypothesis["market_demand_claimed"] is False
    assert hypothesis["capability_created"] is False
    assert hypothesis["authority_created"] is False
    assert hypothesis["external_effects"] is False
    assert hypothesis["execution_performed"] is False
    assert hypothesis["direct_learning_to_execution"] is False
    assert hypothesis["pivot_hypothesis_digest"].startswith("sha256:")


def test_atlas_pivot_foundation_gate_passes(pivot_receipt):
    assert pivot_receipt["passed"] is True, pivot_receipt
    assert pivot_receipt["acceptance"] == ATLAS_PIVOT_TOKEN
    assert pivot_receipt["parent_acceptance"] == "DIO_M2_PROJECTION_ADAPTATION_READY"
    assert pivot_receipt["parent_verified"] is True
    assert pivot_receipt["negative_learning_context_bound"] is True
    assert pivot_receipt["pivot_gauntlet_case_count"] == 33
    assert pivot_receipt["pivot_gauntlet_passed_case_count"] == 33
    assert pivot_receipt["pivot_gauntlet_all_cases_passed"] is True


def test_atlas_foundation_does_not_claim_universal_expertise_market_truth_or_authority(foundation, pivot_receipt):
    assert foundation["knowledge_is_capability"] is False
    assert foundation["similarity_is_equivalence"] is False
    assert foundation["analogy_is_evidence"] is False
    assert foundation["domain_adjacency_is_market_demand"] is False
    assert foundation["task_match_is_execution_proof"] is False
    assert foundation["taxonomy_membership_mints_authority"] is False
    assert pivot_receipt["similarity_is_capability"] is False
    assert pivot_receipt["analogy_is_evidence"] is False
    assert pivot_receipt["market_demand_claimed"] is False
    assert pivot_receipt["authority_created"] is False
    assert pivot_receipt["authority_widened"] is False
    assert pivot_receipt["external_effects"] is False
    assert pivot_receipt["direct_learning_to_execution"] is False
    assert pivot_receipt["execution_performed"] is False
    assert foundation["m4_final_verified"] is False
    assert pivot_receipt["m4_final_verified"] is False
