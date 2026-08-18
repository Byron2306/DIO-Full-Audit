"""Phase 0 canonical integration inventory for the DIO Metamorphic Spine.

This module deliberately contains no runtime organ implementation.  It records
which existing implementation owns each responsibility so later phases bridge
into proven code instead of growing duplicate semantic, world-state, sensing,
harmonic, egress, or execution authorities.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PHASE0_EXIT_TOKEN = "DIO_METAMORPHIC_M1_CONSTITUTION_FROZEN"


@dataclass(frozen=True, slots=True)
class IntegrationAnchor:
    organ: str
    responsibility: str
    path: str
    authority_note: str


CANONICAL_INTEGRATION_ANCHORS: tuple[IntegrationAnchor, ...] = (
    IntegrationAnchor(
        organ="lingua_beast",
        responsibility="source-bound semantic units, semantic review, BEAST learning bridge",
        path="docs/DIO_LINGUA_SHARED_ORGAN_AND_BEAST.md",
        authority_note="semantic learning does not mint execution authority",
    ),
    IntegrationAnchor(
        organ="beast_world_state",
        responsibility="deterministic signed/hash-chained world-state convergence",
        path="cross_folder_variants/EdgeK-BEAST/A_CODE/app/kernel/dai/world_state.py",
        authority_note="tested world is explicit and replayable, not self-authorising",
    ),
    IntegrationAnchor(
        organ="beast_sensorium",
        responsibility="read-only causal observation and runtime episode construction",
        path="cross_folder_variants/EdgeK-BEAST/A_CODE/app/kernel/sensorium/runtime.py",
        authority_note="observation remains distinct from execution authority",
    ),
    IntegrationAnchor(
        organ="metatron_world_model",
        responsibility="canonical operational world model and governance state",
        path="cross_folder_variants/Metatron-triune-outbound-gate/A_CODE/backend/services/world_model.py",
        authority_note="world-state authority remains canonical here, not in Metamorphic adapters",
    ),
    IntegrationAnchor(
        organ="metatron_world_manifold",
        responsibility="operational manifold fusion and signed world snapshot",
        path="cross_folder_variants/Metatron-triune-outbound-gate/A_CODE/backend/services/world_manifold.py",
        authority_note="manifold enriches deterministic reality state without replacing it",
    ),
    IntegrationAnchor(
        organ="vns",
        responsibility="independent network truth and reconciliation",
        path="cross_folder_variants/Metatron-triune-outbound-gate/A_CODE/backend/services/vns.py",
        authority_note="network corroboration is evidence, not business-effect authority",
    ),
    IntegrationAnchor(
        organ="harmonics",
        responsibility="behavioural coherence, drift, cadence, discord and obligations",
        path="cross_folder_variants/Metatron-triune-outbound-gate/A_CODE/backend/services/harmonic_engine.py",
        authority_note="harmonic state may tighten scrutiny but cannot mint authority",
    ),
    IntegrationAnchor(
        organ="seraph",
        responsibility="high-impact outbound gate and reality-bound egress",
        path="cross_folder_variants/Metatron-triune-outbound-gate/A_CODE/backend/services/outbound_gate.py",
        authority_note="all consequential external effects remain separately gated",
    ),
    IntegrationAnchor(
        organ="arda",
        responsibility="measured substrate/runtime execution truth",
        path="cross_folder_variants/Metatron-triune-outbound-gate/A_CODE/backend/services/arda_fabric.py",
        authority_note="measured execution truth does not grant semantic authority",
    ),
    IntegrationAnchor(
        organ="last_chord",
        responsibility="whole-stack witness-state and settlement doctrine",
        path="cross_folder_variants/Metatron-triune-outbound-gate/A_CODE/docs/THE_LAST_CHORD_PROTOCOL.md",
        authority_note="required witnesses must speak, corroborate, stand armed, or declare non-applicability",
    ),
)


CONSTITUTIONAL_INVARIANTS: tuple[str, ...] = (
    "anything_can_become_anything_except_authority",
    "harvest_existing_capabilities_before_new_engines",
    "buyer_language_does_not_replace_proof_truth",
    "world_state_w0_does_not_imply_world_state_w1",
    "no_outcome_crystal_before_world_settlement",
    "learning_never_mints_or_widens_authority",
    "native_executors_and_native_receipts_are_preserved",
    "required_witness_silence_is_failure",
    "m2_commercial_metabolism_is_required_destination",
)


def validate_integration_inventory(repo_root: str | Path) -> dict[str, object]:
    """Validate that Phase 0 points at existing canonical implementation anchors.

    This is intentionally a filesystem and ownership check only.  Later phases
    will test executable bridges.  Missing anchors fail closed because inventing
    a replacement during a later phase would violate the Phase 0 contract.
    """

    root = Path(repo_root).resolve()
    checked = []
    missing = []
    duplicates = []
    seen_paths: set[str] = set()

    for anchor in CANONICAL_INTEGRATION_ANCHORS:
        if anchor.path in seen_paths:
            duplicates.append(anchor.path)
        seen_paths.add(anchor.path)
        present = (root / anchor.path).is_file()
        checked.append(
            {
                "organ": anchor.organ,
                "path": anchor.path,
                "present": present,
                "responsibility": anchor.responsibility,
                "authority_note": anchor.authority_note,
            }
        )
        if not present:
            missing.append(anchor.path)

    passed = not missing and not duplicates and bool(CONSTITUTIONAL_INVARIANTS)
    return {
        "phase": 0,
        "acceptance": PHASE0_EXIT_TOKEN if passed else "DIO_METAMORPHIC_M1_CONSTITUTION_BLOCKED",
        "passed": passed,
        "anchor_count": len(CANONICAL_INTEGRATION_ANCHORS),
        "invariant_count": len(CONSTITUTIONAL_INVARIANTS),
        "missing": missing,
        "duplicate_paths": duplicates,
        "anchors": checked,
        "constitutional_invariants": list(CONSTITUTIONAL_INVARIANTS),
        "new_runtime_engines_created": False,
        "authority_widened": False,
        "m2_destination_declared": "m2_commercial_metabolism_is_required_destination" in CONSTITUTIONAL_INVARIANTS,
    }


def iter_anchor_paths() -> Iterable[str]:
    return (anchor.path for anchor in CANONICAL_INTEGRATION_ANCHORS)
