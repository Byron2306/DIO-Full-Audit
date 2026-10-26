from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from products.unpromoted_evidence_profile import run_unpromoted_evidence_review


ROOT = Path(__file__).resolve().parents[1]
ROUTES_PATH = ROOT / "config" / "product_class_routes.json"
RECONCILIATION_PATH = ROOT / "config" / "product_class_reconciliation.json"

HIGH_RISK_PROFILE_IDS = {
    "controldrift",
    "ai_incidentroom",
    "criticalai_assurance",
    "cyberassurance",
    "dora_vendor_assurance",
    "incidentproof",
    "modelproof",
    "releaseproof",
    "suppliercyberproof",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_no_engine_boundary(profile_id: str) -> dict[str, Any]:
    if profile_id not in HIGH_RISK_PROFILE_IDS:
        raise ValueError(f"Profile is not in the bounded high-risk no-engine set: {profile_id}")

    routes = _load_json(ROUTES_PATH)
    reconciliation = _load_json(RECONCILIATION_PATH)
    route = (routes.get("product_classes") or {}).get(profile_id)
    extension = (reconciliation.get("genuine_profile_extensions") or {}).get(profile_id)
    if not isinstance(route, dict) or not isinstance(extension, dict):
        raise RuntimeError(f"High-risk profile is missing route/reconciliation truth: {profile_id}")
    if route.get("route_kind") != "profile_extension":
        raise RuntimeError(f"High-risk profile route_kind drifted: {profile_id}")
    if route.get("auto_promotable") is not False:
        raise RuntimeError(f"High-risk profile cannot become auto-promotable: {profile_id}")
    if route.get("suggested_engine") is not None:
        raise RuntimeError(f"High-risk profile route gained an engine without review: {profile_id}")
    if extension.get("suggested_engine") is not None:
        raise RuntimeError(f"High-risk reconciliation gained an engine without review: {profile_id}")

    return {
        "schema": "dio.high_risk_profile.route_boundary.v1",
        "profile_id": profile_id,
        "route_kind": "profile_extension",
        "suggested_engine": None,
        "engine_assigned": False,
        "engine_invoked": False,
        "auto_promotable": False,
        "execution_proof_created": False,
        "authority_created": False,
        "external_effects": False,
        "external_release": False,
    }


def run_high_risk_evidence_review(
    case: dict[str, Any],
    *,
    profile_id: str,
    requirements: list[dict[str, Any]],
    evidence_inputs: list[dict[str, Any]],
    issues: list[dict[str, Any]] | None,
    output_dir: Path,
    operator_id: str,
    now: str,
) -> dict[str, Any]:
    """Run shared evidence review while proving that no domain engine was assigned or invoked."""

    boundary = validate_no_engine_boundary(profile_id)
    result = run_unpromoted_evidence_review(
        case,
        profile_id=profile_id,
        requirements=requirements,
        evidence_inputs=evidence_inputs,
        issues=issues,
        output_dir=output_dir,
        operator_id=operator_id,
        now=now,
    )
    if result["receipt"].get("execution_performed") is not False:
        raise RuntimeError("High-risk evidence review cannot become product execution proof.")
    if result["receipt"].get("authority_created") is not False:
        raise RuntimeError("High-risk evidence review cannot create authority.")
    if result["receipt"].get("external_effects") is not False:
        raise RuntimeError("High-risk evidence review cannot create external effects.")
    if result["receipt"].get("external_release") is not False:
        raise RuntimeError("High-risk evidence review cannot grant external release.")
    result["route_boundary"] = boundary
    return result
