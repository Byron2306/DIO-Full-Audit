from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

from metamorphic.contracts import LayerWitnessState


SERAPH_ANCHOR = "cross_folder_variants/Metatron-triune-outbound-gate/A_CODE/backend/services/outbound_gate.py"
_EFFECT_KEYS = ("external_publication", "external_send", "media_spend", "payment")


class MetamorphicSeraphEgressError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def bind_seraph_egress(
    repo_root: str | Path,
    *,
    authority: Mapping[str, Any],
    world_lease_digest: str,
    effect_hash: str,
) -> dict[str, Any]:
    """Bind a controlled composition to Seraph's canonical egress boundary.

    This adapter is intentionally incapable of issuing ALLOW. Phase 8 has no
    external effect to perform, so the canonical operational gate remains ARMED
    while the metamorphic projection proves that every consequential effect is
    still REFUSE. The real OutboundGateService remains the authority owner.
    """
    root = Path(repo_root).resolve()
    anchor = root / SERAPH_ANCHOR
    if not anchor.is_file():
        raise MetamorphicSeraphEgressError(f"canonical Seraph anchor missing: {SERAPH_ANCHOR}")
    source = anchor.read_text(encoding="utf-8")
    required_markers = (
        "class OutboundGateService",
        "async def gate_action",
        "world_state_hash_drift",
        "from backend.services.vns import vns",
        "get_arda_fabric",
    )
    missing = [marker for marker in required_markers if marker not in source]
    if missing:
        raise MetamorphicSeraphEgressError(f"canonical Seraph contract markers missing: {missing}")
    if not str(world_lease_digest).startswith("sha256:") or not str(effect_hash).startswith("sha256:"):
        raise MetamorphicSeraphEgressError("Seraph binding requires world-lease and effect digests")

    decisions = dict(authority.get("effect_decisions") or {})
    boundary_clean = (
        authority.get("authority_widened") is False
        and authority.get("external_effects_authorized") is False
        and authority.get("learning_used_as_authority") is False
        and all(decisions.get(key) == "REFUSE" for key in _EFFECT_KEYS)
    )
    state = LayerWitnessState.ARMED if boundary_clean else LayerWitnessState.FAILED
    return {
        "schema": "dio.metamorphic.seraph_egress_binding.v1",
        "organ": "seraph",
        "state": state.value,
        "canonical_anchor": SERAPH_ANCHOR,
        "canonical_anchor_digest": _sha256_file(anchor),
        "world_lease_digest": world_lease_digest,
        "effect_hash": effect_hash,
        "effect_decisions": {key: decisions.get(key) for key in _EFFECT_KEYS},
        "verdict": "REFUSE",
        "seraph_egress_bound": boundary_clean,
        "canonical_operational_gate_armed": True,
        "operational_gate_action_executed": False,
        "adapter_can_issue_allow": False,
        "external_effects_authorized": False,
        "authority_created": False,
        "authority_widened": False if boundary_clean else True,
        "learning_used_as_authority": False if boundary_clean else bool(authority.get("learning_used_as_authority")),
        "explicit": True,
    }
