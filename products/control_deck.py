from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from products.compiler import compile_manifest


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "portfolio" / "control_deck.json"
SCHEMA_PATH = ROOT / "schemas" / "dio_control_deck_snapshot.schema.json"
SNAPSHOT_SCHEMA = "dio.control_deck.portfolio_snapshot.v1"


class ControlDeckError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ControlDeckError(f"expected JSON object: {path}")
    return value


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _file_fingerprint(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load_control_deck_config(root: Path = ROOT) -> dict[str, Any]:
    config = _load(root / "config" / "portfolio" / "control_deck.json")
    if config.get("schema") != "dio.control_deck.config.v1":
        raise ControlDeckError("unexpected Control Deck configuration schema")
    laws = config.get("laws") or {}
    required_laws = {
        "projection_only": True,
        "creates_authority": False,
        "creates_executor": False,
        "changes_maturity": False,
        "infers_commercial_success": False,
        "external_effects": False,
        "memory_is_permission": False,
        "unknown_state_is_visible": True,
    }
    if any(laws.get(key) != value for key, value in required_laws.items()):
        raise ControlDeckError("Control Deck laws are incomplete or unsafe")
    if config.get("goldeneye", {}).get("source_branch") != "dio-c7-goldeneye-control-deck":
        raise ControlDeckError("GoldenEye provenance must remain explicit")
    return config


def validate_snapshot(root: Path, snapshot: dict[str, Any]) -> None:
    schema = _load(root / "schemas" / "dio_control_deck_snapshot.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(snapshot), key=lambda item: list(item.path))
    if errors:
        detail = "; ".join(error.message for error in errors[:5])
        raise ControlDeckError(f"Control Deck snapshot schema failure: {detail}")


def _validate_runtime_receipt(receipt: dict[str, Any]) -> None:
    if receipt.get("schema") != "dio.meta_runtime_gauntlet.receipt.v1":
        raise ControlDeckError("Control Deck requires the canonical Phase 8 gauntlet receipt")
    required_safe = {
        "authority_created": False,
        "executor_created": False,
        "external_effects": False,
        "external_release_authorized": False,
        "maturity_changed": False,
        "market_validation_created": False,
        "human_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
    }
    if any(receipt.get(key) != value for key, value in required_safe.items()):
        raise ControlDeckError("unsafe or untruthful META runtime receipt refused")
    if receipt.get("deterministic_invocation") != "PASS" or receipt.get("input_immutability") != "PASS":
        raise ControlDeckError("unverified META runtime receipt refused")


def build_portfolio_snapshot(root: Path, runtime_receipt: dict[str, Any]) -> dict[str, Any]:
    root = root.resolve()
    config = load_control_deck_config(root)
    _validate_runtime_receipt(runtime_receipt)

    suite_path = root / "config" / "portfolio" / "suites.json"
    maturity_path = root / "config" / "portfolio" / "maturity_vocabulary.json"
    meta_path = root / "config" / "portfolio" / "meta_capabilities.json"
    suites_registry = _load(suite_path)
    maturity_registry = _load(maturity_path)
    suite_rows = suites_registry.get("suites") or []
    suite_ids = [str(item.get("id") or "") for item in suite_rows]
    if len(suite_ids) != 6 or len(set(suite_ids)) != 6:
        raise ControlDeckError("Control Deck requires the six canonical portfolio suites")

    maturity_rows = maturity_registry.get("states") or []
    maturity_by_id = {str(item["id"]): item for item in maturity_rows}
    runtime_products = {str(item.get("product_id") or ""): item for item in runtime_receipt.get("products") or []}
    manifests = sorted((root / "config" / "products" / "manifests").glob("*.json"))
    if not manifests:
        raise ControlDeckError("no canonical product manifests found")

    products: list[dict[str, Any]] = []
    attention: list[dict[str, Any]] = []
    for manifest_path in manifests:
        manifest = _load(manifest_path)
        compiled = compile_manifest(root, manifest_path)
        product_id = str(compiled["product_id"])
        runtime = runtime_products.get(product_id)
        if runtime is None:
            raise ControlDeckError(f"META runtime receipt missing canonical product: {product_id}")
        if runtime.get("human_gate") != "NEEDS_YOU" or runtime.get("external_release_gate") != "REFUSE":
            raise ControlDeckError(f"unsafe runtime gates refused for {product_id}")
        product_suites = [str(item) for item in manifest.get("suite_ids") or []]
        unknown = sorted(set(product_suites).difference(suite_ids))
        if unknown:
            raise ControlDeckError(f"unknown suite binding for {product_id}: {unknown}")
        maturity = str(compiled["maturity"]["state"])
        if maturity not in maturity_by_id:
            raise ControlDeckError(f"unknown maturity state for {product_id}: {maturity}")
        flags = dict(compiled["maturity"].get("operational_flags") or {})
        product = {
            "product_id": product_id,
            "name": compiled["name"],
            "incarnation_id": manifest["incarnation"]["id"],
            "suite_ids": product_suites,
            "maturity": {
                "state": maturity,
                "label": maturity_by_id[maturity]["label"],
                "rank": maturity_by_id[maturity]["rank"],
            },
            "operational_flags": flags,
            "gates": {key: value["state"] for key, value in compiled["gates"].items()},
            "composition_fingerprint": compiled["composition_fingerprint"],
            "compilation_fingerprint": compiled["compilation_fingerprint"],
            "runtime_fingerprint": runtime["runtime_fingerprint"],
            "meta_step_fingerprints": dict(runtime["step_fingerprints"]),
            "human_gate": "NEEDS_YOU",
            "external_release_gate": "REFUSE",
            "authority_created": False,
            "executor_created": False,
            "external_effects": False,
        }
        products.append(product)
        attention.append({
            "attention_id": f"attention:{product_id}:human_review",
            "product_id": product_id,
            "severity": "human_boundary",
            "state": "NEEDS_YOU",
            "reason": compiled["gates"]["human_review"]["reason"],
            "authorised_action": "inspect_bound_receipts_and_record_human_decision",
            "may_execute": False,
            "may_release": False,
            "may_change_maturity": False,
        })

    products.sort(key=lambda item: item["product_id"])
    attention.sort(key=lambda item: item["attention_id"])
    product_by_suite = {suite_id: [] for suite_id in suite_ids}
    for product in products:
        for suite_id in product["suite_ids"]:
            product_by_suite[suite_id].append(product["product_id"])
    suites = [
        {
            "suite_id": row["id"],
            "name": row["name"],
            "registered_product_count": len(product_by_suite[row["id"]]),
            "product_ids": sorted(product_by_suite[row["id"]]),
            "runtime_changed": False,
            "authority_created": False,
            "maturity_changed": False,
        }
        for row in suite_rows
    ]

    summary = {
        "suite_count": len(suites),
        "registered_product_count": len(products),
        "runtime_observed_product_count": len(runtime_products),
        "needs_you_count": len(attention),
        "internally_proven_count": sum(item["maturity"]["state"] == "internal_proof" for item in products),
        "externally_validated_count": sum(bool(item["operational_flags"].get("externally_validated")) for item in products),
        "revenue_proven_count": sum(bool(item["operational_flags"].get("revenue_proven")) for item in products),
        "external_release_authorized_count": 0,
    }
    body: dict[str, Any] = {
        "schema": SNAPSHOT_SCHEMA,
        "control_deck_version": config["control_deck_version"],
        "surface": "GOLDENEYE",
        "observed_at": runtime_receipt["evaluated_at"],
        "source_fingerprints": {
            "control_deck_config": _file_fingerprint(root / "config" / "portfolio" / "control_deck.json"),
            "suite_registry": _file_fingerprint(suite_path),
            "maturity_vocabulary": _file_fingerprint(maturity_path),
            "meta_registry": _file_fingerprint(meta_path),
            "meta_runtime_gauntlet": _fingerprint(runtime_receipt),
        },
        "summary": summary,
        "meta_runtime": {
            "entrypoint": runtime_receipt["runtime_entrypoint"],
            "runtime_version": runtime_receipt["runtime_version"],
            "primitive_count": runtime_receipt["meta_primitive_count"],
            "runtime_order": list(runtime_receipt["runtime_order"]),
            "deterministic_invocation": runtime_receipt["deterministic_invocation"],
            "input_immutability": runtime_receipt["input_immutability"],
        },
        "suites": suites,
        "products": products,
        "operator_attention": attention,
        "truth_boundaries": {
            "projection_only": True,
            "memory_is_permission": False,
            "authority_created": False,
            "executor_created": False,
            "external_effects": False,
            "maturity_changed": False,
            "market_validation_created": False,
            "commercial_success_inferred": False,
            "external_release_authorized": False,
        },
    }
    body["snapshot_fingerprint"] = _fingerprint(body)
    validate_snapshot(root, body)
    return body


def write_snapshot(snapshot: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path
