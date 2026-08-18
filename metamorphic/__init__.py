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
"""

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
]
