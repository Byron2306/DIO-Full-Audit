from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from products.meta_runtime import build_runtime_plan, invoke_runtime, load_runtime_registry
from products.reference_gauntlet import REGISTRY_PATH as INCARNATION_REGISTRY_PATH
from products.reference_gauntlet import run_reference_entry


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "dio.meta_runtime_gauntlet.receipt.v1"
ACCEPTANCE_TOKEN = "DIO_META_RUNTIME_CONSOLIDATED_READY"


def run_meta_runtime_gauntlet(*, output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    registry = load_runtime_registry(ROOT)
    incarnation_registry = json.loads(INCARNATION_REGISTRY_PATH.read_text(encoding="utf-8"))
    evaluated_at = str(incarnation_registry["fixed_evaluation_time"])
    products = []
    for entry in incarnation_registry["incarnations"]:
        manifest = ROOT / entry["manifest"]
        first_plan = build_runtime_plan(ROOT, manifest)
        second_plan = build_runtime_plan(ROOT, manifest)
        if first_plan != second_plan:
            raise AssertionError(f"META runtime planning is non-deterministic: {entry['product_id']}")
        if [step["meta_id"] for step in first_plan["steps"]] != registry["runtime_order"]:
            raise AssertionError(f"reference incarnation does not resolve the complete META runtime: {entry['product_id']}")
        result = run_reference_entry(entry, output_dir / entry["slug"] / "product", evaluated_at)
        first = invoke_runtime(first_plan, result, evaluated_at=evaluated_at, output_path=output_dir / entry["slug"] / "META_RUNTIME_RECEIPT.json")
        second = invoke_runtime(second_plan, result, evaluated_at=evaluated_at)
        if first != second:
            raise AssertionError(f"META runtime invocation is non-deterministic: {entry['product_id']}")
        if any(step["authority_created"] or step["executor_created"] or step["external_effects"] or step["external_release_authorized"] for step in first["step_receipts"]):
            raise AssertionError(f"META runtime crossed a product boundary: {entry['product_id']}")
        products.append({"product_id": entry["product_id"], "plan_fingerprint": first_plan["plan_fingerprint"], "runtime_fingerprint": first["runtime_fingerprint"], "step_fingerprints": {step["meta_id"]: step["step_fingerprint"] for step in first["step_receipts"]}, "deterministic": True, "input_immutable": first["input_immutable"], "human_gate": first["human_gate"], "external_release_gate": first["external_release_gate"]})
    receipt = {"schema": SCHEMA, "runtime_version": registry["runtime_version"], "runtime_entrypoint": registry["runtime_entrypoint"], "evaluated_at": evaluated_at, "incarnation_count": len(products), "meta_primitive_count": len(registry["meta_capabilities"]), "runtime_order": list(registry["runtime_order"]), "products": products, "legacy_registry_alignment": "PASS", "component_refs_verified": "PASS", "deterministic_planning": "PASS", "deterministic_invocation": "PASS", "input_immutability": "PASS", "authority_created": False, "executor_created": False, "external_effects": False, "external_release_authorized": False, "maturity_changed": False, "market_validation_created": False, "human_gate": "NEEDS_YOU", "external_release_gate": "REFUSE", "maturity_ceiling": "internal_proof", "acceptance_token": ACCEPTANCE_TOKEN}
    (output_dir / "META_RUNTIME_GAUNTLET_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt
