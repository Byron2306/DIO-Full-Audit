import csv
from pathlib import Path

import pytest

from atlas import (
    ATLAS_SURFACE_PIVOT_TOKEN,
    ATLAS_SURFACE_TOKEN,
    AtlasRegistry,
    candidate_surface_receipt,
    compile_candidate_incarnations,
    materialize_candidate_registry_csv,
    negative_learning_surface_pivot_receipt,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def registry():
    return AtlasRegistry.load(REPO_ROOT)


@pytest.fixture(scope="module")
def candidates(registry):
    return compile_candidate_incarnations(REPO_ROOT, registry=registry)


@pytest.fixture(scope="module")
def surface():
    return candidate_surface_receipt(REPO_ROOT)


@pytest.fixture(scope="module")
def pivot_surface():
    return negative_learning_surface_pivot_receipt(REPO_ROOT)


def test_legacy_53_is_preserved_but_is_not_the_generated_candidate_universe(surface):
    assert surface["passed"] is True, surface
    assert surface["acceptance"] == ATLAS_SURFACE_TOKEN
    assert surface["legacy_portfolio_incarnation_count"] == 53
    assert surface["legacy_portfolio_preserved_exactly"] is True
    assert surface["legacy_portfolio_is_generated_candidate_universe"] is False
    assert surface["derived_candidate_incarnation_count"] >= 500
    assert surface["derived_candidate_incarnation_count"] > 53
    assert surface["derived_candidate_count_exceeds_legacy_portfolio"] is True
    assert surface["candidate_to_legacy_ratio"] > 9.0


def test_every_atlas_domain_node_has_at_least_one_derived_candidate(surface):
    assert surface["eligible_domain_node_count"] > 200
    assert surface["covered_domain_node_count"] == surface["eligible_domain_node_count"]
    assert surface["domain_coverage_ratio"] == 1.0


def test_candidate_registry_is_substantially_novel_relative_to_original_portfolio(surface):
    assert surface["novel_candidate_incarnation_count"] > 53
    assert surface["legacy_analogy_candidate_count"] >= 0
    assert surface["gap_bearing_candidate_count"] > 0
    assert surface["candidate_state_counts"]["COMPOSABLE_CANDIDATE"] > 0
    assert surface["candidate_state_counts"].get("PARTIALLY_COMPOSABLE_CANDIDATE", 0) > 0


def test_candidate_ids_and_digests_are_unique_and_deterministic(candidates, registry):
    second = compile_candidate_incarnations(REPO_ROOT, registry=registry)
    assert candidates == second
    ids = [row.candidate_id for row in candidates]
    digests = [row.candidate_digest for row in candidates]
    assert len(ids) == len(set(ids))
    assert len(digests) == len(set(digests))
    assert all(value.startswith("ACI-") for value in ids)
    assert all(value.startswith("sha256:") for value in digests)


def test_generated_candidates_are_held_hypotheses_not_products_or_market_claims(candidates, surface):
    assert surface["every_candidate_held_unproved"] is True
    assert all(row.execution_truth_state == "UNPROVED_CANDIDATE" for row in candidates)
    assert all(row.commercial_truth_state == "UNTESTED" for row in candidates)
    assert all(row.relation_state == "ANALOGICAL_CANDIDATE" for row in candidates)
    assert all(row.market_demand_claimed is False for row in candidates)
    assert all(row.capability_created is False for row in candidates)
    assert all(row.authority_created is False for row in candidates)
    assert all(row.authority_widened is False for row in candidates)
    assert all(row.external_effects is False for row in candidates)
    assert all(row.execution_performed is False for row in candidates)


def test_capability_cost_is_first_class_but_explicitly_not_observed_financial_cost(candidates, surface):
    assert surface["capability_cost_first_class"] is True
    assert surface["capability_cost_basis"] == "ATLAS_PLANNING_ESTIMATE_NOT_OBSERVED_COST"
    assert set(surface["capability_cost_counts"]) <= {"LOW", "LOW_MEDIUM", "MEDIUM", "HIGH", "VERY_HIGH"}
    assert all(row.capability_cost_basis == "ATLAS_PLANNING_ESTIMATE_NOT_OBSERVED_COST" for row in candidates)
    assert all(0.0 < row.capability_cost_score <= 5.0 for row in candidates)


def test_high_risk_domain_candidates_preserve_specialized_gaps_and_authority_ceiling(candidates):
    clinical_regulatory = next(
        row for row in candidates
        if row.domain_id == "D1002" and row.template_id == "MORPH-007"
    )
    assert clinical_regulatory.mechanical_verdict != "COMPOSABLE"
    assert "regulated_domain_interpretation" in clinical_regulatory.missing_specialized_capabilities
    assert clinical_regulatory.professional_authority_required is True
    assert clinical_regulatory.safety_criticality == "VERY_HIGH"
    assert clinical_regulatory.authority_ceiling == "controlled_artifact_only"
    assert clinical_regulatory.authority_created is False


def test_universal_controlled_artifact_morphology_can_cross_unknown_domain_without_claiming_domain_expertise(candidates):
    unknown = next(
        row for row in candidates
        if row.domain_id == "D1800" and row.template_id == "MORPH-001"
    )
    assert unknown.mechanical_verdict == "COMPOSABLE"
    assert unknown.missing_primitive_ids == ()
    assert unknown.domain_profile_state == "SOURCE_REFERENCED_NOT_EXECUTION_CORROBORATED"
    assert unknown.execution_truth_state == "UNPROVED_CANDIDATE"
    assert unknown.market_demand_claimed is False


def test_candidate_registry_can_be_materialized_as_the_requested_csv(tmp_path, candidates):
    target = tmp_path / "dio_atlas_candidate_incarnations.csv"
    receipt = materialize_candidate_registry_csv(REPO_ROOT, target)
    assert receipt["output_exists"] is True
    assert receipt["candidate_count"] == len(candidates)
    assert receipt["capability_created"] is False
    with target.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == len(candidates)
    assert "capability_cost" in rows[0]
    assert "legacy_analogy_names" in rows[0]
    assert "missing_specialized_capabilities" in rows[0]
    assert "candidate_state" in rows[0]


def test_negative_learning_can_search_the_vast_generated_candidate_universe(pivot_surface):
    assert pivot_surface["passed"] is True, pivot_surface
    assert pivot_surface["acceptance"] == ATLAS_SURFACE_PIVOT_TOKEN
    assert pivot_surface["parent_acceptance"] == "DIO_M2_PROJECTION_ADAPTATION_READY"
    assert pivot_surface["parent_verified"] is True
    assert pivot_surface["negative_learning_context_bound"] is True
    assert pivot_surface["derived_candidate_incarnation_count"] >= 500
    assert pivot_surface["selected_candidate_count"] == 25
    assert pivot_surface["selected_domain_family_count"] >= 8
    assert pivot_surface["selected_domain_count"] >= 8
    assert pivot_surface["selected_template_count"] >= 4


def test_negative_learning_pivot_is_diverse_and_source_domain_is_not_the_answer_loop(pivot_surface):
    rows = pivot_surface["top_pivot_candidates"]
    assert len(rows) == 25
    assert len({row["domain_family"] for row in rows}) >= 8
    assert len({row["domain_id"] for row in rows}) >= 8
    assert len({row["template_id"] for row in rows}) >= 4
    assert all(row["domain_id"] != "D1701" for row in rows)
    assert all(row["relation_state"] == "ANALOGICAL_CANDIDATE" for row in rows)
    assert all(row["candidate_digest"].startswith("sha256:") for row in rows)


def test_vast_pivot_does_not_turn_negative_learning_into_execution_authority_or_demand(pivot_surface):
    assert pivot_surface["all_selected_candidates_held_analogical"] is True
    assert pivot_surface["market_demand_claimed"] is False
    assert pivot_surface["capability_created"] is False
    assert pivot_surface["authority_created"] is False
    assert pivot_surface["authority_widened"] is False
    assert pivot_surface["external_effects"] is False
    assert pivot_surface["execution_performed"] is False
    assert pivot_surface["direct_learning_to_execution"] is False
    assert pivot_surface["m4_final_verified"] is False
