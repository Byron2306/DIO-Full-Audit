from pathlib import Path

from atlas import ATLAS_CONSTITUTION_TOKEN, validate_atlas_constitution


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_atlas_constitution_freezes_exact_laws_relations_and_verdicts():
    receipt = validate_atlas_constitution(REPO_ROOT)
    assert receipt["passed"] is True, receipt
    assert receipt["acceptance"] == ATLAS_CONSTITUTION_TOKEN
    assert receipt["law_count"] == 16
    assert receipt["laws_exact"] is True
    assert receipt["relation_state_count"] == 7
    assert receipt["relation_states_exact"] is True
    assert receipt["mechanical_verdict_count"] == 3
    assert receipt["mechanical_verdicts_exact"] is True


def test_atlas_constitution_binds_all_foundation_sources_and_expected_scale():
    receipt = validate_atlas_constitution(REPO_ROOT)
    assert receipt["source_file_count"] == 8
    assert receipt["missing_source_files"] == []
    assert len(receipt["source_digests"]) == 8
    assert all(value.startswith("sha256:") for value in receipt["source_digests"].values())
    assert receipt["minimums"] == {
        "source_federation": 12,
        "work_primitives": 50,
        "universal_domain_nodes": 200,
        "pivot_gauntlet_tasks": 30,
    }
    assert receipt["exact_portfolio_bindings"] == {
        "incarnations": 53,
        "profile_rows": 43,
        "canonical_work_patterns": 12,
        "candidate_work_patterns": 1,
        "execution_grade_m1_capability_signatures": 4,
    }


def test_atlas_constitution_preserves_truth_authority_and_foundation_boundary():
    receipt = validate_atlas_constitution(REPO_ROOT)
    assert all(receipt["truth_boundaries"].values())
    assert receipt["full_external_taxonomy_ingestion_required_for_m4_0"] is False
    assert receipt["federation_envelope_may_reference_not_yet_ingested_sources"] is True
    assert receipt["authority_created"] is False
    assert receipt["authority_widened"] is False
    assert receipt["external_effects"] is False
    assert receipt["new_runtime_engine_created"] is False
    assert receipt["m4_final_verified"] is False
