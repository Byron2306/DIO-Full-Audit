"""Immutable M2 commercial contracts over harvested DIO commercial substrate.

These objects bind commercial meaning, lineage, observation and settlement. They
create no campaign, payment, publication, spend, delivery or authority. Existing
DIO organs remain the owners of execution and evidence described by M2-0.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any

from metamorphic.contracts import digest_payload, parse_datetime, require_digest
from commercial_metabolism.constitution import M2_PHASE0_EXIT_TOKEN, validate_commercial_constitution


M2_PHASE1_EXIT_TOKEN = "DIO_M2_COMMERCIAL_CONTRACTS_READY"


class OfferLifecycle(str, Enum):
    DRAFT = "DRAFT"
    HELD = "HELD"
    ELIGIBLE = "ELIGIBLE"
    RELEASED = "RELEASED"
    WITHDRAWN = "WITHDRAWN"


class ChannelAccessState(str, Enum):
    READ_ONLY = "READ_ONLY"
    DRAFT_ONLY = "DRAFT_ONLY"
    RELEASE_ELIGIBLE = "RELEASE_ELIGIBLE"
    RELEASED = "RELEASED"
    BLOCKED = "BLOCKED"


class PricingEvidenceState(str, Enum):
    UNTESTED = "UNTESTED"
    EXPOSED = "EXPOSED"
    OBSERVING = "OBSERVING"
    SUPPORTED = "SUPPORTED"
    WEAKENED = "WEAKENED"
    REFUTED = "REFUTED"


class CustomerIndependence(str, Enum):
    UNKNOWN = "UNKNOWN"
    OPERATOR_SELF = "OPERATOR_SELF"
    RELATED = "RELATED"
    INDEPENDENT_EXTERNAL = "INDEPENDENT_EXTERNAL"


class PaymentState(str, Enum):
    UNKNOWN = "UNKNOWN"
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    DISPUTED = "DISPUTED"


class MarketObservationKind(str, Enum):
    IMPRESSION = "IMPRESSION"
    ENGAGEMENT = "ENGAGEMENT"
    ENQUIRY = "ENQUIRY"
    QUALIFIED_LEAD = "QUALIFIED_LEAD"
    ORDER = "ORDER"
    PAYMENT = "PAYMENT"
    ACCEPTANCE = "ACCEPTANCE"
    REJECTION = "REJECTION"
    NO_RESPONSE = "NO_RESPONSE"
    LOSS = "LOSS"
    REFUND = "REFUND"
    DISPUTE = "DISPUTE"


class EvidenceClaimState(str, Enum):
    UNPROVED = "UNPROVED"
    PROVED = "PROVED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class CommercialSettlementState(str, Enum):
    SETTLED = "SETTLED"
    PARTIAL = "PARTIAL"
    FRACTURED = "FRACTURED"
    REFUSED = "REFUSED"


class SettlementOutcome(str, Enum):
    GAIN = "GAIN"
    LOSS = "LOSS"
    NO_RESPONSE = "NO_RESPONSE"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


def _nonempty(value: str, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required")
    return value.strip()


def _tuple_strings(values: tuple[str, ...], *, field_name: str, allow_empty: bool = True) -> None:
    if not allow_empty and not values:
        raise ValueError(f"{field_name} requires at least one value")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{field_name} values must be non-empty strings")


def _enum(value: Any, enum_type: type[Enum], *, field_name: str) -> Enum:
    try:
        return value if isinstance(value, enum_type) else enum_type(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} has unsupported value: {value}") from exc


def _optional_digest(value: str | None, *, field_name: str) -> None:
    if value is not None:
        require_digest(value, field_name=field_name)


def _require_currency(value: str) -> str:
    text = _nonempty(value, field_name="currency").upper()
    if len(text) != 3 or not text.isalpha():
        raise ValueError("currency must be a 3-letter alphabetic code")
    return text


@dataclass(frozen=True, slots=True)
class CommercialContext:
    context_id: str
    product_id: str
    metamorphic_unit_digest: str
    buyer_segment_id: str
    jurisdiction: str
    channel_id: str
    offer_id: str
    currency: str
    price_minor: int
    period_start: str
    period_end: str
    world_lease_digest: str
    world_state_digest: str
    market_state_digest: str
    creative_profile_digest: str
    copy_profile_digest: str
    source_refs: tuple[str, ...] = ()
    schema: str = "dio.commercial_context.v1"

    def __post_init__(self) -> None:
        for field_name in ("context_id", "product_id", "buyer_segment_id", "jurisdiction", "channel_id", "offer_id"):
            _nonempty(getattr(self, field_name), field_name=field_name)
        for field_name in (
            "metamorphic_unit_digest", "world_lease_digest", "world_state_digest",
            "market_state_digest", "creative_profile_digest", "copy_profile_digest",
        ):
            require_digest(getattr(self, field_name), field_name=field_name)
        object.__setattr__(self, "currency", _require_currency(self.currency))
        if not isinstance(self.price_minor, int) or isinstance(self.price_minor, bool) or self.price_minor < 0:
            raise ValueError("price_minor must be a non-negative integer")
        start = parse_datetime(self.period_start, field_name="period_start")
        end = parse_datetime(self.period_end, field_name="period_end")
        if end <= start:
            raise ValueError("period_end must be after period_start")
        _tuple_strings(self.source_refs, field_name="source_refs")

    @property
    def context_digest(self) -> str:
        return digest_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "context_id": self.context_id,
            "product_id": self.product_id,
            "metamorphic_unit_digest": self.metamorphic_unit_digest,
            "buyer_segment_id": self.buyer_segment_id,
            "jurisdiction": self.jurisdiction,
            "channel_id": self.channel_id,
            "offer_id": self.offer_id,
            "currency": self.currency,
            "price_minor": self.price_minor,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "world_lease_digest": self.world_lease_digest,
            "world_state_digest": self.world_state_digest,
            "market_state_digest": self.market_state_digest,
            "creative_profile_digest": self.creative_profile_digest,
            "copy_profile_digest": self.copy_profile_digest,
            "source_refs": list(self.source_refs),
            "context_digest": self.context_digest,
        }


@dataclass(frozen=True, slots=True)
class OfferState:
    offer_state_id: str
    offer_id: str
    product_id: str
    context_digest: str
    version: str
    lifecycle: OfferLifecycle
    price_hypothesis_id: str
    semantic_object_ref: str
    authority_ceiling: str
    claim_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    authority_created: bool = False
    schema: str = "dio.offer_state.v1"

    def __post_init__(self) -> None:
        for field_name in (
            "offer_state_id", "offer_id", "product_id", "version",
            "price_hypothesis_id", "semantic_object_ref", "authority_ceiling",
        ):
            _nonempty(getattr(self, field_name), field_name=field_name)
        require_digest(self.context_digest, field_name="context_digest")
        object.__setattr__(self, "lifecycle", _enum(self.lifecycle, OfferLifecycle, field_name="lifecycle"))
        _tuple_strings(self.claim_refs, field_name="claim_refs")
        _tuple_strings(self.evidence_refs, field_name="evidence_refs")
        if self.authority_created is not False:
            raise ValueError("offer state may not create authority")

    @property
    def offer_state_digest(self) -> str:
        return digest_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return {**_simple_payload(self), "offer_state_digest": self.offer_state_digest}


@dataclass(frozen=True, slots=True)
class ChannelState:
    channel_state_id: str
    channel_id: str
    context_digest: str
    access_state: ChannelAccessState
    read_capability_present: bool
    draft_capability_present: bool
    publish_capability_present: bool
    spend_capability_present: bool
    required_authority_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    authority_created: bool = False
    schema: str = "dio.channel_state.v1"

    def __post_init__(self) -> None:
        _nonempty(self.channel_state_id, field_name="channel_state_id")
        _nonempty(self.channel_id, field_name="channel_id")
        require_digest(self.context_digest, field_name="context_digest")
        object.__setattr__(self, "access_state", _enum(self.access_state, ChannelAccessState, field_name="access_state"))
        for field_name in (
            "read_capability_present", "draft_capability_present", "publish_capability_present", "spend_capability_present",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be boolean")
        _tuple_strings(self.required_authority_refs, field_name="required_authority_refs")
        _tuple_strings(self.evidence_refs, field_name="evidence_refs")
        if self.authority_created is not False:
            raise ValueError("channel state may describe capability but may not create authority")

    @property
    def channel_state_digest(self) -> str:
        return digest_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return {**_simple_payload(self), "channel_state_digest": self.channel_state_digest}


@dataclass(frozen=True, slots=True)
class PricingHypothesisState:
    pricing_state_id: str
    hypothesis_id: str
    context_digest: str
    amount_minor: int
    currency: str
    evidence_state: PricingEvidenceState
    exposure_count: int = 0
    verified_payment_count: int = 0
    accepted_customer_count: int = 0
    evidence_refs: tuple[str, ...] = ()
    schema: str = "dio.pricing_hypothesis_state.v1"

    def __post_init__(self) -> None:
        _nonempty(self.pricing_state_id, field_name="pricing_state_id")
        _nonempty(self.hypothesis_id, field_name="hypothesis_id")
        require_digest(self.context_digest, field_name="context_digest")
        if not isinstance(self.amount_minor, int) or isinstance(self.amount_minor, bool) or self.amount_minor < 0:
            raise ValueError("amount_minor must be a non-negative integer")
        object.__setattr__(self, "currency", _require_currency(self.currency))
        object.__setattr__(self, "evidence_state", _enum(self.evidence_state, PricingEvidenceState, field_name="evidence_state"))
        for field_name in ("exposure_count", "verified_payment_count", "accepted_customer_count"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.verified_payment_count > self.exposure_count:
            raise ValueError("verified_payment_count cannot exceed exposure_count")
        if self.accepted_customer_count > self.verified_payment_count:
            raise ValueError("accepted_customer_count cannot exceed verified_payment_count")
        _tuple_strings(self.evidence_refs, field_name="evidence_refs")

    @property
    def pricing_state_digest(self) -> str:
        return digest_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return {**_simple_payload(self), "pricing_state_digest": self.pricing_state_digest}


@dataclass(frozen=True, slots=True)
class CustomerLineage:
    customer_lineage_id: str
    context_digest: str
    subject_digest: str
    independence: CustomerIndependence
    source_refs: tuple[str, ...] = ()
    acceptance_refs: tuple[str, ...] = ()
    schema: str = "dio.customer_lineage.v1"

    def __post_init__(self) -> None:
        _nonempty(self.customer_lineage_id, field_name="customer_lineage_id")
        require_digest(self.context_digest, field_name="context_digest")
        require_digest(self.subject_digest, field_name="subject_digest")
        object.__setattr__(self, "independence", _enum(self.independence, CustomerIndependence, field_name="independence"))
        _tuple_strings(self.source_refs, field_name="source_refs")
        _tuple_strings(self.acceptance_refs, field_name="acceptance_refs")

    @property
    def customer_lineage_digest(self) -> str:
        return digest_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return {**_simple_payload(self), "customer_lineage_digest": self.customer_lineage_digest}


@dataclass(frozen=True, slots=True)
class PaymentLineage:
    payment_lineage_id: str
    context_digest: str
    order_id: str
    provider: str
    amount_minor: int
    currency: str
    payment_state: PaymentState
    customer_lineage_id: str | None = None
    provider_event_refs: tuple[str, ...] = ()
    live_order_refs: tuple[str, ...] = ()
    verified_at: str | None = None
    schema: str = "dio.payment_lineage.v1"

    def __post_init__(self) -> None:
        _nonempty(self.payment_lineage_id, field_name="payment_lineage_id")
        _nonempty(self.order_id, field_name="order_id")
        _nonempty(self.provider, field_name="provider")
        require_digest(self.context_digest, field_name="context_digest")
        if not isinstance(self.amount_minor, int) or isinstance(self.amount_minor, bool) or self.amount_minor < 0:
            raise ValueError("amount_minor must be a non-negative integer")
        object.__setattr__(self, "currency", _require_currency(self.currency))
        object.__setattr__(self, "payment_state", _enum(self.payment_state, PaymentState, field_name="payment_state"))
        if self.customer_lineage_id is not None:
            _nonempty(self.customer_lineage_id, field_name="customer_lineage_id")
        _tuple_strings(self.provider_event_refs, field_name="provider_event_refs")
        _tuple_strings(self.live_order_refs, field_name="live_order_refs")
        if self.verified_at is not None:
            parse_datetime(self.verified_at, field_name="verified_at")
        if self.payment_state == PaymentState.VERIFIED:
            if not self.provider_event_refs or not self.live_order_refs or self.verified_at is None:
                raise ValueError("VERIFIED payment requires provider event, live order evidence and verified_at")

    @property
    def payment_lineage_digest(self) -> str:
        return digest_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return {**_simple_payload(self), "payment_lineage_digest": self.payment_lineage_digest}


@dataclass(frozen=True, slots=True)
class MarketObservation:
    observation_id: str
    context_digest: str
    observed_at: str
    kind: MarketObservationKind
    source: str
    source_ref: str
    window_start: str
    window_end: str
    window_closed: bool
    evidence_refs: tuple[str, ...] = ()
    customer_lineage_id: str | None = None
    payment_lineage_id: str | None = None
    schema: str = "dio.market_observation.v1"

    def __post_init__(self) -> None:
        _nonempty(self.observation_id, field_name="observation_id")
        _nonempty(self.source, field_name="source")
        _nonempty(self.source_ref, field_name="source_ref")
        require_digest(self.context_digest, field_name="context_digest")
        parse_datetime(self.observed_at, field_name="observed_at")
        start = parse_datetime(self.window_start, field_name="window_start")
        end = parse_datetime(self.window_end, field_name="window_end")
        if end <= start:
            raise ValueError("window_end must be after window_start")
        if not isinstance(self.window_closed, bool):
            raise ValueError("window_closed must be boolean")
        object.__setattr__(self, "kind", _enum(self.kind, MarketObservationKind, field_name="kind"))
        _tuple_strings(self.evidence_refs, field_name="evidence_refs")
        if self.customer_lineage_id is not None:
            _nonempty(self.customer_lineage_id, field_name="customer_lineage_id")
        if self.payment_lineage_id is not None:
            _nonempty(self.payment_lineage_id, field_name="payment_lineage_id")
        if self.kind == MarketObservationKind.NO_RESPONSE and not self.window_closed:
            raise ValueError("NO_RESPONSE may only be recorded after the observation window closes")
        if self.kind == MarketObservationKind.PAYMENT and not self.payment_lineage_id:
            raise ValueError("PAYMENT observation requires payment_lineage_id")
        if self.kind == MarketObservationKind.ACCEPTANCE and not self.customer_lineage_id:
            raise ValueError("ACCEPTANCE observation requires customer_lineage_id")

    @property
    def observation_digest(self) -> str:
        return digest_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return {**_simple_payload(self), "observation_digest": self.observation_digest}


@dataclass(frozen=True, slots=True)
class CommercialSettlement:
    settlement_id: str
    context_digest: str
    settled_at: str
    settlement_state: CommercialSettlementState
    outcome: SettlementOutcome
    market_observation_digests: tuple[str, ...]
    customer_independence: CustomerIndependence
    verified_payment: EvidenceClaimState
    customer_acceptance: EvidenceClaimState
    willingness_to_pay: EvidenceClaimState
    repeatability: EvidenceClaimState
    validated_engagement_count: int = 0
    distinct_independent_customer_count: int = 0
    world_settlement_digest: str | None = None
    customer_lineage_digest: str | None = None
    payment_lineage_digest: str | None = None
    unexpected_effects: tuple[str, ...] = ()
    authority_preserved: bool = True
    authority_created: bool = False
    schema: str = "dio.commercial_settlement.v1"

    def __post_init__(self) -> None:
        _nonempty(self.settlement_id, field_name="settlement_id")
        require_digest(self.context_digest, field_name="context_digest")
        parse_datetime(self.settled_at, field_name="settled_at")
        object.__setattr__(self, "settlement_state", _enum(self.settlement_state, CommercialSettlementState, field_name="settlement_state"))
        object.__setattr__(self, "outcome", _enum(self.outcome, SettlementOutcome, field_name="outcome"))
        object.__setattr__(self, "customer_independence", _enum(self.customer_independence, CustomerIndependence, field_name="customer_independence"))
        for field_name in ("verified_payment", "customer_acceptance", "willingness_to_pay", "repeatability"):
            object.__setattr__(self, field_name, _enum(getattr(self, field_name), EvidenceClaimState, field_name=field_name))
        _tuple_strings(self.market_observation_digests, field_name="market_observation_digests")
        for value in self.market_observation_digests:
            require_digest(value, field_name="market_observation_digest")
        _tuple_strings(self.unexpected_effects, field_name="unexpected_effects")
        for field_name in ("world_settlement_digest", "customer_lineage_digest", "payment_lineage_digest"):
            _optional_digest(getattr(self, field_name), field_name=field_name)
        for field_name in ("validated_engagement_count", "distinct_independent_customer_count"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if not isinstance(self.authority_preserved, bool) or not isinstance(self.authority_created, bool):
            raise ValueError("authority flags must be boolean")
        if self.authority_created:
            raise ValueError("commercial settlement may not create authority")
        if self.settlement_state == CommercialSettlementState.SETTLED:
            if self.world_settlement_digest is None:
                raise ValueError("SETTLED commercial settlement requires world_settlement_digest")
            if not self.market_observation_digests:
                raise ValueError("SETTLED commercial settlement requires at least one market observation")
            if not self.authority_preserved:
                raise ValueError("SETTLED commercial settlement requires authority_preserved")
        if self.verified_payment == EvidenceClaimState.PROVED and self.payment_lineage_digest is None:
            raise ValueError("PROVED verified_payment requires payment_lineage_digest")
        if self.customer_acceptance == EvidenceClaimState.PROVED and self.customer_lineage_digest is None:
            raise ValueError("PROVED customer_acceptance requires customer_lineage_digest")
        if self.willingness_to_pay == EvidenceClaimState.PROVED:
            if not (
                self.verified_payment == EvidenceClaimState.PROVED
                and self.customer_acceptance == EvidenceClaimState.PROVED
                and self.customer_independence == CustomerIndependence.INDEPENDENT_EXTERNAL
            ):
                raise ValueError("WTP PROVED requires verified payment plus independent-customer acceptance")
        if self.repeatability == EvidenceClaimState.PROVED:
            if not (
                self.willingness_to_pay == EvidenceClaimState.PROVED
                and self.validated_engagement_count >= 3
                and self.distinct_independent_customer_count >= 3
            ):
                raise ValueError("repeatability PROVED requires >=3 validated engagements from >=3 independent customers")
        if self.outcome == SettlementOutcome.NO_RESPONSE:
            if any(
                state == EvidenceClaimState.PROVED
                for state in (self.verified_payment, self.customer_acceptance, self.willingness_to_pay, self.repeatability)
            ):
                raise ValueError("NO_RESPONSE cannot carry proved payment, acceptance, WTP or repeatability")

    @property
    def settlement_digest(self) -> str:
        return digest_payload(self)

    @property
    def market_crystal_eligible(self) -> bool:
        return (
            self.settlement_state == CommercialSettlementState.SETTLED
            and self.world_settlement_digest is not None
            and self.authority_preserved
            and not self.authority_created
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            **_simple_payload(self),
            "market_crystal_eligible": self.market_crystal_eligible,
            "settlement_digest": self.settlement_digest,
        }


def _simple_payload(value: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field_name in value.__dataclass_fields__:
        item = getattr(value, field_name)
        if isinstance(item, Enum):
            result[field_name] = item.value
        elif isinstance(item, tuple):
            result[field_name] = list(item)
        else:
            result[field_name] = item
    return result


SCHEMA_FILES = (
    "dio.commercial_context.v1.json",
    "dio.offer_state.v1.json",
    "dio.channel_state.v1.json",
    "dio.pricing_hypothesis_state.v1.json",
    "dio.customer_lineage.v1.json",
    "dio.payment_lineage.v1.json",
    "dio.market_observation.v1.json",
    "dio.commercial_settlement.v1.json",
)


def phase1_contract_receipt(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    parent = validate_commercial_constitution(root)
    missing: list[str] = []
    invalid: list[str] = []
    schemas: list[dict[str, Any]] = []
    for name in SCHEMA_FILES:
        path = root / "schemas" / name
        if not path.is_file():
            missing.append(str(path.relative_to(root)))
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            invalid.append(name)
            continue
        if payload.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            invalid.append(name)
            continue
        schemas.append({"name": name, "title": payload.get("title"), "id": payload.get("$id")})

    enum_contracts = {
        "offer_lifecycle": [row.value for row in OfferLifecycle],
        "channel_access_state": [row.value for row in ChannelAccessState],
        "pricing_evidence_state": [row.value for row in PricingEvidenceState],
        "customer_independence": [row.value for row in CustomerIndependence],
        "payment_state": [row.value for row in PaymentState],
        "market_observation_kind": [row.value for row in MarketObservationKind],
        "evidence_claim_state": [row.value for row in EvidenceClaimState],
        "commercial_settlement_state": [row.value for row in CommercialSettlementState],
        "settlement_outcome": [row.value for row in SettlementOutcome],
    }
    passed = (
        parent.get("passed") is True
        and parent.get("acceptance") == M2_PHASE0_EXIT_TOKEN
        and len(schemas) == len(SCHEMA_FILES)
        and not missing
        and not invalid
    )
    return {
        "phase": "M2-1",
        "acceptance": M2_PHASE1_EXIT_TOKEN if passed else "DIO_M2_COMMERCIAL_CONTRACTS_BLOCKED",
        "passed": passed,
        "parent_phase": parent.get("phase"),
        "parent_acceptance": parent.get("acceptance"),
        "parent_verified": parent.get("passed") is True,
        "schema_count": len(schemas),
        "schemas": schemas,
        "missing_schemas": missing,
        "invalid_schemas": invalid,
        "enum_contracts": enum_contracts,
        "immutable_contracts": True,
        "customer_payment_lineage_distinct": True,
        "world_binding_required": True,
        "payment_implies_wtp": False,
        "customer_acceptance_implies_repeatability": False,
        "no_response_requires_closed_window": True,
        "market_crystal_requires_settlement": True,
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
        "new_runtime_engine_created": False,
        "m2_final_verified": False,
    }


__all__ = [
    "ChannelAccessState", "ChannelState", "CommercialContext", "CommercialSettlement",
    "CommercialSettlementState", "CustomerIndependence", "CustomerLineage",
    "EvidenceClaimState", "M2_PHASE1_EXIT_TOKEN", "MarketObservation",
    "MarketObservationKind", "OfferLifecycle", "OfferState", "PaymentLineage",
    "PaymentState", "PricingEvidenceState", "PricingHypothesisState", "SCHEMA_FILES",
    "SettlementOutcome", "phase1_contract_receipt",
]
