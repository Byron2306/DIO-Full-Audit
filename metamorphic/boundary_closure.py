from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
from typing import Any, Iterable

from adapters.arda.metamorphic_execution import bind_arda_execution_evidence
from adapters.beast.metamorphic_learning import record_execution_learning_candidate
from adapters.harmonics.metamorphic_state import assess_execution_harmony
from adapters.seraph.metamorphic_egress import bind_seraph_egress
from adapters.vns.metamorphic_witness import build_vns_witness

from .contracts import LayerWitnessState
from .native_execution import execute_resolution
from .resolver import build_reference_intent, resolve_intent
from .world_lease import acquire_world_lease, build_controlled_world_snapshot


PHASE8_EXIT_TOKEN = "DIO_METAMORPHIC_BOUNDARY_CLOSURE_READY"
REQUIRED_PHASE8_WITNESSES = ("vns", "seraph", "arda")
_ACCEPTABLE_WITNESS_STATES = {
    LayerWitnessState.EXERCISED.value,
    LayerWitnessState.CORROBORATED.value,
    LayerWitnessState.ARMED.value,
    LayerWitnessState.NOT_APPLICABLE.value,
}


class MetamorphicBoundaryClosureError(RuntimeError):
    pass


def validate_required_witnesses(
    witnesses: Iterable[dict[str, Any]],
    *,
    required: Iterable[str] = REQUIRED_PHASE8_WITNESSES,
) -> dict[str, Any]:
    rows = tuple(witnesses)
    by_organ: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for row in rows:
        organ = str(row.get("organ") or "").strip()
        if not organ:
            continue
        if organ in by_organ:
            duplicates.append(organ)
        by_organ[organ] = row
    required_tuple = tuple(required)
    missing = [organ for organ in required_tuple if organ not in by_organ]
    failed = [
        organ
        for organ in required_tuple
        if organ in by_organ and str(by_organ[organ].get("state") or "") not in _ACCEPTABLE_WITNESS_STATES
    ]
    implicit = [
        organ
        for organ in required_tuple
        if organ in by_organ and by_organ[organ].get("explicit") is not True
    ]
    return {
        "valid": not missing and not failed and not duplicates and not implicit,
        "required": list(required_tuple),
        "missing": missing,
        "failed_or_silent": failed,
        "duplicates": sorted(set(duplicates)),
        "implicit": implicit,
        "states": {organ: by_organ.get(organ, {}).get("state", "MISSING") for organ in required_tuple},
    }


def _run_phase8(repo_root: Path, work_root: Path) -> dict[str, Any]:
    plan_now = datetime.now(timezone.utc).replace(microsecond=0)
    intent, source_text, config = build_reference_intent(repo_root)
    snapshot = build_controlled_world_snapshot(repo_root, now=plan_now)
    lease = acquire_world_lease(repo_root, snapshot=snapshot, composition_id=intent.intent_id)
    resolution = resolve_intent(
        repo_root,
        intent=intent,
        live_buyer_job_text=source_text,
        world_lease=lease,
        live_snapshot=snapshot,
        now=plan_now,
        config=config,
    )
    execution = execute_resolution(
        repo_root,
        resolution=resolution,
        world_lease=lease,
        live_snapshot=snapshot,
        output_dir=work_root / "execution",
        now=None,
    )
    learning = record_execution_learning_candidate(
        repo_root,
        execution=execution,
        state_root=work_root / "beast_learning",
    )
    harmonic = assess_execution_harmony(repo_root, execution)

    vns_witness = build_vns_witness(
        repo_root,
        execution=execution,
        external_network_effect_expected=False,
    )
    seraph_witness = bind_seraph_egress(
        repo_root,
        authority=resolution["authority"],
        world_lease_digest=lease.lease_digest,
        effect_hash=execution["effect_hash"],
    )
    arda_witness = bind_arda_execution_evidence(repo_root, execution=execution)
    witnesses = [vns_witness, seraph_witness, arda_witness]
    witness_validation = validate_required_witnesses(witnesses)

    passed = (
        execution.get("all_native_nodes_passed") is True
        and execution.get("sensorium_episode_complete") is True
        and learning.get("learning_candidate_only") is True
        and learning.get("direct_learning_to_execution") is False
        and learning.get("learning_used_as_authority") is False
        and learning.get("beast_crystallization_executed") is False
        and harmonic.get("harmonic_inference_executed") is True
        and harmonic.get("harmonic_state_is_authority") is False
        and vns_witness.get("state") == LayerWitnessState.NOT_APPLICABLE.value
        and vns_witness.get("external_network_effect_expected") is False
        and seraph_witness.get("state") == LayerWitnessState.ARMED.value
        and seraph_witness.get("seraph_egress_bound") is True
        and seraph_witness.get("verdict") == "REFUSE"
        and seraph_witness.get("operational_gate_action_executed") is False
        and arda_witness.get("state") == LayerWitnessState.ARMED.value
        and arda_witness.get("arda_execution_evidence_bound") is True
        and arda_witness.get("arda_bounded_replay_executed") is False
        and arda_witness.get("physical_transport_executed") is False
        and witness_validation["valid"] is True
        and resolution["authority"].get("authority_widened") is False
        and resolution["authority"].get("external_effects_authorized") is False
        and execution.get("external_effects") is False
    )

    return {
        "phase": 8,
        "acceptance": PHASE8_EXIT_TOKEN if passed else "DIO_METAMORPHIC_BOUNDARY_CLOSURE_BLOCKED",
        "passed": passed,
        "composition_name": execution.get("composition_name"),
        "composition_digest": execution.get("composition_digest"),
        "effect_hash": execution.get("effect_hash"),
        "world_lease_digest": lease.lease_digest,
        "sensorium_episode_hash": (execution.get("sensorium_episode") or {}).get("episode_hash"),
        "learning_candidate_only": learning.get("learning_candidate_only"),
        "direct_learning_to_execution": learning.get("direct_learning_to_execution"),
        "beast_crystallization_executed": learning.get("beast_crystallization_executed"),
        "harmonics_executed": harmonic.get("harmonic_inference_executed"),
        "harmonic_state_is_authority": harmonic.get("harmonic_state_is_authority"),
        "harmonic_mode": harmonic.get("mode_recommendation"),
        "vns_witness_explicit": vns_witness.get("explicit") is True,
        "vns_witness_state": vns_witness.get("state"),
        "seraph_egress_bound": seraph_witness.get("seraph_egress_bound"),
        "seraph_witness_state": seraph_witness.get("state"),
        "seraph_verdict": seraph_witness.get("verdict"),
        "seraph_operational_gate_executed": seraph_witness.get("operational_gate_action_executed"),
        "arda_execution_evidence_bound": arda_witness.get("arda_execution_evidence_bound"),
        "arda_witness_state": arda_witness.get("state"),
        "arda_bounded_replay_executed": arda_witness.get("arda_bounded_replay_executed"),
        "arda_physical_transport_executed": arda_witness.get("physical_transport_executed"),
        "required_witnesses_complete": witness_validation["valid"],
        "witness_validation": witness_validation,
        "witnesses": witnesses,
        "external_effects_authorized": False,
        "external_effects": False,
        "authority_widened": False,
        "learning_used_as_authority": False,
        "world_settlement_performed": False,
        "market_feedback_learning_executed": False,
        "new_engine_created": False,
    }


def phase8_boundary_closure_receipt(
    repo_root: str | Path,
    *,
    work_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    if work_root is not None:
        target = Path(work_root).resolve()
        target.mkdir(parents=True, exist_ok=True)
        return _run_phase8(root, target)
    with tempfile.TemporaryDirectory(prefix="dio-metamorphic-phase8-") as temp:
        return _run_phase8(root, Path(temp))
