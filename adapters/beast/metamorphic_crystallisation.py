from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

from metamorphic.contracts import SettlementState, require_digest
from metamorphic.settlement import SettlementResult


class MetamorphicCrystallisationError(RuntimeError):
    pass


def _load_beast_crystal_organs(repo_root: str | Path):
    root = Path(repo_root).resolve()
    beast_root = root / "cross_folder_variants/EdgeK-BEAST/A_CODE"
    if not beast_root.is_dir():
        raise MetamorphicCrystallisationError(f"BEAST root missing: {beast_root}")
    if str(beast_root) not in sys.path:
        sys.path.insert(0, str(beast_root))
    crystal_module = importlib.import_module("app.kernel.security.crystal_chain")
    learning_module = importlib.import_module("app.kernel.compute.capability_learning")
    return crystal_module.CrystalChainLedger, learning_module.CapabilityLearningLedger


def crystallize_settled_composition(
    repo_root: str | Path,
    *,
    settlement_result: SettlementResult,
    boundary_receipt: dict[str, Any],
    state_root: str | Path,
) -> dict[str, Any]:
    """Crystallize only a fully settled composition episode.

    The crystal is evidence-only. It can make a composition eligible for later
    reuse, but it cannot grant SEND/PUBLISH/SPEND/PAYMENT or general execution
    authority.
    """
    settlement = settlement_result.settlement
    if settlement.settlement_state is not SettlementState.SETTLED or not settlement_result.passed:
        raise MetamorphicCrystallisationError("world settlement must be SETTLED before crystallisation")
    if boundary_receipt.get("passed") is not True:
        raise MetamorphicCrystallisationError("boundary closure must pass before crystallisation")
    if boundary_receipt.get("required_witnesses_complete") is not True:
        raise MetamorphicCrystallisationError("required witnesses must be complete before crystallisation")
    if boundary_receipt.get("authority_widened") is not False:
        raise MetamorphicCrystallisationError("authority widening blocks crystallisation")
    if boundary_receipt.get("external_effects") is not False:
        raise MetamorphicCrystallisationError("unexpected external effects block crystallisation")

    composition_digest = str(boundary_receipt.get("composition_digest") or "")
    effect_hash = str(boundary_receipt.get("effect_hash") or "")
    for field_name, value in (
        ("composition_digest", composition_digest),
        ("effect_hash", effect_hash),
        ("settlement_digest", settlement.settlement_digest),
    ):
        try:
            require_digest(value, field_name=field_name)
        except ValueError as exc:
            raise MetamorphicCrystallisationError(str(exc)) from exc

    CrystalChainLedger, CapabilityLearningLedger = _load_beast_crystal_organs(repo_root)
    state = Path(state_root).resolve()
    state.mkdir(parents=True, exist_ok=True)
    chain = CrystalChainLedger(state / "crystal_chain.jsonl", node_id="dio-metamorphic-m1")

    payload = {
        "crystal_type": "metamorphic_composition",
        "composition_name": boundary_receipt.get("composition_name"),
        "composition_digest": composition_digest,
        "effect_hash": effect_hash,
        "settlement_digest": settlement.settlement_digest,
        "settlement_state": settlement.settlement_state.value,
        "pre_world_digest": settlement.pre_world_digest,
        "post_world_digest": settlement.post_world_digest,
        "authority_preserved": settlement.authority_preserved,
        "required_witnesses_complete": boundary_receipt.get("required_witnesses_complete"),
        "external_effects_authorized": False,
        "learning_used_as_authority": False,
        "content_transform_dataflow_proved": bool(boundary_receipt.get("content_transform_dataflow_proved", False)),
        "authority": "evidence_only",
    }
    block = chain.append(
        "metamorphic_composition_crystallized",
        "funding_proposal_studio",
        payload,
    )
    verification = chain.verify()
    if not verification.valid:
        raise MetamorphicCrystallisationError("BEAST crystal chain failed verification after append")

    learning = CapabilityLearningLedger(state / "capability_learning.jsonl")
    event = learning.record(
        event_type="metamorphic_composition_crystallized",
        capability_type="metamorphic_composition",
        capability_id="composition:" + composition_digest.split(":", 1)[1][:24],
        lifecycle_state="settled_crystal",
        authority="evidence_only",
        evidence_digest=settlement.settlement_digest,
        receipt_digest=block["block_hash"],
        metadata={
            "composition_name": boundary_receipt.get("composition_name"),
            "world_settlement_required": True,
            "world_settlement_state": settlement.settlement_state.value,
            "authority_preserved": settlement.authority_preserved,
            "direct_learning_to_execution": False,
        },
    )

    return {
        "schema": "dio.metamorphic.beast_crystal.v1",
        "beast_crystallization_executed": True,
        "world_settlement_required": True,
        "settlement_digest": settlement.settlement_digest,
        "crystal_type": "metamorphic_composition",
        "crystal_block_hash": block["block_hash"],
        "crystal_payload_hash": block["payload_hash"],
        "crystal_chain_valid": verification.valid,
        "crystal_chain_block_count": verification.block_count,
        "crystal_chain_head_hash": verification.head_hash,
        "beast_learning_event_digest": event.event_digest,
        "lifecycle_state": event.lifecycle_state,
        "authority": event.authority,
        "direct_learning_to_execution": False,
        "authority_created": False,
        "external_effects": False,
    }
