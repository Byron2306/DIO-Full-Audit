from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_business_workbench_exposes_atlas_readiness_and_advanced_patch() -> None:
    source = read("scripts/serve_business_workbench.py")
    assert 'route == "/api/business/atlas"' in source
    assert 'state["runtime_readiness"] = runtime_readiness(ROOT)' in source
    assert 'route == "/dashboard/index.html"' in source
    assert "patch_advanced_dashboard(page)" in source
    assert '"canonical_incarnations": portfolio.get("canonical_incarnation_count", 0)' in source


def test_business_workbench_injects_slice1_surfaces() -> None:
    source = read("scripts/serve_business_workbench.py")
    assert "/dashboard/atlas_slice1.js" in source
    assert "/dashboard/production_slice1.js" in source
    assert "/dashboard/production_semantic.js" in source


def test_production_slice_surfaces_readiness_and_persistent_marketing_failure() -> None:
    source = read("dashboard/production_slice1.js")
    assert "Cloud runtime readiness" in source
    assert "runtime_readiness" in source
    assert "MARKETING PRODUCTION BLOCKED" in source
    assert "No publication or spend occurred" in source
    assert "/api/business/production/marketing" in source


def test_atlas_slice_is_read_only_and_preserves_existing_registry() -> None:
    source = read("dashboard/atlas_slice1.js")
    assert "ATLAS + preserved prospect registry" in source
    assert "/api/business/atlas" in source
    assert "does not create a second CRM or authorize outreach" in source
    assert "electronic sales authority" in source


def test_market_command_does_not_let_missing_sensorium_kill_basic_hydration() -> None:
    source = read("scripts/serve_market_command_ms10.py")
    assert "SENSORIUM_UNAVAILABLE" in source
    assert "Promise.allSettled" in source
    assert "patch_market_dashboard" in source
    assert 'route == "/api/market/sensorium"' in source
    assert 'route == "/sensorium-evidence"' in source
    assert "authority_created" in source


def test_legacy_artifact_compatibility_is_narrow_existing_and_wired_to_live_gateway() -> None:
    source = read("cockpit_runtime.py")
    assert 'LEGACY_KNOWEDGE_ROOT = Path("/home/byron/Downloads/KnowEdge_AutoRelease_Suite")' in source
    assert "def resolve_legacy_artifact_path" in source
    assert "candidate.relative_to(LEGACY_KNOWEDGE_ROOT)" in source
    assert "if not target.exists():" in source
    assert "return None" in source
    live_gateway = read("scripts/serve_business_workbench.py")
    assert "resolve_legacy_artifact_path" in live_gateway
    assert "resolve_legacy_artifact_path(raw, ROOT)" in live_gateway
    assert "super()._serve_artifact()" in live_gateway
    base_gateway = read("scripts/serve_control_deck_ms10.py")
    assert "Artifact path is outside the approved DIO output roots" in base_gateway


def test_slice1_preserves_stronger_v2_68_product_receipt_contract() -> None:
    source = read("portfolio_runtime.py")
    assert 'EXTENSION_SCHEMA_V2 = "dio.product_grade.canon_extension_gauntlet_receipt.v2"' in source
    assert 'EXTENSION_PRODUCT_GRADE_TOKEN_V2 = "DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED"' in source
    assert 'value.get("controlled_journey_count") == 45' in source
    assert 'value.get("verified_journey_count") == 45' in source
    assert 'value.get("refused_journey_count") == 0' in source
    assert 'value.get("extension_count") == 15' in source
    assert 'value.get("product_grade_verified_count") == 15' in source
    assert 'value.get("commercial_validation") == "UNPROVED"' in source
    assert 'value.get("authority_created") is False' in source
    assert 'value.get("external_effects") is False' in source


def test_no_slice1_code_creates_public_listener_or_legacy_host_claim() -> None:
    combined = "\n".join(
        read(path)
        for path in (
            "cockpit_runtime.py",
            "scripts/serve_business_workbench.py",
            "dashboard/production_slice1.js",
            "dashboard/atlas_slice1.js",
        )
    )
    assert "LEGACY_HOST_AUDIT_PENDING" in combined
    assert "0.0.0.0" not in combined
    assert '`/api/business/artifact?path=${encodeURIComponent(p)}`' in read("cockpit_runtime.py")
