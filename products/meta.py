from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from products.registry import load_portfolio

ROOT = Path(__file__).resolve().parents[1]
META_REGISTRY_PATH = ROOT / "config" / "dio_meta_products.json"
META_REGISTRY_SCHEMA = "dio.meta_products.registry.v1"
META_COMPOSITION_SCHEMA = "dio.meta_product.composition.v1"
EXPECTED_META_PRODUCTS = {
    "meta_evidence",
    "meta_assurance",
    "meta_authority",
    "meta_room",
}


class MetaProductError(ValueError):
    pass


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def load_meta_registry(path: Path = META_REGISTRY_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_meta_registry(payload)
    return payload


def _meta_rows(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["id"]): row for row in registry.get("meta_products") or []}


def _vertical_rows(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["product_id"]): row for row in registry.get("vertical_compositions") or []}


def validate_meta_registry(
    registry: dict[str, Any],
    *,
    portfolio: dict[str, Any] | None = None,
) -> None:
    if registry.get("schema") != META_REGISTRY_SCHEMA:
        raise MetaProductError("Unsupported DIO META product registry schema.")

    laws = registry.get("laws") or {}
    required_false = (
        "meta_product_creates_authority",
        "meta_product_executes",
        "meta_product_changes_vertical_maturity",
        "meta_product_implies_market_validation",
        "new_executors_created",
    )
    for key in required_false:
        if laws.get(key) is not False:
            raise MetaProductError(f"META product law must remain false: {key}")
    if laws.get("vertical_risk_boundary_preserved") is not True:
        raise MetaProductError("META products must preserve vertical product risk boundaries.")
    if laws.get("kernel_authority") != "Valinor":
        raise MetaProductError("Valinor must remain sole kernel authority.")
    if laws.get("execution_identity_authority") != "ARDA":
        raise MetaProductError("ARDA must remain execution identity / attestation authority.")

    meta_products = registry.get("meta_products") or []
    meta_ids = [str(row.get("id") or "") for row in meta_products]
    if any(not meta_id for meta_id in meta_ids) or len(meta_ids) != len(set(meta_ids)):
        raise MetaProductError("META product IDs must be present and unique.")
    if set(meta_ids) != EXPECTED_META_PRODUCTS:
        raise MetaProductError(f"META product set must be exactly {sorted(EXPECTED_META_PRODUCTS)}")
    for row in meta_products:
        if row.get("authority") is not False:
            raise MetaProductError(f"META product may not create authority: {row.get('id')}")
        if row.get("execution") is not False:
            raise MetaProductError(f"META product may not execute: {row.get('id')}")
        if row.get("external_release") is not False:
            raise MetaProductError(f"META product may not authorize external release: {row.get('id')}")
        capabilities = row.get("capabilities") or []
        if not capabilities or len(capabilities) != len(set(capabilities)):
            raise MetaProductError(f"META product capabilities must be present and unique: {row.get('id')}")
        component_refs = row.get("component_refs") or []
        if not component_refs or len(component_refs) != len(set(component_refs)):
            raise MetaProductError(f"META product component refs must be present and unique: {row.get('id')}")

    portfolio = copy.deepcopy(portfolio if portfolio is not None else load_portfolio())
    if portfolio.get("schema") != "dio.product_portfolio.v1":
        raise MetaProductError("Unsupported DIO product portfolio schema.")
    profiles = {str(row["id"]): row for row in portfolio.get("products") or []}

    mappings = registry.get("vertical_compositions") or []
    mapped_ids = [str(row.get("product_id") or "") for row in mappings]
    if any(not product_id for product_id in mapped_ids) or len(mapped_ids) != len(set(mapped_ids)):
        raise MetaProductError("Vertical composition product IDs must be present and unique.")
    if set(mapped_ids) != set(profiles):
        missing = sorted(set(profiles) - set(mapped_ids))
        extra = sorted(set(mapped_ids) - set(profiles))
        raise MetaProductError(f"META vertical mapping must cover the governed portfolio exactly; missing={missing}, extra={extra}")

    known_meta = set(meta_ids)
    used_meta: set[str] = set()
    for mapping in mappings:
        product_id = str(mapping["product_id"])
        profile = profiles[product_id]
        primary = str(mapping.get("primary_meta_product") or "")
        required = [str(item) for item in mapping.get("required_meta_products") or []]
        release_guard = mapping.get("release_guard_meta_product")

        if not required or len(required) != len(set(required)):
            raise MetaProductError(f"Vertical composition must have unique required META products: {product_id}")
        if not set(required).issubset(known_meta):
            raise MetaProductError(f"Vertical composition references unknown META products: {product_id}")
        if primary not in required:
            raise MetaProductError(f"Primary META product must be part of required composition: {product_id}")
        if release_guard is not None and str(release_guard) not in known_meta:
            raise MetaProductError(f"Unknown release guard META product: {product_id}")

        expected_surface = "customer_facing" if profile.get("customer_facing") is True else "internal"
        if mapping.get("surface_mode") != expected_surface:
            raise MetaProductError(f"META surface mode must preserve portfolio truth for {product_id}")
        if profile.get("customer_facing") is True and release_guard != "meta_authority":
            raise MetaProductError(f"Customer-facing product must retain META Authority release guard: {product_id}")
        if product_id == "dio_capitalroom":
            if mapping.get("surface_mode") != "internal":
                raise MetaProductError("CapitalRoom must remain internal in META productisation.")
            if release_guard is not None:
                raise MetaProductError("CapitalRoom must not gain an external release guard through META productisation.")

        used_meta.update(required)
        if release_guard:
            used_meta.add(str(release_guard))

    if used_meta != EXPECTED_META_PRODUCTS:
        raise MetaProductError("Every canonical META product must be used by at least one governed vertical composition.")


def compose_vertical_product(
    product_id: str,
    *,
    registry: dict[str, Any] | None = None,
    portfolio: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = copy.deepcopy(registry if registry is not None else load_meta_registry())
    portfolio = copy.deepcopy(portfolio if portfolio is not None else load_portfolio())
    validate_meta_registry(registry, portfolio=portfolio)

    profiles = {str(row["id"]): row for row in portfolio["products"]}
    mappings = _vertical_rows(registry)
    meta = _meta_rows(registry)
    if product_id not in profiles or product_id not in mappings:
        raise MetaProductError(f"Unknown governed product for META composition: {product_id}")

    profile = profiles[product_id]
    mapping = mappings[product_id]
    required_ids = [str(item) for item in mapping["required_meta_products"]]

    meta_products = []
    for meta_id in required_ids:
        row = meta[meta_id]
        meta_products.append(
            {
                "id": meta_id,
                "name": row["name"],
                "role": row["role"],
                "capabilities": copy.deepcopy(row["capabilities"]),
                "component_refs": copy.deepcopy(row["component_refs"]),
                "authority": False,
                "execution": False,
                "external_release": False,
            }
        )

    body: dict[str, Any] = {
        "schema": META_COMPOSITION_SCHEMA,
        "product_id": product_id,
        "product_name": profile.get("name"),
        "category": profile.get("category"),
        "source_product_status": profile.get("status"),
        "runtime_mode": profile.get("runtime_mode"),
        "customer_facing": profile.get("customer_facing"),
        "campaign_enabled": profile.get("campaign_enabled"),
        "surface_mode": mapping.get("surface_mode"),
        "primary_meta_product": mapping.get("primary_meta_product"),
        "required_meta_products": required_ids,
        "meta_products": meta_products,
        "release_guard_meta_product": mapping.get("release_guard_meta_product"),
        "risk_boundary": profile.get("risk_boundary"),
        "activation_gates": copy.deepcopy(profile.get("activation_gates") or []),
        "expected_outputs": copy.deepcopy(profile.get("expected_outputs") or []),
        "authority_created": False,
        "executor_created": False,
        "external_release_authorized": False,
        "market_validation_created": False,
        "maturity_changed": False,
        "kernel_authority": "Valinor",
        "execution_identity_authority": "ARDA",
    }
    body["fingerprint"] = _fingerprint(body)
    return body


def validate_vertical_composition(
    composition: dict[str, Any],
    *,
    registry: dict[str, Any] | None = None,
    portfolio: dict[str, Any] | None = None,
) -> None:
    if composition.get("schema") != META_COMPOSITION_SCHEMA:
        raise MetaProductError("Unsupported META product composition schema.")
    product_id = str(composition.get("product_id") or "")
    expected = compose_vertical_product(product_id, registry=registry, portfolio=portfolio)
    if composition != expected:
        raise MetaProductError("META product composition does not match canonical governed product truth.")


def compose_all_vertical_products(
    *,
    registry: dict[str, Any] | None = None,
    portfolio: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    registry = copy.deepcopy(registry if registry is not None else load_meta_registry())
    portfolio = copy.deepcopy(portfolio if portfolio is not None else load_portfolio())
    validate_meta_registry(registry, portfolio=portfolio)
    product_ids = [str(row["id"]) for row in portfolio["products"]]
    return [compose_vertical_product(product_id, registry=registry, portfolio=portfolio) for product_id in product_ids]
