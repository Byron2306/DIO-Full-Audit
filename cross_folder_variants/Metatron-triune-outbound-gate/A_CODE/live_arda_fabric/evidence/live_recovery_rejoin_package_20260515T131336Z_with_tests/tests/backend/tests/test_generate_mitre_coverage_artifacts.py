from backend.scripts.generate_mitre_coverage_artifacts import (
    build_osquery_catalog,
    build_soar_execution_seed,
    discover_techniques,
    validate_generated_artifacts,
)


def test_discover_techniques_matches_active_enterprise_catalog() -> None:
    techniques, referenced_techniques, metadata = discover_techniques()

    assert metadata["enterprise_attack_techniques"] == 691
    assert metadata["enterprise_attack_parents"] == 216
    assert metadata["enterprise_attack_subtechniques"] == 475
    assert len(techniques) == metadata["enterprise_attack_techniques"]
    assert len(referenced_techniques) == metadata["enterprise_attack_techniques"]


def test_validate_generated_artifacts_accepts_full_catalog_generation() -> None:
    techniques, _, metadata = discover_techniques()
    osquery_catalog = build_osquery_catalog(techniques)
    soar_seed = build_soar_execution_seed(techniques)

    validation = validate_generated_artifacts(techniques, osquery_catalog, soar_seed, metadata)

    assert validation["full_catalog_generated"] is True
    assert validation["expected_technique_count"] == 691
    assert validation["generated_technique_count"] == 691
    assert validation["osquery_queries_expected"] == 2073
    assert validation["soar_rows_expected"] == len(soar_seed)
    assert validation["soar_rows_generated"] == len(soar_seed)
    assert validation["soar_rows_unique"] == len({str(row.get("id") or "") for row in soar_seed})