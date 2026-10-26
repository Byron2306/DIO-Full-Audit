from pathlib import Path

from atlas import META_CROSSWALK_TOKEN, validate_meta_profile_crosswalk


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_full_dio_meta_portfolio_crosswalk_passes():
    receipt = validate_meta_profile_crosswalk(REPO_ROOT)
    assert receipt["passed"] is True, receipt
    assert receipt["acceptance"] == META_CROSSWALK_TOKEN
    assert receipt["portfolio_incarnation_count"] == 53
    assert receipt["profile_row_count"] == 43
    assert receipt["profile_class_counts"] == {
        "Domain": 15,
        "Framework": 15,
        "Authority": 3,
        "Connector": 4,
        "Output": 3,
        "Commercial": 3,
    }
    assert receipt["profile_class_counts_exact"] is True


def test_meta_profiles_map_to_atlas_without_creating_capability_or_authority():
    receipt = validate_meta_profile_crosswalk(REPO_ROOT)
    assert receipt["profile_domain_refs_valid"] is True
    assert receipt["profile_source_refs_valid"] is True
    assert receipt["profile_rows_non_authorizing"] is True
    assert receipt["authority_created"] is False
    assert receipt["authority_widened"] is False
    assert receipt["external_effects"] is False


def test_capability_cost_and_atlas_axes_are_first_class():
    receipt = validate_meta_profile_crosswalk(REPO_ROOT)
    assert receipt["capability_cost_first_class"] is True
    assert receipt["atlas_axes_present"] == ["ARTIFACT", "COMMERCIAL", "CONNECTOR", "CONSTRAINT", "DOMAIN"]
    assert receipt["canonical_work_pattern_count"] == 12
    assert receipt["candidate_work_pattern_count"] == 1
