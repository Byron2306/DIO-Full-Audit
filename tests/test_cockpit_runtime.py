from __future__ import annotations

from pathlib import Path

import cockpit_runtime


def test_artifact_url_routes_local_paths_through_governed_gateway() -> None:
    url = cockpit_runtime.artifact_url("deliverables/evidex/example pack")
    assert url.startswith("/api/business/artifact?path=")
    assert "file://" not in url
    assert ".." not in url
    assert cockpit_runtime.artifact_url("https://example.com/proof") == "https://example.com/proof"


def test_runtime_readiness_never_exposes_secret_values(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "cross_folder_variants" / "NicheFoundry_Phase11").mkdir(parents=True)
    monkeypatch.setenv("HF_TOKEN", "SECRET-MUST-NOT-LEAK")
    result = cockpit_runtime.runtime_readiness(tmp_path)
    rendered = repr(result)
    assert "SECRET-MUST-NOT-LEAK" not in rendered
    assert result["legacy_host_audit"] == "LEGACY_HOST_AUDIT_PENDING"
    assert result["authority_created"] is False
    assert result["gamma_required_for_media"] is False
    assert result["local_compositor_fallback"] is True


def test_atlas_projection_preserves_registry_truth_read_only(tmp_path: Path) -> None:
    atlas = tmp_path / "config" / "atlas"
    atlas.mkdir(parents=True)
    (atlas / "dio_atlas_constitution.json").write_text("{}", encoding="utf-8")
    state = {
        "prospect_registry": {
            "counts": {"buyer_unit_targets": 426, "product_opportunities": 4834},
            "top_targets": [
                {
                    "rank": "1",
                    "target_id": "W4-TGT-0018",
                    "organisation": "FEDSAS",
                    "product_line_id": "HOMS_ASSESS",
                    "product_name": "HOMS Assessment Desk",
                    "attack_score": "97.6",
                    "route_state": "PARTNERSHIP_ROUTE_AVAILABLE",
                    "route_type": "association_business_development",
                    "source_url": "https://example.invalid",
                    "source_verified_date": "2026-08-08",
                    "email_eligible": True,
                    "outreach_state": "sent",
                }
            ],
            "electronic_sales_allowed": 0,
            "source": "campaigns/dio_market_loop/wave4/REGISTRY_IMPORT_RECEIPT.json",
        }
    }
    result = cockpit_runtime.atlas_projection(tmp_path, state)
    assert result["prospect_registry"]["counts"]["buyer_unit_targets"] == 426
    assert result["prospect_registry"]["electronic_sales_allowed"] == 0
    assert result["prospect_registry"]["read_only"] is True
    assert result["prospect_registry"]["top_targets"][0]["organisation"] == "FEDSAS"
    assert "public_contact_route" not in result["prospect_registry"]["top_targets"][0]
    assert result["legacy_host_audit"] == "LEGACY_HOST_AUDIT_PENDING"


def test_advanced_dashboard_patch_repairs_links_and_exposes_hydration_failure() -> None:
    page = '''<html><body><script>
const href=(p)=>p?((p.startsWith("http://")||p.startsWith("https://"))?p:(p.startsWith("/")?`file://${p}`:`../${p}`)):"";
async function refresh(){try{const r=await fetch("/api/control/state",{cache:"no-store"});if(r.ok)render(await r.json())}catch{}}
</script></body></html>'''
    result = cockpit_runtime.patch_advanced_dashboard(page)
    assert "file://" not in result
    assert "../${p}" not in result
    assert "/api/business/artifact?path=" in result
    assert "LIVE_STATE_UNAVAILABLE" in result
    assert 'id="slice1LiveState"' in result
