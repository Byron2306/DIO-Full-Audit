from __future__ import annotations

import importlib.util
import os
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import quote


LEGACY_HOST_AUDIT_PENDING = "LEGACY_HOST_AUDIT_PENDING"


def artifact_url(raw: str) -> str:
    """Route local DIO artifacts through the governed localhost gateway."""
    value = str(raw or "").strip()
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return "/api/business/artifact?path=" + quote(value, safe="")


def runtime_readiness(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    edge_package = importlib.util.find_spec("edge_tts") is not None
    gamma_enabled = str(os.environ.get("DIO_GAMMA_VISUAL_CANDIDATE") or "0").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }
    nichefoundry_root = root / "cross_folder_variants" / "NicheFoundry_Phase11"
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    node = shutil.which("node")
    npm = shutil.which("npm")
    edge_cli = shutil.which("edge-tts")
    static_media_ready = bool(ffmpeg and ffprobe and nichefoundry_root.is_dir())
    reel_voice_ready = bool(static_media_ready and edge_package and edge_cli)
    return {
        "schema": "dio.business.runtime_readiness.v1",
        "static_media": "READY" if static_media_ready else "NEEDS_RUNTIME",
        "rendered_reel": "READY" if reel_voice_ready else "NEEDS_RUNTIME",
        "ffmpeg": "READY" if ffmpeg else "MISSING",
        "ffprobe": "READY" if ffprobe else "MISSING",
        "node": "READY" if node else "MISSING",
        "npm": "READY" if npm else "MISSING",
        "edge_tts_package": "READY" if edge_package else "MISSING",
        "edge_tts_cli": "READY" if edge_cli else "MISSING",
        "nichefoundry_phase11": "PRESENT" if nichefoundry_root.is_dir() else "MISSING",
        "gamma_visual_candidate": "ENABLED" if gamma_enabled else "OPTIONAL_DISABLED",
        "gamma_required_for_media": False,
        "local_compositor_fallback": True,
        "legacy_host_audit": LEGACY_HOST_AUDIT_PENDING,
        "authority_created": False,
    }


def atlas_projection(root: Path, dashboard_state: dict[str, Any]) -> dict[str, Any]:
    root = Path(root).resolve()
    atlas_root = root / "config" / "atlas"
    expected = {
        "constitution": atlas_root / "dio_atlas_constitution.json",
        "universal_domain_registry": atlas_root / "dio_atlas_universal_domain_registry.csv",
        "work_pattern_crosswalk": atlas_root / "dio_atlas_work_pattern_crosswalk.csv",
        "capability_signatures": atlas_root / "dio_atlas_capability_signatures.csv",
        "pivot_gauntlet": atlas_root / "dio_atlas_pivot_gauntlet.csv",
        "job_morphologies": atlas_root / "dio_atlas_job_morphologies.csv",
        "source_federation": atlas_root / "dio_atlas_source_federation.csv",
        "work_primitives": atlas_root / "dio_atlas_work_primitives.csv",
    }
    prospect = dict(dashboard_state.get("prospect_registry") or {})
    counts = dict(prospect.get("counts") or {})
    top_targets = []
    for row in list(prospect.get("top_targets") or [])[:20]:
        top_targets.append(
            {
                "rank": row.get("rank"),
                "target_id": row.get("target_id"),
                "organisation": row.get("organisation"),
                "product_line_id": row.get("product_line_id"),
                "product_name": row.get("product_name"),
                "attack_score": row.get("attack_score"),
                "route_state": row.get("route_state"),
                "route_type": row.get("route_type"),
                "source_url": row.get("source_url"),
                "source_verified_date": row.get("source_verified_date"),
                "outreach_state": row.get("outreach_state"),
                "email_eligible": bool(row.get("email_eligible")),
                "creative_state": row.get("creative_state"),
            }
        )
    missing_assets = [name for name, path in expected.items() if not path.is_file()]
    return {
        "schema": "dio.business.atlas_projection.v1",
        "atlas": {
            "state": "READY" if not missing_assets else "PARTIAL",
            "asset_count": sum(path.is_file() for path in expected.values()),
            "expected_asset_count": len(expected),
            "missing_assets": missing_assets,
            "assets": {name: str(path.relative_to(root)) for name, path in expected.items() if path.is_file()},
        },
        "prospect_registry": {
            "state": "PRESENT" if counts or top_targets else "EMPTY",
            "counts": counts,
            "top_targets": top_targets,
            "electronic_sales_allowed": prospect.get("electronic_sales_allowed", 0),
            "source": prospect.get("source") or "",
            "read_only": True,
        },
        "legacy_host_audit": LEGACY_HOST_AUDIT_PENDING,
        "authority_created": False,
    }


def patch_advanced_dashboard(page: str) -> str:
    """Repair stale artifact links and make live-state hydration fail visibly."""
    stale_href = (
        'const href=(p)=>p?((p.startsWith("http://")||p.startsWith("https://"))?p:'
        '(p.startsWith("/")?`file://${p}`:`../${p}`)):"";'
    )
    safe_href = (
        'const href=(p)=>p?((p.startsWith("http://")||p.startsWith("https://"))?p:'
        '`/api/business/artifact?path=${encodeURIComponent(p)}`):"";'
    )
    page = page.replace(stale_href, safe_href, 1)

    banner = (
        '<div id="slice1LiveState" style="position:sticky;top:0;z-index:9999;padding:8px 12px;'
        'background:#2c210d;color:#f2cf79;border-bottom:1px solid #6e5925;font:12px system-ui">'
        'Checking live DIO state…</div>'
    )
    if 'id="slice1LiveState"' not in page:
        page = page.replace("<body>", "<body>" + banner, 1)

    old_refresh = (
        'async function refresh(){try{const r=await fetch("/api/control/state",{cache:"no-store"});'
        'if(r.ok)render(await r.json())}catch{}}'
    )
    new_refresh = (
        'async function refresh(){const b=document.querySelector("#slice1LiveState");try{'
        'const r=await fetch("/api/control/state",{cache:"no-store"});'
        'if(!r.ok)throw new Error(`HTTP ${r.status}`);render(await r.json());'
        'if(b){b.textContent="LIVE STATE · connected";b.style.background="#10261b";b.style.color="#8ee8b4";}}'
        'catch(e){if(b){b.textContent=`LIVE_STATE_UNAVAILABLE · ${e?.message||"state fetch failed"} · showing fallback snapshot`;'
        'b.style.background="#321816";b.style.color="#ff9a91";}}}'
    )
    page = page.replace(old_refresh, new_refresh, 1)
    return page
