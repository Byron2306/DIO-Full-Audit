from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from metamorphic.contracts import LayerWitnessState


VNS_ANCHOR = "cross_folder_variants/Metatron-triune-outbound-gate/A_CODE/backend/services/vns.py"


class MetamorphicVNSWitnessError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def build_vns_witness(
    repo_root: str | Path,
    *,
    execution: dict[str, Any],
    external_network_effect_expected: bool,
) -> dict[str, Any]:
    """Bind the composition episode to VNS without inventing network evidence.

    The Phase 8 reference organism is controlled-artifact-only. Therefore a
    network witness is explicitly NOT_APPLICABLE. If a caller says a network
    effect was expected, silence is not accepted and the witness becomes
    MISSING. VNS never grants authority in either case.
    """
    root = Path(repo_root).resolve()
    anchor = root / VNS_ANCHOR
    if not anchor.is_file():
        raise MetamorphicVNSWitnessError(f"canonical VNS anchor missing: {VNS_ANCHOR}")
    source = anchor.read_text(encoding="utf-8")
    required_markers = (
        "class VirtualNetworkSensor",
        "def record_flow",
        "def record_dns_query",
        "is_confirmed=False",
    )
    missing = [marker for marker in required_markers if marker not in source]
    if missing:
        raise MetamorphicVNSWitnessError(f"canonical VNS contract markers missing: {missing}")

    episode = execution.get("sensorium_episode") or {}
    episode_hash = str(episode.get("episode_hash") or "")
    effect_hash = str(execution.get("effect_hash") or "")
    if not episode_hash.startswith("sha256:") or not effect_hash.startswith("sha256:"):
        raise MetamorphicVNSWitnessError("VNS witness requires digest-bound Sensorium episode and effect")

    if external_network_effect_expected:
        state = LayerWitnessState.MISSING
        reason = "network effect expected but no independent VNS observation is bound"
    else:
        state = LayerWitnessState.NOT_APPLICABLE
        reason = "controlled artifact-only composition produced no external network effect to corroborate"

    return {
        "schema": "dio.metamorphic.vns_witness.v1",
        "organ": "vns",
        "state": state.value,
        "reason": reason,
        "canonical_anchor": VNS_ANCHOR,
        "canonical_anchor_digest": _sha256_file(anchor),
        "sensorium_episode_hash": episode_hash,
        "effect_hash": effect_hash,
        "external_network_effect_expected": bool(external_network_effect_expected),
        "network_effect_observed": False,
        "independent_network_truth_available": True,
        "vns_can_mint_authority": False,
        "authority_created": False,
        "explicit": True,
    }
