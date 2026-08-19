from __future__ import annotations

import json
from pathlib import Path

from portfolio_runtime import ROOT
from products.professional_evidence_executor import BLOCKED, FAIL, PASS


EXECUTOR = ROOT / "products" / "professional_evidence_executor.py"
ROUTES = ROOT / "config" / "professional_evidence_portfolio" / "v1" / "routes.json"
RUNNER = ROOT / "scripts" / "run_professional_evidence_portfolio.py"


def test_only_three_truthful_case_states_exist() -> None:
    assert {PASS, FAIL, BLOCKED} == {"PASS_FULL_PIPELINE", "FAIL_EXECUTION", "BLOCKED_FULL_PIPELINE_GAP"}


def test_all_53_routes_have_an_execution_branch() -> None:
    routes = json.loads(ROUTES.read_text(encoding="utf-8"))["routes"]
    source = EXECUTOR.read_text(encoding="utf-8")
    assert len(routes) == 53
    route_names = {str(row["route"]) for row in routes.values()}
    for route_name in route_names:
        assert route_name in source, f"route missing from professional executor: {route_name}"


def test_executor_does_not_import_golden_fixture_execution_helpers() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    forbidden = [
        "controlled_education_research_fixture",
        "controlled_evidence_profile_fixture",
        "controlled_high_risk_fixture",
        "run_phase11_1_gauntlet",
        "controlled_regops_fixture",
        "controlled_dossierops_fixture",
    ]
    for marker in forbidden:
        assert marker not in source
    assert '"golden_fixture_used": False' in source
    assert '"examiner_data_used_during_execution": False' in source


def test_examiner_is_loaded_only_inside_post_execution_blind_review() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    blind_position = source.index("def _blind_review")
    route_position = source.index("def _route_execute")
    assert 'case_root / "EXAMINER" / "EXPECTED_FACTS.json"' in source[blind_position:route_position]
    assert '"examiner_data_used_during_execution": False' in source


def test_outer_receipt_is_excluded_from_its_own_artifact_inventory() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    assert "path.name == OUTER_RECEIPT" in source
    assert source.count("write_json(case_root / OUTER_RECEIPT, receipt)") == 1


def test_portfolio_acceptance_requires_literal_53_of_53() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert 'ACCEPTANCE_TOKEN = "DIO_PROFESSIONAL_EVIDENCE_PORTFOLIO_53_VERIFIED"' in source
    assert "counts[PASS] == 53" in source
    assert "counts[FAIL] == 0" in source
    assert "counts[BLOCKED] == 0" in source
    assert '"market_validation_claimed": False' in source
    assert '"external_effects": False' in source
