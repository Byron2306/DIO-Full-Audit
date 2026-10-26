from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

from metamorphic.contracts import SettlementState, require_digest


class CommercialCrystallisationError(RuntimeError):
    pass


def _load_beast_crystal_organs(repo_root: str | Path):
    root = Path(repo_root).resolve()
    beast_root = root / "cross_folder_variants/EdgeK-BEAST/A_CODE"
    if not beast_root.is_dir():
        raise CommercialCrystallisationError(f"BEAST root missing: {beast_root}")
    if str(beast_root) not in sys.path:
        sys.path.insert(0, str(beast_root))
    crystal_module = importlib.import_module("app.kernel.security.crystal_chain")
    learning_module = importlib.import_module("app.kernel.compute.capability_learning")
    return crystal_module.CrystalChainLedger, learning_module.CapabilityLearningLedger


def crystallize_commercial_settlement(
    repo_root: str | Path,
    *,
    commercial_settlement: Any,
    world_settlement: Any,
    scenario_id: str,
    lineage_truth_digest: str,
    structural_wtp_gate_satisfied: bool,
    state_root: str | Path,
) -> dict[str, Any]:
    """Append one evidence-only market crystal after full commercial settlement.

    Commercial contract imports are intentionally resolved inside the call. This
    keeps the BEAST adapter importable independently without creating a package
    cycle through commercial_metabolism.__init__.

    M2-7 uses controlled fixtures. A crystal records the settled evidence shape; it
    does not turn fixture evidence into real market truth, WTP, validation,
    repeatability, execution authority, release authority or spend authority.
    """
    from commercial_metabolism.contracts import CommercialSettlementState

    if commercial_settlement.settlement_state is not CommercialSettlementState.SETTLED:
        raise CommercialCrystallisationError("commercial settlement must be SETTLED before crystallisation")
    if not commercial_settlement.market_crystal_eligible:
        raise CommercialCrystallisationError("commercial settlement is not market-crystal eligible")
    if world_settlement.settlement_state is not SettlementState.SETTLED:
        raise CommercialCrystallisationError("world settlement must be SETTLED before commercial crystallisation")
    if commercial_settlement.world_settlement_digest != world_settlement.settlement_digest:
        raise CommercialCrystallisationError("commercial settlement is not bound to the supplied world settlement")
    if not commercial_settlement.authority_preserved or commercial_settlement.authority_created:
        raise CommercialCrystallisationError("authority boundary blocks commercial crystallisation")
    for field_name, value in (
        ("commercial_settlement_digest", commercial_settlement.settlement_digest),
        ("world_settlement_digest", world_settlement.settlement_digest),
        ("lineage_truth_digest", lineage_truth_digest),
    ):
        try:
            require_digest(value, field_name=field_name)
        except ValueError as exc:
            raise CommercialCrystallisationError(str(exc)) from exc
    if not str(scenario_id or "").strip():
        raise CommercialCrystallisationError("scenario_id is required")

    CrystalChainLedger, CapabilityLearningLedger = _load_beast_crystal_organs(repo_root)
    state = Path(state_root).resolve()
    state.mkdir(parents=True, exist_ok=True)
    chain = CrystalChainLedger(state / "commercial_crystal_chain.jsonl", node_id="dio-metamorphic-m2")

    payload = {
        "crystal_type": "market_evidence",
        "evidence_scope": "controlled_fixture",
        "scenario_id": scenario_id,
        "context_digest": commercial_settlement.context_digest,
        "commercial_settlement_digest": commercial_settlement.settlement_digest,
        "world_settlement_digest": world_settlement.settlement_digest,
        "settlement_outcome": commercial_settlement.outcome.value,
        "market_observation_digests": list(commercial_settlement.market_observation_digests),
        "customer_lineage_digest": commercial_settlement.customer_lineage_digest,
        "payment_lineage_digest": commercial_settlement.payment_lineage_digest,
        "lineage_truth_digest": lineage_truth_digest,
        "structural_wtp_gate_satisfied": bool(structural_wtp_gate_satisfied),
        "real_market_evidence": False,
        "verified_payment_proved": False,
        "customer_acceptance_proved": False,
        "willingness_to_pay_proved": False,
        "commercial_validation_proved": False,
        "repeatability_proved": False,
        "authority_preserved": True,
        "authority": "evidence_only",
        "direct_learning_to_execution": False,
        "external_effects": False,
    }
    block = chain.append(
        "commercial_market_evidence_crystallized",
        f"funding_proposal_studio:{scenario_id}",
        payload,
    )
    verification = chain.verify()
    if not verification.valid:
        raise CommercialCrystallisationError("BEAST commercial crystal chain failed verification after append")

    learning = CapabilityLearningLedger(state / "commercial_capability_learning.jsonl")
    event = learning.record(
        event_type="commercial_market_evidence_crystallized",
        capability_type="commercial_market_evidence",
        capability_id=f"market:{scenario_id}",
        lifecycle_state="settled_market_crystal",
        authority="evidence_only",
        evidence_digest=commercial_settlement.settlement_digest,
        receipt_digest=block["block_hash"],
        metadata={
            "evidence_scope": "controlled_fixture",
            "world_settlement_required": True,
            "commercial_settlement_required": True,
            "real_market_evidence": False,
            "structural_wtp_gate_satisfied": bool(structural_wtp_gate_satisfied),
            "direct_learning_to_execution": False,
            "authority_preserved": True,
        },
    )

    return {
        "schema": "dio.m2.beast_market_crystal.v1",
        "beast_market_crystallization_executed": True,
        "crystal_type": "market_evidence",
        "evidence_scope": "controlled_fixture",
        "scenario_id": scenario_id,
        "commercial_settlement_required": True,
        "world_settlement_required": True,
        "commercial_settlement_digest": commercial_settlement.settlement_digest,
        "world_settlement_digest": world_settlement.settlement_digest,
        "lineage_truth_digest": lineage_truth_digest,
        "crystal_block_hash": block["block_hash"],
        "crystal_payload_hash": block["payload_hash"],
        "crystal_chain_valid": verification.valid,
        "crystal_chain_block_count": verification.block_count,
        "crystal_chain_head_hash": verification.head_hash,
        "beast_learning_event_digest": event.event_digest,
        "lifecycle_state": event.lifecycle_state,
        "authority": event.authority,
        "direct_learning_to_execution": False,
        "real_market_evidence": False,
        "willingness_to_pay_proved": False,
        "commercial_validation_proved": False,
        "repeatability_proved": False,
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
    }


__all__ = [
    "CommercialCrystallisationError",
    "crystallize_commercial_settlement",
]
