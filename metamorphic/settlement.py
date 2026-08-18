from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .contracts import (
    SettlementState,
    WorldSettlement,
    digest_payload,
    require_digest,
)
from .world_lease import build_controlled_world_snapshot


class MetamorphicSettlementError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SettlementResult:
    settlement: WorldSettlement
    gates: Mapping[str, bool]
    red_gates: tuple[str, ...]
    post_world_facts_digest: str

    @property
    def passed(self) -> bool:
        return self.settlement.settlement_state is SettlementState.SETTLED and not self.red_gates

    def to_dict(self) -> dict[str, Any]:
        return {
            "settlement": self.settlement.to_dict(),
            "gates": dict(self.gates),
            "red_gates": list(self.red_gates),
            "post_world_facts_digest": self.post_world_facts_digest,
            "passed": self.passed,
        }


def _witness_digest(boundary_receipt: Mapping[str, Any], organ: str) -> str:
    for row in boundary_receipt.get("witnesses") or []:
        if isinstance(row, Mapping) and row.get("organ") == organ:
            return digest_payload(dict(row))
    return digest_payload({"organ": organ, "state": "MISSING"})


def settle_boundary_episode(
    repo_root: str | Path,
    *,
    boundary_receipt: Mapping[str, Any],
    now: datetime | None = None,
) -> SettlementResult:
    """Settle one closed metamorphic episode against a fresh tested-world observation.

    Settlement records what happened. It does not grant external-effect authority.
    A later crystal may be created only when this result is fully SETTLED.
    """
    root = Path(repo_root).resolve()
    settle_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)

    pre_world_digest = str(boundary_receipt.get("pre_world_digest") or "")
    effect_hash = str(boundary_receipt.get("effect_hash") or "")
    episode_hash = str(boundary_receipt.get("sensorium_episode_hash") or "")
    for name, value in (
        ("pre_world_digest", pre_world_digest),
        ("effect_hash", effect_hash),
        ("sensorium_episode_hash", episode_hash),
    ):
        try:
            require_digest(value, field_name=name)
        except ValueError as exc:
            raise MetamorphicSettlementError(str(exc)) from exc

    post_snapshot = build_controlled_world_snapshot(root, now=settle_now)
    post_facts_digest = digest_payload(post_snapshot.facts)
    pre_facts_digest = str(boundary_receipt.get("world_facts_digest") or "")

    gates = {
        "boundary_closure_passed": boundary_receipt.get("passed") is True,
        "required_witnesses_complete": boundary_receipt.get("required_witnesses_complete") is True,
        "native_execution_complete": boundary_receipt.get("all_native_nodes_passed") is True,
        "node_receipts_complete": boundary_receipt.get("node_receipts_complete") is True,
        "lineage_preserved": boundary_receipt.get("same_unit_identity_preserved") is True,
        "quality_contracts_preserved": boundary_receipt.get("quality_contracts_preserved") is True,
        "authority_preserved": boundary_receipt.get("authority_widened") is False,
        "learning_not_authority": boundary_receipt.get("learning_used_as_authority") is False,
        "external_effects_not_authorized": boundary_receipt.get("external_effects_authorized") is False,
        "external_effects_not_observed": boundary_receipt.get("external_effects") is False,
        "world_facts_stable": pre_facts_digest == post_facts_digest,
        "epoch_stable": boundary_receipt.get("world_epoch_id") == post_snapshot.epoch_id,
        "policy_generation_stable": boundary_receipt.get("world_policy_generation") == post_snapshot.policy_generation,
        "post_world_current": bool(post_snapshot.is_current(now=settle_now)),
    }
    red_gates = tuple(name for name, passed in gates.items() if not passed)

    unexpected: list[str] = []
    if not gates["required_witnesses_complete"]:
        unexpected.append("required_witness_closure_failed")
    if not gates["authority_preserved"]:
        unexpected.append("authority_widened")
    if not gates["external_effects_not_authorized"]:
        unexpected.append("external_effect_authorized")
    if not gates["external_effects_not_observed"]:
        unexpected.append("external_effect_observed")
    if not gates["world_facts_stable"]:
        unexpected.append("world_facts_drift")
    if not gates["epoch_stable"]:
        unexpected.append("epoch_drift")
    if not gates["policy_generation_stable"]:
        unexpected.append("policy_generation_drift")
    if not gates["native_execution_complete"] or not gates["node_receipts_complete"]:
        unexpected.append("native_execution_incomplete")

    if not gates["boundary_closure_passed"]:
        state = SettlementState.REFUSED
    elif red_gates:
        state = SettlementState.FRACTURED
    else:
        state = SettlementState.SETTLED

    expected_effects = ("controlled_artifact_execution",)
    observed_effects = (
        ("controlled_artifact_execution",)
        if gates["native_execution_complete"] and gates["node_receipts_complete"]
        else ()
    )

    settlement_id = "settlement:" + digest_payload(
        {
            "composition_digest": boundary_receipt.get("composition_digest"),
            "episode_hash": episode_hash,
            "effect_hash": effect_hash,
            "pre_world_digest": pre_world_digest,
            "post_world_digest": post_snapshot.snapshot_digest,
        }
    ).split(":", 1)[1][:24]

    settlement = WorldSettlement(
        settlement_id=settlement_id,
        episode_id="episode:" + episode_hash.split(":", 1)[1][:24],
        pre_world_digest=pre_world_digest,
        post_world_digest=post_snapshot.snapshot_digest,
        expected_effects=expected_effects,
        observed_effects=observed_effects,
        sensorium_receipts=(episode_hash,),
        vns_receipts=(_witness_digest(boundary_receipt, "vns"),),
        arda_receipts=(_witness_digest(boundary_receipt, "arda"),),
        seraph_receipts=(_witness_digest(boundary_receipt, "seraph"),),
        harmonic_before={
            "status": "not_observed_pre_execution_in_phase8",
            "authority": False,
        },
        harmonic_after={
            "status": "observed_after_execution",
            "mode": boundary_receipt.get("harmonic_mode"),
            "authority": bool(boundary_receipt.get("harmonic_state_is_authority")),
        },
        authority_preserved=gates["authority_preserved"],
        unexpected_effects=tuple(unexpected),
        settlement_state=state,
    )
    return SettlementResult(
        settlement=settlement,
        gates=gates,
        red_gates=red_gates,
        post_world_facts_digest=post_facts_digest,
    )
