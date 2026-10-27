from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_presence_bridge_exposes_operator_case_read_apis_without_public_access():
    source = read("scripts/serve_presence_bridge.py")
    assert "case_list_view" in source
    assert "case_detail_view" in source
    assert "commercial_pipeline_view" in source
    assert "@app.get('/api/presence/cases')" in source
    assert "@app.get('/api/presence/cases/{case_id}')" in source
    assert "@app.get('/api/presence/commercial-pipeline')" in source
    assert "Operator token required." in source
    assert "customer_cases" in source


def test_control_deck_projects_same_canonical_commercial_state_not_a_second_crm():
    source = read("scripts/serve_business_workbench.py")
    assert '"/api/business/commercial/state"' in source
    assert '"/api/business/commercial/case"' in source
    assert "case_list_view" in source
    assert "case_detail_view" in source
    assert "commercial_pipeline_view" in source
    assert "build_commercial_pricing_registry" in source
    assert "list_needs_you" in source
    assert "DIO_PRESENCE_STATE_ROOT" in source
    assert "/dashboard/commercial_slice2.js" in source


def test_mobile_commercial_projection_has_required_operator_columns_and_empty_state():
    source = read("dashboard/commercial_slice2.js")
    for label in ("Customer", "Product", "Value", "Stage", "Needs You"):
        assert label in source
    assert "No customer cases yet" in source
    assert "/api/business/commercial/state" in source
    assert "/api/business/commercial/case?case_id=" in source
    assert "Recommended and invoiced values are not revenue" in source
    assert "authority_created" in source


def test_commercial_browser_surface_contains_no_long_lived_authority_secret():
    source = read("dashboard/commercial_slice2.js")
    forbidden = (
        "DIO_PRESENCE_OPERATOR_TOKEN",
        "DIO_PRESENCE_PUBLIC_SHARED_SECRET",
        "DIO_PRESENCE_OPERATOR_SHARED_SECRET",
        "X-DIO-Control-Token",
        "Bearer ",
    )
    assert all(value not in source for value in forbidden)
    assert "fetch('/api/business/commercial/state'" in source or 'fetch("/api/business/commercial/state"' in source


def test_slice2_keeps_slice1_cockpit_regression_in_final_ci():
    workflow = read(".github/workflows/dio-slice2-commercial-spine.yml")
    assert "tests/test_slice1_cockpit_contracts.py" in workflow
    assert "tests/test_slice2_commercial_spine_contracts.py" in workflow
    assert "DIO_SLICE_2_COMMERCIAL_SPINE" in workflow
