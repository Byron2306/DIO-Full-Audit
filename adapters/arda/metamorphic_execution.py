from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from metamorphic.contracts import LayerWitnessState


ARDA_EXECUTION_ANCHOR = "cross_folder_variants/EdgeK-BEAST/A_CODE/app/kernel/dai/arda_execution.py"


class MetamorphicARDAExecutionError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def bind_arda_execution_evidence(
    repo_root: str | Path,
    *,
    execution: dict[str, Any],
) -> dict[str, Any]:
    """Bind native composition evidence to ARDA's bounded execution contract.

    Phase 8 does not replay the composition through ARDA and does not ignite
    transport. Instead it proves that the observed native effect is ready to be
    consumed by the already-existing bounded ARDA/reverse-evidence contract.
    This is an ARMED witness, not a claim of ARDA physical execution.
    """
    root = Path(repo_root).resolve()
    anchor = root / ARDA_EXECUTION_ANCHOR
    if not anchor.is_file():
        raise MetamorphicARDAExecutionError(f"canonical ARDA execution anchor missing: {ARDA_EXECUTION_ANCHOR}")
    source = anchor.read_text(encoding="utf-8")
    required_markers = (
        "class ArdaSandboxExecutionReceipt",
        "def execute_arda_bounded_replay",
        "def verify_arda_reverse_evidence",
        "host_mutation_allowed: bool = False",
        "execution_authority_allowed: bool = False",
    )
    missing = [marker for marker in required_markers if marker not in source]
    if missing:
        raise MetamorphicARDAExecutionError(f"canonical ARDA execution markers missing: {missing}")

    episode = execution.get("sensorium_episode") or {}
    effect_hash = str(execution.get("effect_hash") or "")
    episode_hash = str(episode.get("episode_hash") or "")
    evidence_complete = (
        execution.get("all_native_nodes_passed") is True
        and execution.get("sensorium_episode_complete") is True
        and execution.get("authority_widened") is False
        and execution.get("external_effects") is False
        and effect_hash.startswith("sha256:")
        and episode_hash.startswith("sha256:")
    )
    state = LayerWitnessState.ARMED if evidence_complete else LayerWitnessState.MISSING
    return {
        "schema": "dio.metamorphic.arda_execution_binding.v1",
        "organ": "arda",
        "state": state.value,
        "canonical_anchor": ARDA_EXECUTION_ANCHOR,
        "canonical_anchor_digest": _sha256_file(anchor),
        "composition_digest": execution.get("composition_digest"),
        "effect_hash": effect_hash,
        "sensorium_episode_hash": episode_hash,
        "arda_execution_evidence_bound": evidence_complete,
        "bounded_replay_contract_available": True,
        "reverse_evidence_contract_available": True,
        "arda_bounded_replay_executed": False,
        "physical_transport_executed": False,
        "host_mutation_allowed": False,
        "general_execution_authority_allowed": False,
        "authority_created": False,
        "explicit": True,
    }
