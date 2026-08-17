#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECONCILIATION = ROOT / "config" / "product_class_reconciliation.json"
DEFAULT_ROUTE_CONFIG = ROOT / "config" / "product_class_routes.json"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest_executor_ids(manifest: dict[str, Any]) -> set[str]:
    return {
        str(row.get("capability_id"))
        for row in manifest.get("capability_requirements", [])
        if isinstance(row, dict) and row.get("execution_required") is True
    }


def audit_reconciliation(
    reconciliation_path: Path = DEFAULT_RECONCILIATION,
    route_config_path: Path = DEFAULT_ROUTE_CONFIG,
    root: Path = ROOT,
) -> dict[str, Any]:
    reconciliation = read_json(reconciliation_path)
    routes = read_json(route_config_path)

    errors: list[str] = []
    warnings: list[str] = []

    if reconciliation.get("schema") != "dio.product_class_reconciliation.v2":
        errors.append("unsupported reconciliation schema")
    if routes.get("schema") != "dio.product_class_routes.v1":
        errors.append("unsupported route contract schema")

    exact = reconciliation.get("exact_canonical_incarnations") or {}
    candidates = reconciliation.get("equivalence_candidates") or {}
    resolved = reconciliation.get("resolved_composition_bindings") or {}
    extensions = reconciliation.get("genuine_profile_extensions") or {}
    route_classes = routes.get("product_classes") or {}

    partitions = [set(exact), set(candidates), set(resolved), set(extensions)]
    names = set().union(*partitions)
    for left_index, left in enumerate(partitions):
        for right in partitions[left_index + 1 :]:
            overlap = sorted(left & right)
            if overlap:
                errors.append(f"reconciliation partitions overlap: {', '.join(overlap)}")

    missing = sorted(set(route_classes) - names)
    extra = sorted(names - set(route_classes))
    if missing:
        errors.append(f"route product classes missing from reconciliation: {', '.join(missing)}")
    if extra:
        errors.append(f"reconciliation contains unknown product classes: {', '.join(extra)}")

    exact_results: dict[str, Any] = {}
    for product_class, binding in exact.items():
        route = route_classes.get(product_class) or {}
        manifest_rel = str(binding.get("canonical_manifest") or "")
        manifest_path = root / manifest_rel
        row: dict[str, Any] = {
            "manifest": manifest_rel,
            "manifest_exists": manifest_path.is_file(),
            "route_auto_promotable": route.get("auto_promotable"),
        }
        if route.get("auto_promotable") is not False:
            errors.append(f"{product_class}: reconciliation must not create auto-promotion authority")
        if not manifest_path.is_file():
            errors.append(f"{product_class}: canonical manifest missing: {manifest_rel}")
            exact_results[product_class] = row
            continue

        manifest = read_json(manifest_path)
        expected_product_id = str(binding.get("canonical_product_id") or "")
        expected_executor = str(binding.get("canonical_executor") or "")
        executor_ids = _manifest_executor_ids(manifest)
        maturity = manifest.get("maturity") or {}
        flags = maturity.get("operational_flags") or {}

        row.update(
            {
                "manifest_product_id": manifest.get("product_id"),
                "product_id_match": manifest.get("product_id") == expected_product_id,
                "required_executor": expected_executor,
                "executor_bound": expected_executor in executor_ids,
                "maturity": maturity.get("state"),
                "routable": flags.get("routable"),
                "governable": flags.get("governable"),
                "executable": flags.get("executable"),
                "externally_validated": flags.get("externally_validated"),
                "campaign_enabled": flags.get("campaign_enabled"),
            }
        )

        if manifest.get("product_id") != expected_product_id:
            errors.append(f"{product_class}: canonical product id mismatch")
        if expected_executor not in executor_ids:
            errors.append(f"{product_class}: canonical execution capability is not required by the manifest")
        if maturity.get("state") != "internal_proof":
            errors.append(f"{product_class}: canonical maturity must remain internal_proof")
        if flags.get("executable") is not True:
            errors.append(f"{product_class}: canonical manifest does not assert executable internal proof")
        if flags.get("externally_validated") is not False:
            errors.append(f"{product_class}: reconciliation must not inherit external validation")
        if flags.get("campaign_enabled") is not False:
            errors.append(f"{product_class}: reconciliation must not silently enable campaigns")

        exact_results[product_class] = row

    candidate_results: dict[str, Any] = {}
    for product_class, binding in candidates.items():
        route = route_classes.get(product_class) or {}
        manifest_rel = str(binding.get("candidate_manifest") or "")
        manifest_path = root / manifest_rel
        row: dict[str, Any] = {
            "manifest": manifest_rel,
            "manifest_exists": manifest_path.is_file(),
            "state": binding.get("state"),
            "route_auto_promotable": route.get("auto_promotable"),
        }
        if route.get("auto_promotable") is not False:
            errors.append(f"{product_class}: equivalence candidate must remain non-auto-promotable")
        if binding.get("state") != "equivalence_review_required":
            errors.append(f"{product_class}: equivalence candidate must require review")
        if not manifest_path.is_file():
            errors.append(f"{product_class}: candidate manifest missing: {manifest_rel}")
            candidate_results[product_class] = row
            continue
        manifest = read_json(manifest_path)
        expected_product_id = str(binding.get("candidate_product_id") or "")
        row.update(
            {
                "manifest_product_id": manifest.get("product_id"),
                "candidate_id_match": manifest.get("product_id") == expected_product_id,
                "candidate_maturity": (manifest.get("maturity") or {}).get("state"),
            }
        )
        if manifest.get("product_id") != expected_product_id:
            errors.append(f"{product_class}: equivalence candidate product id mismatch")
        candidate_results[product_class] = row

    portfolio = {
        str(row.get("id")): row
        for row in read_json(root / "config" / "dio_product_portfolio.json").get("products", [])
        if isinstance(row, dict)
    }

    resolved_results: dict[str, Any] = {}
    for product_class, binding in resolved.items():
        route = route_classes.get(product_class) or {}
        manifest_rel = str(binding.get("reusable_component_manifest") or "")
        manifest_path = root / manifest_rel
        canonical_product_id = str(binding.get("canonical_product_id") or "")
        component_product_id = str(binding.get("reusable_component_product_id") or "")

        row: dict[str, Any] = {
            "canonical_product_id": canonical_product_id,
            "canonical_product_exists": canonical_product_id in portfolio,
            "component_manifest": manifest_rel,
            "component_manifest_exists": manifest_path.is_file(),
            "relationship": binding.get("relationship"),
            "state": binding.get("state"),
            "route_auto_promotable": route.get("auto_promotable"),
        }

        if route.get("auto_promotable") is not False:
            errors.append(
                f"{product_class}: resolved composition binding must remain non-auto-promotable"
            )
        if binding.get("relationship") != "composition_reuse":
            errors.append(
                f"{product_class}: resolved binding must declare composition_reuse"
            )
        if binding.get("state") != "identity_equivalence_rejected":
            errors.append(
                f"{product_class}: resolved binding must reject identity equivalence"
            )
        if canonical_product_id not in portfolio:
            errors.append(
                f"{product_class}: canonical composition product missing: {canonical_product_id}"
            )

        if not manifest_path.is_file():
            errors.append(
                f"{product_class}: reusable component manifest missing: {manifest_rel}"
            )
            resolved_results[product_class] = row
            continue

        manifest = read_json(manifest_path)
        row.update(
            {
                "component_manifest_product_id": manifest.get("product_id"),
                "component_id_match": manifest.get("product_id") == component_product_id,
                "component_maturity": (manifest.get("maturity") or {}).get("state"),
            }
        )
        if manifest.get("product_id") != component_product_id:
            errors.append(
                f"{product_class}: reusable component product id mismatch"
            )

        resolved_results[product_class] = row

    extension_results: dict[str, Any] = {}
    for product_class, binding in extensions.items():
        route = route_classes.get(product_class) or {}
        extension_results[product_class] = {
            "suggested_engine": binding.get("suggested_engine"),
            "route_kind": route.get("route_kind"),
            "route_auto_promotable": route.get("auto_promotable"),
        }
        if route.get("route_kind") != "profile_extension":
            errors.append(f"{product_class}: genuine extension must remain a profile_extension route")
        if route.get("auto_promotable") is not False:
            errors.append(f"{product_class}: genuine extension must remain non-auto-promotable")

    summary = reconciliation.get("summary") or {}
    expected_counts = {
        "atlas_profile_extensions_reviewed": len(names),
        "exact_canonical_incarnations": len(exact),
        "equivalence_candidates": len(candidates),
        "resolved_composition_bindings": len(resolved),
        "genuine_profile_extensions": len(extensions),
    }
    for key, value in expected_counts.items():
        if summary.get(key) != value:
            errors.append(f"summary count mismatch for {key}: expected {value}, found {summary.get(key)}")

    if summary.get("auto_promotable_from_reconciliation") != 0:
        errors.append("reconciliation must grant zero automatic promotion authority")
    if summary.get("public_launch_authorized_from_reconciliation") != 0:
        errors.append("reconciliation must grant zero public launch authority")

    return {
        "schema": "dio.product_class_reconciliation_audit.v2",
        "state": "reconciled" if not errors else "failed",
        "summary": {
            **expected_counts,
            "errors": len(errors),
            "warnings": len(warnings),
            "auto_promotable_from_reconciliation": 0,
            "public_launch_authorized_from_reconciliation": 0,
        },
        "exact_canonical_incarnations": exact_results,
        "equivalence_candidates": candidate_results,
        "resolved_composition_bindings": resolved_results,
        "genuine_profile_extensions": extension_results,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the 53-product atlas against canonical DIO product manifests without promoting maturity or authority.")
    parser.add_argument("--reconciliation", type=Path, default=DEFAULT_RECONCILIATION)
    parser.add_argument("--routes", type=Path, default=DEFAULT_ROUTE_CONFIG)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = audit_reconciliation(args.reconciliation, args.routes)
    rendered = json.dumps(result, indent=2, ensure_ascii=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["state"] == "reconciled" else 1


if __name__ == "__main__":
    raise SystemExit(main())
