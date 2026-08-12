from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Check DIO META product layer readiness.")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--core", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    core = Path(args.core).resolve()
    out = Path(args.out).resolve()
    blockers: list[str] = []

    if str(core) not in sys.path:
        sys.path.insert(0, str(core))

    from products.meta import compose_all_vertical_products, load_meta_registry, validate_meta_registry
    from products.registry import load_portfolio

    wave9_path = workspace / "receipts" / "fusion-wave9-latest.json"
    if not wave9_path.is_file():
        blockers.append(f"missing Wave 9 receipt: {wave9_path}")
        wave9 = {}
    else:
        wave9 = _load(wave9_path)
        if wave9.get("state") != "FUSION_WAVE9_READY":
            blockers.append(f"Wave 9 state is not FUSION_WAVE9_READY: {wave9.get('state')}")
        if wave9.get("fusion_wave_receipts_verified") != 8:
            blockers.append("Wave 9 receipt does not prove all eight prior Fusion Wave receipts.")
        if wave9.get("product_profiles") != 9:
            blockers.append("Wave 9 receipt does not expose all nine governed product profiles.")
        if wave9.get("capitalroom_authority") is not False or wave9.get("capitalroom_execution") is not False:
            blockers.append("Wave 9 CapitalRoom constitutional boundary is not preserved.")

    required_paths = [
        core / "products" / "meta.py",
        core / "config" / "dio_meta_products.json",
        core / "schemas" / "dio_meta_products.schema.json",
    ]
    for path in required_paths:
        if not path.is_file():
            blockers.append(f"missing META product layer path: {path}")

    registry = {}
    compositions = []
    portfolio = {}
    try:
        if all(path.is_file() for path in required_paths):
            registry = load_meta_registry(core / "config" / "dio_meta_products.json")
            portfolio = load_portfolio(core / "config" / "dio_product_portfolio.json")
            validate_meta_registry(registry, portfolio=portfolio)
            compositions = compose_all_vertical_products(registry=registry, portfolio=portfolio)
    except Exception as exc:
        blockers.append(f"META product registry/composition validation failed: {exc}")

    meta_products = registry.get("meta_products") or []
    mappings = registry.get("vertical_compositions") or []
    customer_facing = [row for row in compositions if row.get("customer_facing") is True]
    internal = [row for row in compositions if row.get("customer_facing") is not True]
    release_guarded = [row for row in customer_facing if row.get("release_guard_meta_product") == "meta_authority"]

    component_refs = sorted({ref for row in meta_products for ref in row.get("component_refs") or []})
    missing_components = [ref for ref in component_refs if not (core / ref).is_file()]
    if missing_components:
        blockers.append(f"META product component refs are missing from core: {missing_components}")

    receipt = {
        "schema": "dio.meta_product_layer.receipt.v1",
        "state": "META_PRODUCT_LAYER_READY" if not blockers else "BLOCKED",
        "depends_on": {
            "fusion_wave9_receipt": str(wave9_path),
            "fusion_wave9_state": wave9.get("state"),
        },
        "meta_products": len(meta_products),
        "vertical_compositions": len(mappings),
        "customer_facing_verticals": len(customer_facing),
        "internal_verticals": len(internal),
        "customer_facing_release_guarded": len(release_guarded),
        "component_refs_verified": len(component_refs) - len(missing_components),
        "meta_product_authority": False,
        "meta_product_execution": False,
        "new_executors_created": False,
        "vertical_maturity_changed": False,
        "market_validation_created": False,
        "kernel_authority": "Valinor",
        "execution_identity_authority": "ARDA",
        "blockers": blockers,
        "receipt": str(out),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
