"""DIO M2 Commercial Metabolism.

M2 begins from a verified Metamorphic Spine M1 parent. Phase M2-0 freezes the
commercial constitution and harvests existing DIO organs. Phase M2-1 adds
immutable commercial context, lineage, observation and settlement contracts.
Phase M2-2 reuses LINGUA to project buyer-facing claims without laundering proof
gaps into commercial truth. Phase M2-3 separates channel capability, commercial
evidence and planning state from Seraph-owned external-effect authority. Phase
M2-4 compiles a complete market intention and observation contract while keeping
Market Command in local DRAFT/HELD planning state. Phase M2-5 exercises
source-bound controlled positive, negative and no-response observation paths
through Market Command and Sensorium without claiming real market validation.
Phase M2-6 binds customer identity, payment evidence and acceptance evidence as
distinct lineages and exercises the structural WTP gate without claiming real
WTP from controlled fixtures.
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
from .projection import (
    CommercialClaim,
    CommercialClaimState,
    CommercialProjection,
    CommercialProjectionError,
    DEFAULT_PROJECTION_CONFIG,
    M2_PHASE2_EXIT_TOKEN,
    build_commercial_projection,
    build_reference_commercial_context,
    evaluate_buyer_draft,
    phase2_projection_receipt,
)
from .authority import (
    AUTHORITY_SCHEMA_FILE,
    AuthorityDecision,
    CommercialAuthorityError,
    CommercialAuthorityPreflight,
    CommercialEffect,
    DEFAULT_AUTHORITY_CONFIG,
    EffectAuthorityDecision,
    M2_PHASE3_EXIT_TOKEN,
    build_reference_authority_preflight,
    evaluate_non_authority_influences,
    phase3_authority_receipt,
)
from .episode import (
    DEFAULT_EPISODE_CONFIG,
    EPISODE_SCHEMA_FILE,
    M2_PHASE4_EXIT_TOKEN,
    MarketEpisodeError,
    MarketEpisodePlan,
    compile_reference_market_episode,
    phase4_market_episode_receipt,
)
from .observation import (
    CommercialObservationEpisode,
    CommercialObservationError,
    DEFAULT_OBSERVATION_CONFIG,
    M2_PHASE5_EXIT_TOKEN,
    OBSERVATION_EPISODE_SCHEMA_FILE,
    exercise_controlled_observation_scenarios,
    phase5_market_observation_receipt,
)
from .lineage import (
    CommercialLineageError,
    CommercialLineageEvidence,
    DEFAULT_LINEAGE_CONFIG,
    LINEAGE_SCHEMA_FILE,
    M2_PHASE6_EXIT_TOKEN,
    exercise_controlled_lineage_scenarios,
    phase6_customer_payment_lineage_receipt,
)

__all__ = [
    "AUTHORITY_SCHEMA_FILE",
    "AuthorityDecision",
    "DEFAULT_AUTHORITY_CONFIG",
    "DEFAULT_CONFIG",
    "DEFAULT_EPISODE_CONFIG",
    "DEFAULT_LINEAGE_CONFIG",
    "DEFAULT_OBSERVATION_CONFIG",
    "DEFAULT_PROJECTION_CONFIG",
    "EPISODE_SCHEMA_FILE",
    "LINEAGE_SCHEMA_FILE",
    "OBSERVATION_EPISODE_SCHEMA_FILE",
    "M2_PHASE0_EXIT_TOKEN",
    "M2_PHASE1_EXIT_TOKEN",
    "M2_PHASE2_EXIT_TOKEN",
    "M2_PHASE3_EXIT_TOKEN",
    "M2_PHASE4_EXIT_TOKEN",
    "M2_PHASE5_EXIT_TOKEN",
    "M2_PHASE6_EXIT_TOKEN",
    "REQUIRED_ANCHOR_IDS",
    "REQUIRED_LAWS",
    "CommercialAuthorityError",
    "CommercialAuthorityPreflight",
    "CommercialClaim",
    "CommercialClaimState",
    "CommercialConstitutionError",
    "CommercialEffect",
    "CommercialLineageError",
    "CommercialLineageEvidence",
    "CommercialObservationEpisode",
    "CommercialObservationError",
    "CommercialProjection",
    "CommercialProjectionError",
    "ChannelAccessState",
    "ChannelState",
    "CommercialContext",
    "CommercialSettlement",
    "CommercialSettlementState",
    "CustomerIndependence",
    "CustomerLineage",
    "EffectAuthorityDecision",
    "EvidenceClaimState",
    "MarketEpisodeError",
    "MarketEpisodePlan",
    "MarketObservation",
    "MarketObservationKind",
    "OfferLifecycle",
    "OfferState",
    "PaymentLineage",
    "PaymentState",
    "PricingEvidenceState",
    "PricingHypothesisState",
    "SettlementOutcome",
    "build_commercial_projection",
    "build_reference_authority_preflight",
    "build_reference_commercial_context",
    "compile_reference_market_episode",
    "evaluate_buyer_draft",
    "evaluate_non_authority_influences",
    "exercise_controlled_lineage_scenarios",
    "exercise_controlled_observation_scenarios",
    "phase1_contract_receipt",
    "phase2_projection_receipt",
    "phase3_authority_receipt",
    "phase4_market_episode_receipt",
    "phase5_market_observation_receipt",
    "phase6_customer_payment_lineage_receipt",
    "validate_commercial_constitution",
]
