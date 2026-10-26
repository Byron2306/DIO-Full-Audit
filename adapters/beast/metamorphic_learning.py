from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any


class MetamorphicLearningError(RuntimeError):
    pass


def load_beast_learning_classes(repo_root: str | Path):
    root = Path(repo_root).resolve()
    beast_root = root / "cross_folder_variants/EdgeK-BEAST/A_CODE"
    if not beast_root.is_dir():
        raise MetamorphicLearningError(f"BEAST root missing: {beast_root}")
    if str(beast_root) not in sys.path:
        sys.path.insert(0, str(beast_root))
    learning = importlib.import_module("app.kernel.compute.capability_learning")
    outcomes = importlib.import_module("app.kernel.storage.outcome_evidence")
    return learning.CapabilityLearningLedger, outcomes.NegativeCapabilityStore, outcomes.OutcomeEvidence


def record_execution_learning_candidate(
    repo_root: str | Path,
    *,
    execution: dict[str, Any],
    state_root: str | Path,
) -> dict[str, Any]:
    CapabilityLearningLedger, NegativeCapabilityStore, OutcomeEvidence = load_beast_learning_classes(repo_root)
    state = Path(state_root).resolve()
    state.mkdir(parents=True, exist_ok=True)
    ledger = CapabilityLearningLedger(state / "capability_learning.jsonl")
    negative = NegativeCapabilityStore(state / "negative_capabilities.json")

    episode = execution.get("sensorium_episode") or {}
    episode_hash = str(episode.get("episode_hash") or "")
    effect_hash = str(execution.get("effect_hash") or "")
    if not episode_hash.startswith("sha256:") or not effect_hash.startswith("sha256:"):
        raise MetamorphicLearningError("Phase 7 requires digest-bound Sensorium episode and effect")

    node_evidence = []
    for row in execution.get("node_receipts") or []:
        capability_id = str(row.get("unit_id") or "")
        evidence = OutcomeEvidence.create(
            capability_id=capability_id,
            task_class="metamorphic_node_execution",
            outcome="success",
            scope={
                "route": str(execution.get("composition_name") or ""),
                "tool": str(row.get("executor_id") or ""),
            },
            selected_capabilities=(capability_id,),
            confidence_after=1.0,
        )
        negative.record(evidence)
        node_evidence.append(evidence.to_dict())

    event = ledger.record(
        event_type="metamorphic_execution_observed",
        capability_type="metamorphic_composition",
        capability_id="composition:" + str(execution.get("composition_digest") or "").split(":", 1)[-1][:24],
        lifecycle_state="candidate_observed",
        authority="evidence_only",
        evidence_digest=episode_hash,
        receipt_digest=effect_hash,
        fresh_work_units=len(node_evidence),
        metadata={
            "composition_name": execution.get("composition_name"),
            "composition_digest": execution.get("composition_digest"),
            "world_lease_digest": execution.get("world_lease_digest"),
            "direct_learning_to_execution": False,
            "crystallization_status": "NOT_PERFORMED",
        },
    )
    report = ledger.report(limit=20)
    active = []
    for row in execution.get("node_receipts") or []:
        active.extend(
            negative.active_matches(
                {
                    "capability_id": row.get("unit_id"),
                    "task_class": "metamorphic_node_execution",
                    "scope": {
                        "route": execution.get("composition_name"),
                        "tool": row.get("executor_id"),
                    },
                }
            )
        )
    return {
        "beast_learning_event_digest": event.event_digest,
        "beast_learning_report": report,
        "node_outcome_evidence": node_evidence,
        "negative_capability_records": negative.list_records(),
        "active_negative_capability_count": len(active),
        "learning_candidate_only": True,
        "direct_learning_to_execution": False,
        "beast_crystallization_executed": False,
        "learning_used_as_authority": False,
        "authority_created": False,
    }
