#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
UNPROMOTED_IDENTITY = "genuine_profile_extension_unpromoted"
CANONICAL_REGISTERED_IDENTITY = "canonical_portfolio_registered_profile_extension"
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
        canonical_registration = product_id in canonical_ids
        composition_registration = product_id in composition_ids
        identity_state = profile.get("identity_state")
        declared_canonical = profile.get("canonical_portfolio_registration")
        reconciled_canonical = str(extension.get("canonical_product_id") or "")

        row.update(
            {
                "schema": profile.get("schema"),
                "product_id": product_id,
                "identity_state": identity_state,
                "canonical_portfolio_registration": declared_canonical,
                "canonical_identity_present": canonical_registration,
                "meta_composition_present": composition_registration,
            }
        )

        if profile.get("profile_id") != profile_id:
            errors.append(f"{profile_id}: profile_id does not match filename/reconciliation key")
        if not product_id:
            errors.append(f"{profile_id}: product_id is required")

        if canonical_registration:
            row["state"] = "typed_canonical_registered_profile_extension"
            if identity_state != CANONICAL_REGISTERED_IDENTITY:
                errors.append(
                    f"{profile_id}: canonical portfolio profile must use identity_state={CANONICAL_REGISTERED_IDENTITY}"
                )
            if declared_canonical is not True:
                errors.append(f"{profile_id}: canonical portfolio registration must be declared true")
            if reconciled_canonical != product_id:
                errors.append(
                    f"{profile_id}: reconciliation must explicitly bind canonical_product_id={product_id}"
                )
            if not composition_registration:
                errors.append(
                    f"{profile_id}: canonical portfolio profile is missing its canonical META composition"
                )
        else:
            row["state"] = "typed_unpromoted_profile"
            if identity_state != UNPROMOTED_IDENTITY:
                errors.append(f"{profile_id}: identity_state must remain {UNPROMOTED_IDENTITY}")
            if declared_canonical is not False:
                errors.append(f"{profile_id}: noncanonical profile must declare canonical registration false")
            if composition_registration:
                errors.append(
                    f"{profile_id}: noncanonical product_id unexpectedly collides with META composition {product_id}"
                )
            if reconciled_canonical:
                errors.append(
                    f"{profile_id}: noncanonical profile cannot claim reconciliation canonical_product_id={reconciled_canonical}"
                )

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
    audited_identity_states = {UNPROMOTED_IDENTITY, CANONICAL_REGISTERED_IDENTITY}
    for path in sorted(profile_root.glob("*.json")):
        payload = _read(path)
        if payload.get("identity_state") in audited_identity_states and path.stem not in extensions:
            orphan_profiles.append(path.stem)
            errors.append(
                f"{path.stem}: genuine-extension typed profile exists outside reconciliation"
            )

    typed_states = {
        "typed_unpromoted_profile",
        "typed_canonical_registered_profile_extension",
    }
    typed_count = sum(1 for row in rows if row["state"] in typed_states)
    canonical_registered = sum(
        1 for row in rows if row["state"] == "typed_canonical_registered_profile_extension"
    )
    unpromoted = sum(1 for row in rows if row["state"] == "typed_unpromoted_profile")

    result = {
        "schema": "dio.genuine_profile_extension_coverage_audit.v1",
        "state": "reconciled" if not errors else "failed",
        "genuine_profile_extensions": len(extensions),
        "typed_profiles": typed_count,
        "typed_unpromoted_profiles": unpromoted,
        "typed_canonical_registered_profiles": canonical_registered,
        "missing_profiles": len(extensions) - typed_count,
        "auto_promotable_profiles": sum(
            1
            for profile_id in extensions
            if (route_rows.get(profile_id) or {}).get("auto_promotable") is True
        ),
        "orphan_typed_profiles": orphan_profiles,
        "errors": errors,
        "warnings": warnings,
        "profiles": rows,
        "truth_boundary": (
            "Typed profile coverage proves only explicit scope and authority boundaries over shared DIO organs. "
            "A canonical portfolio registration remains distinct from an exact executable incarnation. "
            "Typed coverage and portfolio registration are not product execution proof, customer validation, "
            "public launch authority or external release authority."
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
