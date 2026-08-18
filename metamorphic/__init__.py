"""DIO Metamorphic Spine.

Phase 0 freezes ownership boundaries before runtime composition is introduced.
Phase 1 defines immutable metamorphic, world-lease, settlement, and witness
contracts without reimplementing any organ's runtime authority.
Phase 2 proves that one immutable unit may be viewed as a product or capability
without changing identity, executor, evidence contract, quality contract, or
authority ceiling.
Phase 3 binds LINGUA semantic law to those same units: denotation, affordance,
prohibition and context projection, with learning candidate-only and no direct
learning-to-execution path.
Phase 4 reuses BEAST DAI's canonical WorldStateSnapshot and binds short-lived
metamorphic world leases to exact reality, epoch, policy, capability, and
authority references without replacing the operational Metatron manifold.
Phase 5 resolves source-bound LINGUA intent into existing governed capabilities,
intersects authority, and builds a deterministic composition DAG without
executing the selected native units.
Phase 6 executes that DAG through the existing Studio native executor, rechecks
the world lease at each node, preserves node receipts, and records an evidence-
only BEAST Sensorium runtime episode without claiming later-phase learning,
egress, ARDA execution or world settlement.
Phase 7 records that closed Sensorium outcome into BEAST capability learning and
negative-capability organs, binds Harmonics inference, and keeps all learning
candidate-only with no direct learning-to-execution or authority path.
Phase 8 closes the VNS, Seraph, and ARDA boundaries with explicit Last-Chord
witness states. No network evidence is invented, Seraph remains the egress
authority owner, and ARDA is bound as an armed bounded-execution/reverse-evidence
contract without claiming physical transport or general execution authority.
"""

import importlib

from .integration_inventory import (
    CANONICAL_INTEGRATION_ANCHORS,
    PHASE0_EXIT_TOKEN,
    validate_integration_inventory,
)
from .contracts import (
    LayerWitnessState,
    MetamorphicRole,
    MetamorphicUnit,
    PHASE1_EXIT_TOKEN,
    SettlementState,
    WorldLease,
    WorldSettlement,
    phase1_contract_receipt,
)
from .registry import (
    PHASE2_EXIT_TOKEN,
    MetamorphicRegistry,
    MetamorphicRegistryError,
    build_reference_registry,
    phase2_identity_receipt,
)
from .semantic_law import (
    PHASE3_EXIT_TOKEN,
    SemanticLaw,
    SemanticLawError,
    build_reference_semantic_laws,
    build_semantic_law,
    evaluate_claim,
    phase3_semantic_receipt,
    project_semantics,
)
from .world_lease import (
    PHASE4_EXIT_TOKEN,
    WorldLeaseBindingError,
    WorldLeaseValidation,
    acquire_world_lease,
    build_controlled_world_snapshot,
    phase4_world_lease_receipt,
    require_world_lease_current,
    validate_world_lease,
    world_anchor_digests,
)
from .authority import (
    AuthorityIntersection,
    AuthorityIntersectionError,
    intersect_authority,
)
from .composition import (
    CompositionDAG,
    CompositionEdge,
    CompositionError,
    ResolvedNode,
    build_composition_dag,
)
from .resolver import (
    PHASE5_EXIT_TOKEN,
    LinguaIntent,
    LinguaOutcome,
    ResolverError,
    build_reference_intent,
    phase5_resolver_receipt,
    resolve_intent,
)
from .native_execution import (
    PHASE6_EXIT_TOKEN,
    NativeExecutionError,
    execute_resolution,
    phase6_native_execution_receipt,
    run_reference_native_execution,
)
from .learning import (
    PHASE7_EXIT_TOKEN,
    phase7_learning_receipt,
)

# Phase 8 is deliberately lazy-loaded. Its boundary module imports the ARDA,
# Seraph, and VNS adapters, while those adapters import metamorphic.contracts.
# Eagerly importing boundary_closure here would therefore make an adapter-first
# import recurse through this package and observe a partially initialized module.
_PHASE8_EXPORTS = {
    "PHASE8_EXIT_TOKEN",
    "REQUIRED_PHASE8_WITNESSES",
    "MetamorphicBoundaryClosureError",
    "phase8_boundary_closure_receipt",
    "validate_required_witnesses",
}


def __getattr__(name: str):
    if name in _PHASE8_EXPORTS:
        module = importlib.import_module(".boundary_closure", __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CANONICAL_INTEGRATION_ANCHORS",
    "PHASE0_EXIT_TOKEN",
    "validate_integration_inventory",
    "LayerWitnessState",
    "MetamorphicRole",
    "MetamorphicUnit",
    "PHASE1_EXIT_TOKEN",
    "SettlementState",
    "WorldLease",
    "WorldSettlement",
    "phase1_contract_receipt",
    "PHASE2_EXIT_TOKEN",
    "MetamorphicRegistry",
    "MetamorphicRegistryError",
    "build_reference_registry",
    "phase2_identity_receipt",
    "PHASE3_EXIT_TOKEN",
    "SemanticLaw",
    "SemanticLawError",
    "build_reference_semantic_laws",
    "build_semantic_law",
    "evaluate_claim",
    "phase3_semantic_receipt",
    "project_semantics",
    "PHASE4_EXIT_TOKEN",
    "WorldLeaseBindingError",
    "WorldLeaseValidation",
    "acquire_world_lease",
    "build_controlled_world_snapshot",
    "phase4_world_lease_receipt",
    "require_world_lease_current",
    "validate_world_lease",
    "world_anchor_digests",
    "AuthorityIntersection",
    "AuthorityIntersectionError",
    "intersect_authority",
    "CompositionDAG",
    "CompositionEdge",
    "CompositionError",
    "ResolvedNode",
    "build_composition_dag",
    "PHASE5_EXIT_TOKEN",
    "LinguaIntent",
    "LinguaOutcome",
    "ResolverError",
    "build_reference_intent",
    "phase5_resolver_receipt",
    "resolve_intent",
    "PHASE6_EXIT_TOKEN",
    "NativeExecutionError",
    "execute_resolution",
    "phase6_native_execution_receipt",
    "run_reference_native_execution",
    "PHASE7_EXIT_TOKEN",
    "phase7_learning_receipt",
    "PHASE8_EXIT_TOKEN",
    "REQUIRED_PHASE8_WITNESSES",
    "MetamorphicBoundaryClosureError",
    "phase8_boundary_closure_receipt",
    "validate_required_witnesses",
]
