from backend.mitre_catalog import load_mitre_catalog_totals
from backend.sigma_engine import sigma_engine


def test_load_mitre_catalog_totals_matches_generated_catalog() -> None:
    totals = load_mitre_catalog_totals()

    assert totals["enterprise_technique_total"] == 691
    assert totals["enterprise_parent_total"] == 216
    assert totals["roadmap_target_total"] == 691


def test_sigma_engine_uses_catalog_driven_totals() -> None:
    totals = load_mitre_catalog_totals()
    summary = sigma_engine.coverage_summary()
    unified = summary["unified_coverage"]

    assert summary["enterprise_technique_total"] == totals["enterprise_technique_total"]
    assert summary["enterprise_parent_total"] == totals["enterprise_parent_total"]
    assert summary["roadmap_target_techniques"] == totals["roadmap_target_total"]
    assert unified["enterprise_technique_total"] == totals["enterprise_technique_total"]
    assert unified["enterprise_parent_total"] == totals["enterprise_parent_total"]
    assert unified["gap_to_full_catalog_gte3"] == totals["enterprise_technique_total"] - unified["covered_score_gte3"]
    assert unified["gap_to_full_catalog_gte5"] == totals["enterprise_technique_total"] - unified["covered_score_gte5"]