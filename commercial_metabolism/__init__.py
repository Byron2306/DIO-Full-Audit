"""DIO M2 Commercial Metabolism.

M2 begins from a verified Metamorphic Spine M1 parent. Phase M2-0 freezes the
commercial constitution and harvests existing DIO organs. Phase M2-1 adds
immutable commercial context, lineage, observation and settlement contracts
without introducing a competing runtime or widening authority.
"""

from .constitution import (
    DEFAULT_CONFIG,
    M2_PHASE0_EXIT_TOKEN,
    REQUIRED_ANCHOR_IDS,
    REQUIRED_LAWS,
    CommercialConstitutionError,
    validate_commercial_constitution,
)
from .contracts import (
    ChannelAccessState,
    ChannelState,
    CommercialContext,
    CommercialSettlement,
    CommercialSettlementState,
    CustomerIndependence,
    CustomerLineage,
    EvidenceClaimState,
    M2_PHASE1_EXIT_TOKEN,
    MarketObservation,
    MarketObservationKind,
    OfferLifecycle,
    OfferState,
    PaymentLineage,
    PaymentState,
    PricingEvidenceState,
    PricingHypothesisState,
    SettlementOutcome,
    phase1_contract_receipt,
)

__all__ = [
    "DEFAULT_CONFIG",
    "M2_PHASE0_EXIT_TOKEN",
    "M2_PHASE1_EXIT_TOKEN",
    "REQUIRED_ANCHOR_IDS",
    "REQUIRED_LAWS",
    "CommercialConstitutionError",
    "ChannelAccessState",
    "ChannelState",
    "CommercialContext",
    "CommercialSettlement",
    "CommercialSettlementState",
    "CustomerIndependence",
    "CustomerLineage",
    "EvidenceClaimState",
    "MarketObservation",
    "MarketObservationKind",
    "OfferLifecycle",
    "OfferState",
    "PaymentLineage",
    "PaymentState",
    "PricingEvidenceState",
    "PricingHypothesisState",
    "SettlementOutcome",
    "phase1_contract_receipt",
    "validate_commercial_constitution",
]
