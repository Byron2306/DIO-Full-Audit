from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "design_legal_commercial_products.json"
ROUTES_PATH = ROOT / "config" / "product_class_routes.json"
EXPECTED_PRODUCTS = {
    "dio_site_studio",
    "dio_launch_studio",
    "dio_report_pitch_studio",
    "dio_popia_readiness",
    "dio_corporate_readiness",
    "dio_contract_desk",
}
NON_ROUTE_BINDINGS = {"commercial_composition", "internal_capability", "internal_runtime", "presence_owner"}
FORBIDDEN_KEYS = {"executor", "executor_id", "executor_ref", "canonical_executor", "controlled_processor"}


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")


def _sha(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _find_forbidden(value: Any, path: str = "root") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            here = f"{path}.{key}"
            if key in FORBIDDEN_KEYS:
                found.append(here)
            found.extend(_find_forbidden(child, here))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_find_forbidden(child, f"{path}[{index}]"))
    return found


def _resolve_binding(routes: dict[str, Any], binding: str) -> bool:
    if binding in NON_ROUTE_BINDINGS:
        return True
    parts = binding.split(".", 1)
    if len(parts) != 2:
        return False
    section, key = parts
    return key in (routes.get(section) or {})


def validate_registry(registry: dict[str, Any], routes: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if registry.get("schema") != "dio.commercial_product_compositions.v1":
        errors.append("unsupported_registry_schema")
    products = registry.get("products") or {}
    if set(products) != EXPECTED_PRODUCTS:
        errors.append("expected_exact_six_product_gap_fill")
    forbidden = _find_forbidden(registry)
    if forbidden:
        errors.extend(f"forbidden_executor_binding:{path}" for path in forbidden)

    design = 0
    legal = 0
    for product_id, product in products.items():
        family = product.get("family")
        if family == "design_studio":
            design += 1
        elif family == "legal_operations":
            legal += 1
        else:
            errors.append(f"{product_id}:unsupported_family")
        pricing = product.get("pricing") or {}
        if pricing.get("currency") != "ZAR" or pricing.get("state") != "launch_hypothesis_not_validated":
            errors.append(f"{product_id}:pricing_truth_boundary_drift")
        if product.get("commercial_state") != "composition_defined_execution_proof_required":
            errors.append(f"{product_id}:commercial_state_drift")
        if product.get("intake_owner") not in {"document_studio", "evidex"}:
            errors.append(f"{product_id}:unsupported_intake_owner")
        effects = product.get("effects") or {}
        for field in ("publication", "spend", "send"):
            if effects.get(field) is not False:
                errors.append(f"{product_id}:{field}_must_be_false")
        if family == "legal_operations":
            if product.get("governance_owner") != "legalis":
                errors.append(f"{product_id}:legalis_must_own_governance")
            boundary = product.get("legal_boundary") or {}
            for field, value in boundary.items():
                if field.endswith("required_when_interpretation_needed"):
                    if value is not True:
                        errors.append(f"{product_id}:{field}_must_be_true")
                elif value is not False:
                    errors.append(f"{product_id}:{field}_must_be_false")
            for field in ("filing", "legal_representation"):
                if effects.get(field) is not False:
                    errors.append(f"{product_id}:{field}_must_be_false")
        for component in product.get("components") or []:
            binding = str(component.get("binding") or "")
            if not _resolve_binding(routes, binding):
                errors.append(f"{product_id}:unresolved_component_binding:{binding}")

    portfolio = registry.get("portfolio_truth") or {}
    if portfolio.get("product_count") != 6 or design != 3 or legal != 3:
        errors.append("portfolio_counts_drift")
    if portfolio.get("executors_created_by_this_registry") != 0 or portfolio.get("execution_proofs_created_by_this_registry") != 0:
        errors.append("registry_illegally_claims_execution")
    if portfolio.get("public_launch_authority_created") is not False or portfolio.get("commercial_validation_created") is not False:
        errors.append("registry_illegally_claims_launch_or_validation")

    return {
        "schema": "dio.commercial_product_composition_validation.v1",
        "state": "VALID" if not errors else "INVALID",
        "errors": errors,
        "warnings": warnings,
        "product_count": len(products),
        "design_products": design,
        "legal_operations_products": legal,
        "executor_bindings_found": len(forbidden),
        "public_launch_authority_created": False,
    }


def build_catalog(output: Path) -> dict[str, Any]:
    registry = _read(REGISTRY_PATH)
    routes = _read(ROUTES_PATH)
    validation = validate_registry(registry, routes)
    if validation["state"] != "VALID":
        raise RuntimeError("Design/Legal commercial registry invalid: " + "; ".join(validation["errors"]))

    products = registry["products"]
    catalog_rows = []
    briefs = []
    for product_id, product in products.items():
        catalog_rows.append({
            "product_id": product_id,
            "label": product["label"],
            "family": product["family"],
            "work_pattern": product["work_pattern"],
            "buyer": product["buyer"],
            "pain": product["pain"],
            "outcome": product["outcome"],
            "pricing": product["pricing"],
            "intake_owner": product["intake_owner"],
            "component_ids": [row["id"] for row in product.get("components") or []],
            "deliverables": product["deliverables"],
            "human_gates": product["human_gates"],
            "commercial_state": product["commercial_state"],
        })
        briefs.append({
            "schema": "dio.nichefoundry.composition_brief.v1",
            "product_id": product_id,
            "label": product["label"],
            "family": product["family"],
            "target_buyer": product["buyer"],
            "buyer_pain": product["pain"],
            "desired_outcome": product["outcome"],
            "offer": {"pricing": product["pricing"], "deliverables": product["deliverables"], "bounded_case": True},
            "proof_and_truth": {
                "composition_only": True,
                "execution_proved_by_this_build": False,
                "customer_validated": False,
                "public_launch_authorized": False,
                "legal_advice_created": False
            },
            "release": {"state": "held", "operator_required": True},
            "spend": {"state": "disabled", "operator_required": True}
        })

    catalog = {
        "schema": "dio.design_legal_commercial_catalog.v1",
        "source_registry": str(REGISTRY_PATH.relative_to(ROOT)),
        "source_registry_sha256": _sha(registry),
        "source_route_contract": str(ROUTES_PATH.relative_to(ROOT)),
        "source_route_contract_sha256": _sha(routes),
        "validation": validation,
        "products": catalog_rows,
        "summary": {
            "products": len(catalog_rows),
            "design_products": sum(1 for row in catalog_rows if row["family"] == "design_studio"),
            "legal_operations_products": sum(1 for row in catalog_rows if row["family"] == "legal_operations"),
            "executors_created": 0,
            "execution_proofs_created": 0,
            "public_launch_authorized": False,
            "commercial_validation_created": False
        },
        "claim_ceiling": "This build proves structural commercial composition and route-binding consistency only. It does not prove fulfilment execution, legal correctness, customer demand, willingness to pay, public launch authority or external release authority."
    }
    brief_pack = {
        "schema": "dio.nichefoundry.composition_brief_pack.v1",
        "briefs": briefs,
        "summary": {"briefs": len(briefs), "publication_authorized": False, "spend_authorized": False}
    }
    output.mkdir(parents=True, exist_ok=True)
    _write(output / "DESIGN_LEGAL_COMMERCIAL_CATALOG.json", catalog)
    _write(output / "NICHEFOUNDRY_COMPOSITION_BRIEFS.json", brief_pack)
    _write(output / "VALIDATION_RECEIPT.json", validation)
    return catalog


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the structural Design Studio + Legal Operations commercial catalog.")
    parser.add_argument("--output", type=Path, default=ROOT / "state" / "design_legal_commercial_catalog")
    args = parser.parse_args()
    catalog = build_catalog(args.output.resolve())
    print(json.dumps(catalog["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
