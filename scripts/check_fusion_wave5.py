#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
CORE_ROOT = HERE.parents[1]
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from executors.vertical import load_vertical_executor_registry


def _functions(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    return {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate DIO Fusion Wave 5 vertical executor readiness.")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--core", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    core = Path(args.core).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    blockers: list[dict[str, str]] = []

    wave4_path = workspace / "receipts" / "fusion-wave4-latest.json"
    try:
        wave4 = json.loads(wave4_path.read_text(encoding="utf-8"))
    except Exception as exc:
        blockers.append({"code": "FUSION_WAVE4_RECEIPT_INVALID", "message": str(exc)})
        wave4 = {}
    if wave4.get("state") != "FUSION_WAVE4_READY":
        blockers.append({"code": "FUSION_WAVE4_NOT_READY", "message": f"Observed state: {wave4.get('state')!r}"})

    required_files = [
        core / "executors" / "vertical.py",
        core / "config" / "dio_vertical_executors.json",
        core / "schemas" / "dio_vertical_executors.schema.json",
        core / "tests" / "test_vertical_executors.py",
    ]
    for path in required_files:
        if not path.is_file():
            blockers.append({"code": "WAVE5_FILE_MISSING", "message": str(path)})

    try:
        registry = load_vertical_executor_registry(core / "config" / "dio_vertical_executors.json")
    except Exception as exc:
        blockers.append({"code": "VERTICAL_EXECUTOR_REGISTRY_INVALID", "message": f"{type(exc).__name__}: {exc}"})
        registry = {"executors": [], "laws": {}}

    executor_ids: set[str] = set()
    capability_keys: set[tuple[str, str]] = set()
    bound = 0
    locked = 0
    external_bound = 0

    for executor in registry.get("executors") or []:
        executor_id = str(executor.get("executor_id") or "")
        if not executor_id or executor_id in executor_ids:
            blockers.append({"code": "EXECUTOR_ID_INVALID", "message": executor_id or "missing"})
            continue
        executor_ids.add(executor_id)

        for cap in executor.get("capabilities") or []:
            capability = str(cap.get("capability") or "")
            key = (executor_id, capability)
            if not capability or key in capability_keys:
                blockers.append({"code": "CAPABILITY_ID_INVALID", "message": f"{executor_id}/{capability or 'missing'}"})
                continue
            capability_keys.add(key)
            state = cap.get("binding_state")
            mode = cap.get("mode")
            entrypoint_kind = cap.get("entrypoint_kind")
            entrypoint_ref = cap.get("entrypoint_ref")

            if state == "bound":
                bound += 1
                if not isinstance(entrypoint_ref, str) or not entrypoint_ref:
                    blockers.append({"code": "BOUND_ENTRYPOINT_MISSING", "message": f"{executor_id}/{capability}"})
                    continue
                if mode == "hard_locked":
                    blockers.append({"code": "BOUND_CAPABILITY_HARD_LOCKED", "message": f"{executor_id}/{capability}"})
                if cap.get("external_side_effect") is True:
                    external_bound += 1
                    if mode != "explicit_environment_gate":
                        blockers.append({"code": "EXTERNAL_GATE_MISSING", "message": f"{executor_id}/{capability}"})

                if entrypoint_kind in {"core_callable", "core_cli"}:
                    path_text, _, symbol = entrypoint_ref.partition(":")
                    target = core / path_text
                    if not target.is_file():
                        blockers.append({"code": "BOUND_CORE_ENTRYPOINT_MISSING", "message": str(target)})
                    elif symbol and symbol not in _functions(target):
                        blockers.append({"code": "BOUND_CORE_SYMBOL_MISSING", "message": f"{target}:{symbol}"})
                elif entrypoint_kind == "workspace_mount":
                    target = workspace / entrypoint_ref
                    if not target.exists():
                        blockers.append({"code": "BOUND_WORKSPACE_ENTRYPOINT_MISSING", "message": str(target)})
                else:
                    blockers.append({"code": "BOUND_ENTRYPOINT_KIND_INVALID", "message": f"{executor_id}/{capability}: {entrypoint_kind}"})
            elif state == "locked":
                locked += 1
                if mode != "hard_locked" or entrypoint_kind != "none" or entrypoint_ref is not None:
                    blockers.append({"code": "LOCK_NOT_FAIL_CLOSED", "message": f"{executor_id}/{capability}"})
                if not cap.get("lock_reason"):
                    blockers.append({"code": "LOCK_REASON_MISSING", "message": f"{executor_id}/{capability}"})
            else:
                blockers.append({"code": "BINDING_STATE_INVALID", "message": f"{executor_id}/{capability}: {state!r}"})

    expected_executors = {
        "vesper_presence",
        "outlook_graph",
        "homs",
        "nichefoundry",
        "document_studio",
        "commerce_autorelease",
        "market_command",
        "phoenix",
    }
    if executor_ids != expected_executors:
        blockers.append({
            "code": "EXECUTOR_CENSUS_MISMATCH",
            "message": f"missing={sorted(expected_executors - executor_ids)} extra={sorted(executor_ids - expected_executors)}",
        })

    required_locks = {
        ("vesper_presence", "vesper_external_reply"),
        ("homs", "efundi_publish_marks"),
        ("nichefoundry", "nichefoundry_publish_campaign"),
        ("document_studio", "document_release_external"),
        ("commerce_autorelease", "fulfilment_release"),
        ("market_command", "campaign_release"),
        ("market_command", "campaign_spend"),
        ("phoenix", "phoenix_live_order"),
    }
    cap_map = {
        (executor["executor_id"], cap["capability"]): cap
        for executor in registry.get("executors") or []
        for cap in executor.get("capabilities") or []
    }
    for key in sorted(required_locks):
        if (cap_map.get(key) or {}).get("binding_state") != "locked":
            blockers.append({"code": "DANGEROUS_CAPABILITY_NOT_LOCKED", "message": f"{key[0]}/{key[1]}"})

    if bound != 8:
        blockers.append({"code": "BOUND_CAPABILITY_COUNT_DRIFT", "message": f"Expected 8, observed {bound}."})
    if locked != 8:
        blockers.append({"code": "LOCKED_CAPABILITY_COUNT_DRIFT", "message": f"Expected 8, observed {locked}."})

    state = "FUSION_WAVE5_READY" if not blockers else "BLOCKED"
    receipt = {
        "schema": "dio.fusion.wave5.receipt.v1",
        "state": state,
        "previous_receipt_state": wave4.get("state"),
        "executors": len(executor_ids),
        "bound_capabilities": bound,
        "locked_capabilities": locked,
        "external_bound_capabilities": external_bound,
        "automatic_external_actions": 0,
        "blockers": blockers,
        "receipt": str(out),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if state == "FUSION_WAVE5_READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
