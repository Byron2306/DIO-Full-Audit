from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from products.compiler import compile_manifest


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "portfolio" / "meta_capabilities.json"
LEGACY_PATH = ROOT / "config" / "dio_meta_products.json"
PLAN_SCHEMA = "dio.meta_runtime.plan.v1"
RECEIPT_SCHEMA = "dio.meta_runtime.receipt.v1"
STEP_SCHEMA = "dio.meta_runtime.step_receipt.v1"
EXPECTED_META = {"meta_evidence", "meta_assurance", "meta_authority", "meta_room"}


class MetaRuntimeError(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MetaRuntimeError(f"expected JSON object: {path}")
    return payload


def load_runtime_registry(root: Path = ROOT) -> dict[str, Any]:
    registry = _load(root / "config" / "portfolio" / "meta_capabilities.json")
    validate_runtime_registry(registry, root=root)
    return registry


def validate_runtime_registry(registry: dict[str, Any], *, root: Path = ROOT) -> None:
    if registry.get("schema") != "dio.meta_capabilities.registry.v1":
        raise MetaRuntimeError("unexpected canonical META registry schema")
    if registry.get("runtime_version") != "1.0.0":
        raise MetaRuntimeError("unsupported META runtime version")
    if registry.get("runtime_entrypoint") != "products/meta_runtime.py":
        raise MetaRuntimeError("META runtime must have one canonical entrypoint")
    laws = registry.get("laws") or {}
    required = {
        "exact_primitive_count": 4,
        "creates_authority": False,
        "creates_executor": False,
        "changes_maturity": False,
        "implies_market_validation": False,
        "executes_external_effects": False,
        "single_runtime_entrypoint": True,
        "legacy_registry_must_align": True,
        "vertical_compositions_belong_in_product_manifests": True,
    }
    if any(laws.get(key) != value for key, value in required.items()):
        raise MetaRuntimeError("canonical META runtime laws are incomplete or unsafe")
    rows = registry.get("meta_capabilities") or []
    by_id = {str(row.get("id") or ""): row for row in rows}
    if set(by_id) != EXPECTED_META or len(rows) != 4:
        raise MetaRuntimeError("META runtime must define exactly four unique primitives")
    order = [str(item) for item in registry.get("runtime_order") or []]
    if set(order) != EXPECTED_META or len(order) != 4:
        raise MetaRuntimeError("META runtime order must contain exactly the four primitives")
    seen: set[str] = set()
    handlers: set[str] = set()
    for meta_id in order:
        row = by_id[meta_id]
        dependencies = [str(item) for item in row.get("depends_on") or []]
        if not set(dependencies).issubset(seen):
            raise MetaRuntimeError(f"META dependency order is invalid: {meta_id}")
        handler = str(row.get("handler_id") or "")
        if not handler or handler in handlers:
            raise MetaRuntimeError(f"META handler must be present and unique: {meta_id}")
        handlers.add(handler)
        for key in ("input_contract", "output_contract", "component_refs"):
            values = row.get(key) or []
            if not values or len(values) != len(set(values)):
                raise MetaRuntimeError(f"META {key} must be present and unique: {meta_id}")
        missing = [ref for ref in row["component_refs"] if not (root / ref).is_file()]
        if missing:
            raise MetaRuntimeError(f"META component refs are missing for {meta_id}: {missing}")
        seen.add(meta_id)
    legacy = _load(root / str(registry.get("legacy_registry") or ""))
    legacy_rows = {str(row["id"]): row for row in legacy.get("meta_products") or []}
    if set(legacy_rows) != EXPECTED_META:
        raise MetaRuntimeError("legacy META registry primitive set drifted")
    for meta_id, row in by_id.items():
        old = legacy_rows[meta_id]
        if row["role"] != old.get("role") or row["component_refs"] != old.get("component_refs"):
            raise MetaRuntimeError(f"legacy META definition drifted from canonical registry: {meta_id}")


def build_runtime_plan(root: Path, manifest_path: Path) -> dict[str, Any]:
    root = root.resolve()
    registry = load_runtime_registry(root)
    compiled = compile_manifest(root, manifest_path)
    selected = {str(row["id"]): row for row in compiled["meta_capabilities"]}
    order = [item for item in registry["runtime_order"] if item in selected]
    rows = {str(row["id"]): row for row in registry["meta_capabilities"]}
    steps = []
    for position, meta_id in enumerate(order, 1):
        row = rows[meta_id]
        dependencies = [item for item in row["depends_on"] if item in selected]
        missing = sorted(set(row["depends_on"]).difference(selected))
        if missing:
            raise MetaRuntimeError(f"selected META capability lacks runtime dependencies: {meta_id} -> {missing}")
        steps.append({"position": position, "meta_id": meta_id, "handler_id": row["handler_id"], "depends_on": dependencies, "input_contract": list(row["input_contract"]), "output_contract": list(row["output_contract"]), "component_refs": list(row["component_refs"]), "authority": False, "execution": False, "external_effects": False})
    body = {"schema": PLAN_SCHEMA, "runtime_version": registry["runtime_version"], "runtime_entrypoint": registry["runtime_entrypoint"], "product_id": compiled["product_id"], "composition_fingerprint": compiled["composition_fingerprint"], "compilation_fingerprint": compiled["compilation_fingerprint"], "steps": steps, "compiled_gates": copy.deepcopy(compiled["gates"]), "authority_created": False, "executor_created": False, "external_effects": False}
    body["plan_fingerprint"] = _fingerprint(body)
    return body


def _step(meta_id: str, handler_id: str, product_id: str, inputs: dict[str, Any], outputs: dict[str, Any], dependencies: list[str]) -> dict[str, Any]:
    body = {"schema": STEP_SCHEMA, "meta_id": meta_id, "handler_id": handler_id, "product_id": product_id, "input_fingerprints": inputs, "outputs": outputs, "dependency_receipts": dependencies, "authority_created": False, "executor_created": False, "external_effects": False, "external_release_authorized": False}
    body["step_fingerprint"] = _fingerprint(body)
    return body


def _observe_evidence(plan: dict[str, Any], result: dict[str, Any], prior: dict[str, dict[str, Any]]) -> dict[str, Any]:
    case = result["case"]
    bundle = result["obligation_bundle"]
    sufficiency = result["sufficiency"]
    return _step("meta_evidence", "observe_evidence", plan["product_id"], {"case": _fingerprint(case), "obligation_bundle": bundle["fingerprint"], "sufficiency": _fingerprint(sufficiency)}, {"case_id": case["case_id"], "evidence_records": len(case.get("evidence") or []), "obligation_records": len(bundle.get("obligations") or []), "gap_state": sufficiency["state"], "fulfilment_adjudicated": False}, [])


def _artifact_integrity(result: dict[str, Any]) -> tuple[bool, dict[str, str]]:
    output_dir = Path(result["output_dir"])
    hashes: dict[str, str] = {}
    verified = True
    for row in result["proof_manifest"].get("artifacts") or []:
        path = output_dir / str(row["filename"])
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "missing"
        hashes[str(row["artifact_type"])] = actual
        verified = verified and actual == row.get("sha256")
    return verified, hashes


def _observe_assurance(plan: dict[str, Any], result: dict[str, Any], prior: dict[str, dict[str, Any]]) -> dict[str, Any]:
    receipt = result["receipt"]
    verified, hashes = _artifact_integrity(result)
    failures = []
    if receipt.get("authority_created") is not False: failures.append("authority_created")
    if receipt.get("external_effects") is not False: failures.append("external_effects")
    if receipt.get("external_release_gate") != "REFUSE": failures.append("external_release_gate")
    if not verified: failures.append("artifact_integrity")
    evidence = prior["meta_evidence"]
    return _step("meta_assurance", "observe_assurance", plan["product_id"], {"execution_receipt": _fingerprint(receipt), "proof_manifest": result["proof_manifest"]["proof_fingerprint"], "meta_evidence_receipt": evidence["step_fingerprint"]}, {"integrity_verified": verified, "artifact_hashes": hashes, "boundary_failures": failures, "attention_state": "CLEAR" if not failures else "NEEDS_YOU", "execution_block_recommended": bool(failures)}, [evidence["step_fingerprint"]])


def _observe_authority(plan: dict[str, Any], result: dict[str, Any], prior: dict[str, dict[str, Any]]) -> dict[str, Any]:
    gates = plan["compiled_gates"]
    assurance = prior["meta_assurance"]
    execution = gates["execution"]["state"]
    release = gates["external_release"]["state"]
    state = "REFUSE" if assurance["outputs"]["boundary_failures"] else execution
    return _step("meta_authority", "observe_authority", plan["product_id"], {"compiled_gates": _fingerprint(gates), "execution_receipt": _fingerprint(result["receipt"]), "meta_assurance_receipt": assurance["step_fingerprint"]}, {"authority_observation": state, "human_gate": "NEEDS_YOU", "execution_gate": execution, "release_gate": release, "capability_lease_created": False, "authorization_created": False}, [prior["meta_evidence"]["step_fingerprint"], assurance["step_fingerprint"]])


def _observe_room(plan: dict[str, Any], result: dict[str, Any], prior: dict[str, dict[str, Any]]) -> dict[str, Any]:
    verified, hashes = _artifact_integrity(result)
    dependencies = [prior[item]["step_fingerprint"] for item in ("meta_evidence", "meta_assurance", "meta_authority")]
    return _step("meta_room", "observe_room", plan["product_id"], {"proof_manifest": result["proof_manifest"]["proof_fingerprint"], "artifact_set": _fingerprint(hashes), "prior_meta_receipts": _fingerprint(dependencies)}, {"proof_fingerprint": result["proof_manifest"]["proof_fingerprint"], "artifact_hashes": hashes, "integrity_verified": verified, "disclosure_candidate_only": True, "external_release": False}, dependencies)


HANDLERS: dict[str, Callable[[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]], dict[str, Any]]] = {"observe_evidence": _observe_evidence, "observe_assurance": _observe_assurance, "observe_authority": _observe_authority, "observe_room": _observe_room}


def invoke_runtime(plan: dict[str, Any], product_result: dict[str, Any], *, evaluated_at: str, output_path: Path | None = None) -> dict[str, Any]:
    before = _fingerprint(product_result)
    step_receipts: dict[str, dict[str, Any]] = {}
    for step in plan["steps"]:
        handler = HANDLERS.get(str(step["handler_id"]))
        if handler is None:
            raise MetaRuntimeError(f"unknown canonical META handler: {step['handler_id']}")
        receipt = handler(plan, product_result, step_receipts)
        if receipt["authority_created"] or receipt["executor_created"] or receipt["external_effects"] or receipt["external_release_authorized"]:
            raise MetaRuntimeError(f"META handler crossed constitutional boundary: {step['meta_id']}")
        step_receipts[str(step["meta_id"])] = receipt
    after = _fingerprint(product_result)
    if before != after:
        raise MetaRuntimeError("META runtime mutated the product result it was observing")
    ordered = [step_receipts[step["meta_id"]] for step in plan["steps"]]
    body = {"schema": RECEIPT_SCHEMA, "runtime_version": plan["runtime_version"], "runtime_entrypoint": plan["runtime_entrypoint"], "product_id": plan["product_id"], "evaluated_at": evaluated_at, "plan_fingerprint": plan["plan_fingerprint"], "step_receipts": ordered, "input_immutable": True, "authority_created": False, "executor_created": False, "external_effects": False, "external_release_authorized": False, "human_gate": "NEEDS_YOU", "external_release_gate": "REFUSE"}
    body["runtime_fingerprint"] = _fingerprint(body)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return body
