from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any


class MetamorphicHarmonicError(RuntimeError):
    pass


def load_harmonic_inference(repo_root: str | Path):
    root = Path(repo_root).resolve()
    metatron_root = root / "cross_folder_variants/Metatron-triune-outbound-gate/A_CODE"
    if not metatron_root.is_dir():
        raise MetamorphicHarmonicError(f"Metatron/Harmonics root missing: {metatron_root}")
    if str(metatron_root) not in sys.path:
        sys.path.insert(0, str(metatron_root))
    module = importlib.import_module("backend.services.harmonic_inference")
    return module.get_harmonic_inference_service()


def assess_execution_harmony(repo_root: str | Path, execution: dict[str, Any]) -> dict[str, Any]:
    episode = execution.get("sensorium_episode") or {}
    event_ids = list(episode.get("event_ids") or [])
    source_loss = episode.get("source_loss") or {}
    lost = sum(int(value or 0) for value in source_loss.values())
    complete = bool(
        execution.get("all_native_nodes_passed") is True
        and execution.get("sensorium_episode_complete") is True
        and len(event_ids) >= 1
    )
    expected_events = 2 + 2 * int(execution.get("node_count") or 0)
    completeness = min(1.0, len(event_ids) / max(1, expected_events))
    loss_pressure = min(1.0, lost / max(1, len(event_ids)))
    resonance = max(0.0, min(1.0, completeness * (1.0 - loss_pressure)))
    discord = max(0.0, min(1.0, (1.0 - completeness) + loss_pressure))
    confidence = max(0.0, min(1.0, completeness * (1.0 if complete else 0.5)))

    inference = load_harmonic_inference(repo_root)
    mode, rationale = inference.mode_recommendation(resonance, discord, confidence)
    return {
        "schema": "dio.metamorphic.harmonic_state.v1",
        "input_episode_hash": episode.get("episode_hash"),
        "input_effect_hash": execution.get("effect_hash"),
        "projection_kind": "sensorium_structural_projection",
        "live_cadence_scoring_claimed": False,
        "event_count": len(event_ids),
        "expected_event_count": expected_events,
        "source_loss_count": lost,
        "resonance_score": round(resonance, 6),
        "discord_score": round(discord, 6),
        "confidence": round(confidence, 6),
        "mode_recommendation": mode,
        "rationale": list(rationale),
        "harmonic_inference_executed": True,
        "harmonic_state_is_authority": False,
        "authority_created": False,
    }
