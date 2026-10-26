from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from products.compiler import (
    compile_manifest,
    load_capability_catalog,
    load_json,
    load_work_patterns,
    resolve_capability,
    sha256_file,
    sha256_json,
)


RUNTIME_SCHEMA = "dio.work_pattern_plan.v1"
RUNTIME_VERSION = "1.0.0"
RUNTIME_SOURCE_REF = "products/work_pattern_runtime.py"
RUNTIME_REGISTRY_REF = Path("config/portfolio/work_pattern_runtime.json")
FOCUS_PATTERNS = {"WP01", "WP05", "WP08", "WP10", "WP11"}


class WorkPatternRuntimeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise WorkPatternRuntimeError(message)


def _schema_errors(schema: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda err: list(err.absolute_path))
    rendered: list[str] = []
    for error in errors[:12]:
        where = ".".join(str(part) for part in error.absolute_path) or "<root>"
        rendered.append(f"{where}: {error.message}")
    return rendered


def load_runtime_registry(root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any], str]:
    root = root.resolve()
    path = root / RUNTIME_REGISTRY_REF
    payload = load_json(path)
    schema = load_json(root / "schemas" / "dio_work_pattern_runtime.schema.json")
    errors = _schema_errors(schema, payload)
    require(not errors, "work-pattern runtime schema validation failed: " + " | ".join(errors))

    laws = payload.get("laws") or {}
    require(laws.get("contracts_request_capabilities_not_providers") is True, "work-pattern contracts must request capabilities, not providers")
    require(laws.get("contracts_create_authority") is False, "work-pattern contracts may not create authority")
    require(laws.get("contracts_create_executors") is False, "work-pattern contracts may not create executors")
    require(laws.get("runtime_executes_side_effects") is False, "Phase 3 runtime must remain non-executing")
    require(laws.get("provider_applicability_remains_product_scoped") is True, "provider applicability must remain product-scoped")

    rows = payload.get("contracts") or []
    contracts: dict[str, dict[str, Any]] = {}
    for row in rows:
        pattern_id = str(row.get("work_pattern_id") or "")
        require(pattern_id and pattern_id not in contracts, f"duplicate/empty work-pattern contract: {pattern_id}")
        operation_ids: set[str] = set()
        for operation in row.get("operations") or []:
            operation_id = str(operation.get("operation_id") or "")
            require(operation_id and operation_id not in operation_ids, f"duplicate/empty operation in {pattern_id}: {operation_id}")
            operation_ids.add(operation_id)
            capability_id = str(operation.get("capability_id") or "")
            require(not capability_id.startswith("product.executor."), f"work-pattern contract may not bind a product executor: {pattern_id}/{operation_id}")
            require(operation.get("execution_required") is False, f"Phase 3 operation may not request execution authority: {pattern_id}/{operation_id}")
        contracts[pattern_id] = copy.deepcopy(row)

    canonical, _ = load_work_patterns(root)
    require(set(contracts) == set(canonical), "runtime registry must declare exactly the twelve canonical work patterns")
    require(set(payload.get("focus_patterns") or []) == FOCUS_PATTERNS, "Phase 3 focus pattern set drift")

    catalog, _ = load_capability_catalog(root)
    for pattern_id, contract in contracts.items():
        expected = canonical[pattern_id]
        require(contract.get("human_boundary") == expected.get("human_boundary"), f"human boundary drift for {pattern_id}")
        expected_stage = "v1_focus" if pattern_id in FOCUS_PATTERNS else "declared"
        require(contract.get("runtime_stage") == expected_stage, f"runtime stage mismatch for {pattern_id}")
        if pattern_id in FOCUS_PATTERNS:
            require(bool(contract.get("operations")), f"focus pattern has no operations: {pattern_id}")
        else:
            require(not contract.get("operations"), f"non-focus pattern unexpectedly gained Phase 3 operations: {pattern_id}")
        for operation in contract.get("operations") or []:
            capability_id = str(operation["capability_id"])
            require(capability_id in catalog, f"runtime operation references unknown capability: {pattern_id}/{capability_id}")

    return contracts, payload, f"sha256:{sha256_file(path)}"


def _pattern_state(operation_plan: list[dict[str, Any]]) -> str:
    if not operation_plan:
        return "DECLARED"
    states = [str(item["resolution_state"]) for item in operation_plan]
    if any(state in {"UNKNOWN", "UNAVAILABLE"} for state in states):
        return "BLOCKED"
    if all(state == "RESOLVED" for state in states):
        return "READY"
    if all(state == "PLANNED" for state in states):
        return "PLANNED"
    return "PARTIAL"


def plan_patterns(root: Path, *, product_id: str, pattern_ids: list[str]) -> dict[str, Any]:
    root = root.resolve()
    contracts, registry_payload, registry_hash = load_runtime_registry(root)
    catalog, catalog_hash = load_capability_catalog(root)

    requested = list(dict.fromkeys(str(item) for item in pattern_ids))
    unknown = sorted(set(requested).difference(contracts))
    require(not unknown, f"unknown work-pattern contracts requested: {unknown}")

    plans: list[dict[str, Any]] = []
    for pattern_id in requested:
        contract = contracts[pattern_id]
        operation_plan: list[dict[str, Any]] = []
        for operation in contract.get("operations") or []:
            resolution = resolve_capability(operation, catalog, product_id)
            operation_plan.append(
                {
                    "operation_id": operation["operation_id"],
                    "capability_id": operation["capability_id"],
                    "required": True,
                    "execution_required": False,
                    "resolution_state": resolution["resolution_state"],
                    "provider": copy.deepcopy(resolution["provider"]),
                    "reason": resolution["reason"],
                }
            )
        state = _pattern_state(operation_plan)
        plans.append(
            {
                "work_pattern_id": pattern_id,
                "contract_id": contract["contract_id"],
                "contract_version": contract["contract_version"],
                "runtime_stage": contract["runtime_stage"],
                "runtime_state": state,
                "input_contract": copy.deepcopy(contract["input_contract"]),
                "output_contract": copy.deepcopy(contract["output_contract"]),
                "human_boundary": contract["human_boundary"],
                "human_gate": {
                    "state": "NEEDS_YOU",
                    "reason": contract["human_boundary"],
                },
                "operations": operation_plan,
            }
        )

    blocking = [item for item in plans if item["runtime_state"] in {"BLOCKED", "PARTIAL", "PLANNED", "DECLARED"}]
    plan_identity = {
        "product_id": product_id,
        "runtime_version": RUNTIME_VERSION,
        "runtime_registry_sha256": registry_hash,
        "capability_catalog_sha256": catalog_hash,
        "patterns": [
            {
                "work_pattern_id": item["work_pattern_id"],
                "contract_version": item["contract_version"],
                "runtime_state": item["runtime_state"],
                "operations": [
                    {
                        "operation_id": op["operation_id"],
                        "capability_id": op["capability_id"],
                        "resolution_state": op["resolution_state"],
                        "provider_id": (op.get("provider") or {}).get("provider_id"),
                    }
                    for op in item["operations"]
                ],
            }
            for item in plans
        ],
    }

    return {
        "schema": RUNTIME_SCHEMA,
        "runtime_version": RUNTIME_VERSION,
        "runtime_provenance": {
            "source_ref": RUNTIME_SOURCE_REF,
            "source_sha256": f"sha256:{sha256_file(root / RUNTIME_SOURCE_REF)}",
            "registry_ref": str(RUNTIME_REGISTRY_REF),
            "registry_sha256": registry_hash,
            "capability_catalog_sha256": catalog_hash,
        },
        "runtime_fingerprint": f"sha256:{sha256_json(plan_identity)}",
        "product_id": product_id,
        "planning_gate": {
            "state": "ALLOW" if not blocking else "NEEDS_IMPLEMENTATION",
            "reason": "All requested work-pattern operations are earned." if not blocking else "One or more requested work-pattern contracts contain planned, unavailable, unknown, or not-yet-bound operations.",
        },
        "execution_gate": {
            "state": "REFUSE",
            "reason": "Phase 3 Work Pattern Runtime is a non-executing capability planner and cannot create execution authority.",
        },
        "authority_created": False,
        "executor_created": False,
        "patterns": plans,
        "registry_laws": copy.deepcopy(registry_payload["laws"]),
    }


def plan_manifest(root: Path, manifest_path: Path) -> dict[str, Any]:
    root = root.resolve()
    compiled = compile_manifest(root, manifest_path)
    plan = plan_patterns(
        root,
        product_id=str(compiled["product_id"]),
        pattern_ids=[str(item["id"]) for item in compiled["work_patterns"]],
    )
    plan["composition_fingerprint"] = compiled["composition_fingerprint"]
    plan["compiler_execution_gate"] = copy.deepcopy(compiled["gates"]["execution"])
    require(plan["compiler_execution_gate"]["state"] == "REFUSE" or compiled["maturity"]["operational_flags"].get("executable") is True, "runtime may not relax compiler execution refusal")
    return plan


def inspect_summary(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "product_id": plan["product_id"],
        "runtime_fingerprint": plan["runtime_fingerprint"],
        "composition_fingerprint": plan.get("composition_fingerprint"),
        "planning_gate": plan["planning_gate"]["state"],
        "execution_gate": plan["execution_gate"]["state"],
        "compiler_execution_gate": (plan.get("compiler_execution_gate") or {}).get("state"),
        "authority_created": plan["authority_created"],
        "executor_created": plan["executor_created"],
        "patterns": [
            {
                "work_pattern_id": item["work_pattern_id"],
                "contract_id": item["contract_id"],
                "runtime_state": item["runtime_state"],
                "resolved_operations": [op["operation_id"] for op in item["operations"] if op["resolution_state"] == "RESOLVED"],
                "planned_operations": [op["operation_id"] for op in item["operations"] if op["resolution_state"] == "PLANNED"],
                "unavailable_operations": [op["operation_id"] for op in item["operations"] if op["resolution_state"] in {"UNAVAILABLE", "UNKNOWN"}],
                "human_boundary": item["human_boundary"],
            }
            for item in plan["patterns"]
        ],
    }


def render_summary(plan: dict[str, Any]) -> str:
    return json.dumps(inspect_summary(plan), indent=2, sort_keys=True)
