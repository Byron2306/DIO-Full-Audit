"""Phase 6 native execution for the DIO Metamorphic Spine.

The Phase 5 DAG is executed only through the already-proven Studio native
executor. Each node is rechecked against its immutable unit identity and current
world lease immediately before execution. Sensorium records an evidence-only
causal episode. Dependency order is enforced, but Phase 6 does not yet claim
content-level composite emergence, Harmonics, Seraph, ARDA, settlement or
crystallisation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
from typing import Any

from adapters.sensorium.metamorphic_episode import close_episode, create_runtime, observe
from products.studio_native_closure import close_studio_case, verify_native_closure_proof

from .contracts import digest_payload
from .registry import build_reference_registry
from .resolver import build_reference_intent, resolve_intent
from .world_lease import acquire_world_lease, build_controlled_world_snapshot, require_world_lease_current


PHASE6_EXIT_TOKEN = "DIO_METAMORPHIC_NATIVE_EXECUTION_READY"


class NativeExecutionError(RuntimeError):
    pass


def _node_map(resolution: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = resolution.get("composition", {}).get("nodes") or []
    result = {str(row.get("node_id")): row for row in rows if isinstance(row, dict)}
    if len(result) != len(rows):
        raise NativeExecutionError("composition node identities are invalid")
    return result


def _dependency_map(resolution: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    result: dict[str, list[str]] = {node_id: [] for node_id in _node_map(resolution)}
    for edge in resolution.get("composition", {}).get("edges") or []:
        source = str(edge.get("source_node") or "")
        target = str(edge.get("target_node") or "")
        if source not in result or target not in result:
            raise NativeExecutionError("composition dependency references missing node")
        result[target].append(source)
    return {key: tuple(sorted(value)) for key, value in result.items()}


def _check_time(now: datetime | None) -> datetime:
    return now if now is not None else datetime.now(timezone.utc)


def execute_resolution(
    repo_root: str | Path,
    *,
    resolution: dict[str, Any],
    world_lease: Any,
    live_snapshot: Any,
    output_dir: str | Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)

    composition = resolution.get("composition") or {}
    if resolution.get("native_execution_performed") is not False:
        raise NativeExecutionError("Phase 6 requires an unexecuted Phase 5 plan")
    if composition.get("composition_name") != "Funding Proposal Studio":
        raise NativeExecutionError("unexpected Phase 6 reference composition")

    registry = build_reference_registry(root)
    live_caps = tuple(unit.unit_digest for unit in registry.units())
    nodes = _node_map(resolution)
    dependencies = _dependency_map(resolution)
    order = tuple(composition.get("topological_order") or ())
    if set(order) != set(nodes) or len(order) != len(nodes):
        raise NativeExecutionError("composition topological order is incomplete")

    runtime = create_runtime(root, out_dir=output / "sensorium")
    mission_id = "metamorphic:" + str(composition["composition_digest"]).split(":", 1)[1][:24]
    event_ids = [
        observe(
            runtime,
            mission_id=mission_id,
            event_type="metamorphic.execution_started",
            payload={
                "composition_digest": composition["composition_digest"],
                "world_lease_digest": world_lease.lease_digest,
                "planned_node_order": list(order),
                "external_effects_authorized": False,
            },
        )
    ]

    completed: dict[str, dict[str, Any]] = {}
    try:
        for node_id in order:
            node = nodes[node_id]
            unit = registry.get(str(node["unit_id"]))
            if node.get("unit_digest") != unit.unit_digest:
                raise NativeExecutionError(f"unit identity drift before node execution: {node_id}")
            if node.get("executor_id") != unit.executor_id or node.get("executor_digest") != unit.executor_digest:
                raise NativeExecutionError(f"native executor identity drift before node execution: {node_id}")

            missing_dependencies = [dep for dep in dependencies[node_id] if dep not in completed]
            if missing_dependencies:
                raise NativeExecutionError(
                    f"node {node_id} attempted before dependencies completed: {missing_dependencies}"
                )

            try:
                validation = require_world_lease_current(
                    world_lease,
                    live_snapshot=live_snapshot,
                    live_capability_refs=live_caps,
                    live_authority_refs=tuple(world_lease.authority_refs),
                    now=_check_time(now),
                )
            except Exception as exc:
                raise NativeExecutionError(f"world lease invalid before node {node_id}: {exc}") from exc

            dependency_receipts = {
                dep: completed[dep]["native_closure_fingerprint"] for dep in dependencies[node_id]
            }
            event_ids.append(
                observe(
                    runtime,
                    mission_id=mission_id,
                    event_type="metamorphic.node_started",
                    payload={
                        "node_id": node_id,
                        "unit_id": unit.unit_id,
                        "unit_digest": unit.unit_digest,
                        "executor_id": unit.executor_id,
                        "executor_digest": unit.executor_digest,
                        "dependency_receipts": dependency_receipts,
                        "world_lease_rechecked": validation.valid,
                    },
                )
            )

            manifest_rel = str(unit.input_contract.get("source_manifest") or "")
            if not manifest_rel:
                raise NativeExecutionError(f"unit {unit.unit_id} has no source manifest")
            result = close_studio_case(
                manifest_path=root / manifest_rel,
                output_dir=output / "nodes" / node_id,
                root=root,
            )
            verify_native_closure_proof(Path(result["output_dir"]), result["proof_manifest"])
            receipt = result["receipt"]
            if receipt.get("native_capability_closure") != "PASS":
                raise NativeExecutionError(f"native node failed closure: {node_id}")
            if receipt.get("authority_created") is not False or receipt.get("external_effects") is not False:
                raise NativeExecutionError(f"native node widened authority/effects: {node_id}")
            if any(
                receipt.get(key) != "REFUSE"
                for key in ("external_publication", "external_send", "media_spend", "payment")
            ):
                raise NativeExecutionError(f"native node external-effect boundary changed: {node_id}")

            node_receipt = {
                "node_id": node_id,
                "unit_id": unit.unit_id,
                "unit_digest": unit.unit_digest,
                "executor_id": unit.executor_id,
                "executor_digest": unit.executor_digest,
                "dependencies": list(dependencies[node_id]),
                "dependency_receipts": dependency_receipts,
                "native_closure_fingerprint": receipt["native_closure_fingerprint"],
                "proof_fingerprint": receipt["proof_fingerprint"],
                "all_declared_capabilities_executed": receipt["all_declared_capabilities_executed"],
                "authority_created": receipt["authority_created"],
                "external_effects": receipt["external_effects"],
                "output_dir": str(Path(result["output_dir"]).relative_to(output)),
            }
            node_receipt["node_execution_digest"] = digest_payload(node_receipt)
            completed[node_id] = node_receipt
            event_ids.append(
                observe(
                    runtime,
                    mission_id=mission_id,
                    event_type="metamorphic.node_completed",
                    payload={
                        "node_id": node_id,
                        "unit_id": unit.unit_id,
                        "node_execution_digest": node_receipt["node_execution_digest"],
                        "native_closure_fingerprint": receipt["native_closure_fingerprint"],
                        "status": "PASS",
                    },
                )
            )
    except Exception as exc:
        event_ids.append(
            observe(
                runtime,
                mission_id=mission_id,
                event_type="metamorphic.execution_failed",
                payload={
                    "completed_nodes": list(completed),
                    "error_type": type(exc).__name__,
                    "error_message_retained": False,
                    "status": "FAILED",
                },
            )
        )
        raise

    effect_hash = digest_payload(
        {
            "composition_digest": composition["composition_digest"],
            "node_execution_digests": [completed[node_id]["node_execution_digest"] for node_id in order],
        }
    )
    event_ids.append(
        observe(
            runtime,
            mission_id=mission_id,
            event_type="metamorphic.execution_completed",
            payload={
                "composition_digest": composition["composition_digest"],
                "completed_nodes": list(order),
                "effect_hash": effect_hash,
                "external_effects": False,
            },
        )
    )
    episode = close_episode(
        runtime,
        mission_id=mission_id,
        objective_hash=composition["composition_digest"],
        initial_state_hash=world_lease.lease_digest,
        outcome={"status": "PASS", "effect_hash": effect_hash},
    )
    if episode.get("event_ids") != event_ids:
        raise NativeExecutionError("Sensorium episode event sequence diverged from admitted execution events")

    return {
        "schema": "dio.metamorphic.native_execution_receipt.v1",
        "composition_name": composition["composition_name"],
        "composition_digest": composition["composition_digest"],
        "world_lease_digest": world_lease.lease_digest,
        "topological_order": list(order),
        "dependency_order_enforced": True,
        "world_lease_rechecked_before_each_node": True,
        "content_transform_dataflow_proved": False,
        "node_receipts": [completed[node_id] for node_id in order],
        "node_count": len(completed),
        "all_native_nodes_passed": len(completed) == len(order),
        "same_unit_identity_preserved": True,
        "native_executors_only": True,
        "node_failures_visible": True,
        "sensorium_episode": episode,
        "sensorium_episode_complete": True,
        "sensorium_authority": episode["authority"],
        "external_effects": False,
        "authority_widened": False,
        "new_engine_created": False,
        "beast_crystallization_executed": False,
        "harmonics_executed": False,
        "seraph_egress_executed": False,
        "arda_execution_performed": False,
        "world_settlement_performed": False,
        "market_feedback_learning_executed": False,
        "effect_hash": effect_hash,
    }


def run_reference_native_execution(repo_root: str | Path, *, output_dir: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    plan_now = datetime.now(timezone.utc).replace(microsecond=0)
    intent, source_text, config = build_reference_intent(root)
    snapshot = build_controlled_world_snapshot(root, now=plan_now)
    lease = acquire_world_lease(root, snapshot=snapshot, composition_id=intent.intent_id)
    resolution = resolve_intent(
        root,
        intent=intent,
        live_buyer_job_text=source_text,
        world_lease=lease,
        live_snapshot=snapshot,
        now=plan_now,
        config=config,
    )
    return execute_resolution(
        root,
        resolution=resolution,
        world_lease=lease,
        live_snapshot=snapshot,
        output_dir=output_dir,
        now=None,
    )


def phase6_native_execution_receipt(repo_root: str | Path, *, output_dir: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    if output_dir is None:
        with tempfile.TemporaryDirectory(prefix="dio-metamorphic-phase6-") as temp:
            execution = run_reference_native_execution(root, output_dir=temp)
    else:
        execution = run_reference_native_execution(root, output_dir=output_dir)

    passed = (
        execution["composition_name"] == "Funding Proposal Studio"
        and execution["node_count"] == 3
        and execution["all_native_nodes_passed"] is True
        and execution["native_executors_only"] is True
        and execution["same_unit_identity_preserved"] is True
        and execution["sensorium_episode_complete"] is True
        and execution["sensorium_authority"] == "evidence_only"
        and execution["world_lease_rechecked_before_each_node"] is True
        and execution["external_effects"] is False
        and execution["authority_widened"] is False
        and execution["new_engine_created"] is False
        and execution["content_transform_dataflow_proved"] is False
        and all(
            execution[key] is False
            for key in (
                "beast_crystallization_executed",
                "harmonics_executed",
                "seraph_egress_executed",
                "arda_execution_performed",
                "world_settlement_performed",
                "market_feedback_learning_executed",
            )
        )
    )
    return {
        "phase": 6,
        "acceptance": PHASE6_EXIT_TOKEN if passed else "DIO_METAMORPHIC_NATIVE_EXECUTION_BLOCKED",
        "passed": passed,
        **execution,
    }
