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
