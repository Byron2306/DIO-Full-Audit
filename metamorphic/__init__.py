"""DIO Metamorphic Spine.

Phase 0 freezes ownership boundaries before runtime composition is introduced.
Phase 1 defines immutable metamorphic, world-lease, settlement, and witness
contracts without reimplementing any organ's runtime authority.
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
]
