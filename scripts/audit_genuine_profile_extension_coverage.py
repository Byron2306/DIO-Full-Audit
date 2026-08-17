#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RECONCILIATION = ROOT / "config" / "product_class_reconciliation.json"
ROUTES = ROOT / "config" / "product_class_routes.json"
PORTFOLIO = ROOT / "config" / "dio_product_portfolio.json"
META_REGISTRY = ROOT / "config" / "dio_meta_products.json"
PROFILE_ROOT = ROOT / "config" / "products" / "profiles"

EXPECTED_IDENTITY_STATE = "genuine_profile_extension_unpromoted"
EVIDENCE_REVIEW_SCHEMA = "dio.evidence_review.profile.v1"
EXPECTED_META_PRODUCTS = ["meta_evidence", "meta_assurance", "meta_room"]
EXPECTED_RELEASE_GUARD = "meta_authority"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def audit(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    reconciliation = _read(root / "config" / "product_class_reconciliation.json")
    routes = _read(root / "config" / "product_class_routes.json")
    portfolio = _read(root / "config" / "dio_product_portfolio.json")
    meta_registry = _read(root / "config" / "dio_meta_products.json")
    profile_root = root / "config" / "products" / "profiles"

    errors: list[str] = []
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []

    if reconciliation.get("schema") != "dio.product_class_reconciliation.v2":
        errors.append("reconciliation must use dio.product_class_reconciliation.v2")
    if routes.get("schema") != "dio.product_class_routes.v1":
        errors.append("routes must use dio.product_class_routes.v1")

    canonical_ids = {str(row.get("id") or "") for row in portfolio.get("products") or []}
    composition_ids = {
        str(row.get("product_id") or "")
        for row in meta_registry.get("vertical_compositions") or []
    }
    extensions = reconciliation.get("genuine_profile_extensions") or {}
    route_rows = routes.get("product_classes") or {}

    expected_count = int((reconciliation.get("summary") or {}).get("genuine_profile_extensions") or 0)
    if len(extensions) != expected_count:
        errors.append(
            f"genuine profile extension count drifted: configured={len(extensions)} summary={expected_count}"
        )

    for profile_id in sorted(extensions):
        extension = extensions[profile_id] or {}
        route = route_rows.get(profile_id)
        profile_path = profile_root / f"{profile_id}.json"
        row: dict[str, Any] = {
            "profile_id": profile_id,
            "path": str(profile_path.relative_to(root)),
            "suggested_engine": extension.get("suggested_engine"),
            "exists": profile_path.is_file(),
            "state": "missing",
        }

        if route is None:
            errors.append(f"{profile_id}: missing product-class route")
        else:
            if route.get("route_kind") != "profile_extension":
                errors.append(f"{profile_id}: route_kind must remain profile_extension")
            if route.get("auto_promotable") is not False:
                errors.append(f"{profile_id}: route must remain auto_promotable=false")
            if route.get("suggested_engine") != extension.get("suggested_engine"):
                errors.append(f"{profile_id}: suggested_engine drifted between route and reconciliation")

        if not profile_path.is_file():
            errors.append(f"{profile_id}: missing typed profile {profile_path.relative_to(root)}")
            rows.append(row)
            continue

        try:
            profile = _read(profile_path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{profile_id}: invalid typed profile JSON: {exc}")
            rows.append(row)
            continue

        product_id = str(profile.get("product_id") or "")
        row.update(
            {
                "schema": profile.get("schema"),
                "product_id": product_id,
                "identity_state": profile.get("identity_state"),
                "canonical_portfolio_registration": profile.get("canonical_portfolio_registration"),
                "state": "typed_unpromoted_profile",
            }
        )

        if profile.get("profile_id") != profile_id:
            errors.append(f"{profile_id}: profile_id does not match filename/reconciliation key")
        if not product_id:
            errors.append(f"{profile_id}: product_id is required")
        if profile.get("identity_state") != EXPECTED_IDENTITY_STATE:
            errors.append(f"{profile_id}: identity_state must remain {EXPECTED_IDENTITY_STATE}")
        if profile.get("canonical_portfolio_registration") is not False:
            errors.append(f"{profile_id}: cannot claim canonical portfolio registration")
        if product_id in canonical_ids:
            errors.append(f"{profile_id}: unpromoted profile product_id collides with canonical portfolio {product_id}")
        if product_id in composition_ids:
            errors.append(f"{profile_id}: unpromoted profile product_id collides with canonical META composition {product_id}")
        if not profile.get("scope_limit"):
            errors.append(f"{profile_id}: scope_limit is required")
        if not profile.get("human_gate_reason"):
            errors.append(f"{profile_id}: human_gate_reason is required")
        forbidden = profile.get("forbidden_outcomes") or []
        if not isinstance(forbidden, list) or not forbidden or len(forbidden) != len(set(forbidden)):
            errors.append(f"{profile_id}: forbidden_outcomes must be a non-empty unique list")
        for field in ("authority_created", "external_effects", "external_release"):
            if profile.get(field) is not False:
                errors.append(f"{profile_id}: {field} must remain false")

        if profile.get("schema") == EVIDENCE_REVIEW_SCHEMA:
            if profile.get("required_meta_products") != EXPECTED_META_PRODUCTS:
                errors.append(
                    f"{profile_id}: evidence-review META composition must be {EXPECTED_META_PRODUCTS}"
                )
            if profile.get("release_guard_meta_product") != EXPECTED_RELEASE_GUARD:
                errors.append(f"{profile_id}: evidence-review release guard must remain meta_authority")
        elif profile.get("schema") != "dio.dossier_assembly.profile.v1":
            warnings.append(
                f"{profile_id}: profile schema {profile.get('schema')} is outside the currently audited evidence/dossier schemas"
            )

        rows.append(row)

    orphan_profiles: list[str] = []
    for path in sorted(profile_root.glob("*.json")):
        payload = _read(path)
        if payload.get("identity_state") == EXPECTED_IDENTITY_STATE and path.stem not in extensions:
            orphan_profiles.append(path.stem)
            errors.append(
                f"{path.stem}: unpromoted genuine-extension profile exists outside reconciliation"
            )

    typed_count = sum(1 for row in rows if row["state"] == "typed_unpromoted_profile")
    result = {
        "schema": "dio.genuine_profile_extension_coverage_audit.v1",
        "state": "reconciled" if not errors else "failed",
        "genuine_profile_extensions": len(extensions),
        "typed_profiles": typed_count,
        "missing_profiles": len(extensions) - typed_count,
        "auto_promotable_profiles": sum(
            1
            for profile_id in extensions
            if (route_rows.get(profile_id) or {}).get("auto_promotable") is True
        ),
        "canonical_collisions": sum(
            1
            for row in rows
            if row.get("product_id") in canonical_ids or row.get("product_id") in composition_ids
        ),
        "orphan_unpromoted_profiles": orphan_profiles,
        "errors": errors,
        "warnings": warnings,
        "profiles": rows,
        "truth_boundary": (
            "Typed unpromoted profile coverage proves only that each genuine extension has an explicit "
            "scope and authority boundary over shared DIO organs. It is not product execution proof, "
            "customer validation, public launch authority or external release authority."
        ),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit typed profile coverage for all reconciled genuine DIO profile extensions."
    )
    parser.add_argument("--root", default=str(ROOT), help="DIO repository root")
    args = parser.parse_args()
    result = audit(Path(args.root))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["state"] == "reconciled" else 1


if __name__ == "__main__":
    raise SystemExit(main())
