from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any

from adapters.beast.metamorphic_learning import record_execution_learning_candidate
from adapters.harmonics.metamorphic_state import assess_execution_harmony

from .native_execution import run_reference_native_execution


PHASE7_EXIT_TOKEN = "DIO_METAMORPHIC_BEAST_HARMONICS_READY"


def phase7_learning_receipt(repo_root: str | Path, *, work_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo_root).resolve()

    def _run(base: Path) -> dict[str, Any]:
        execution = run_reference_native_execution(root, output_dir=base / "execution")
        learning = record_execution_learning_candidate(
            root,
            execution=execution,
            state_root=base / "beast_learning",
        )
        harmonic = assess_execution_harmony(root, execution)
        passed = (
            execution.get("all_native_nodes_passed") is True
            and execution.get("sensorium_episode_complete") is True
            and learning.get("learning_candidate_only") is True
            and learning.get("direct_learning_to_execution") is False
            and learning.get("beast_crystallization_executed") is False
            and learning.get("learning_used_as_authority") is False
            and learning.get("active_negative_capability_count") == 0
            and harmonic.get("harmonic_inference_executed") is True
            and harmonic.get("harmonic_state_is_authority") is False
            and harmonic.get("authority_created") is False
            and execution.get("authority_widened") is False
        )
        return {
            "phase": 7,
            "acceptance": PHASE7_EXIT_TOKEN if passed else "DIO_METAMORPHIC_BEAST_HARMONICS_BLOCKED",
            "passed": passed,
            "composition_name": execution.get("composition_name"),
            "composition_digest": execution.get("composition_digest"),
            "effect_hash": execution.get("effect_hash"),
            "sensorium_episode_hash": (execution.get("sensorium_episode") or {}).get("episode_hash"),
            "beast_learning_event_digest": learning.get("beast_learning_event_digest"),
            "beast_learning_event_count": learning.get("beast_learning_report", {}).get("event_count"),
            "learning_candidate_only": learning.get("learning_candidate_only"),
            "direct_learning_to_execution": learning.get("direct_learning_to_execution"),
            "beast_crystallization_executed": learning.get("beast_crystallization_executed"),
            "negative_capability_store_reused": True,
            "active_negative_capability_count": learning.get("active_negative_capability_count"),
            "harmonics_executed": harmonic.get("harmonic_inference_executed"),
            "harmonic_projection_kind": harmonic.get("projection_kind"),
            "live_cadence_scoring_claimed": harmonic.get("live_cadence_scoring_claimed"),
            "harmonic_mode": harmonic.get("mode_recommendation"),
            "harmonic_state": harmonic,
            "learning_used_as_authority": False,
            "authority_widened": False,
            "new_engine_created": False,
            "seraph_egress_executed": False,
            "arda_execution_performed": False,
            "world_settlement_performed": False,
            "market_feedback_learning_executed": False,
        }

    if work_root is not None:
        base = Path(work_root).resolve()
        base.mkdir(parents=True, exist_ok=True)
        return _run(base)
    with tempfile.TemporaryDirectory(prefix="dio-metamorphic-phase7-") as temp:
        return _run(Path(temp))
