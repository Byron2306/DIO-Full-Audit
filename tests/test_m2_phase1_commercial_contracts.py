from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from commercial_metabolism.contracts import (
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
    SCHEMA_FILES,
    SettlementOutcome,
    phase1_contract_receipt,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def d(char: str) -> str:
    return "sha256:" + char * 64


@pytest.fixture(scope="module")
def phase_receipt():
    return phase1_contract_receipt(REPO_ROOT)


@pytest.fixture()
def context():
    return CommercialContext(
        context_id="CTX-FUNDING-001",
        product_id="funding_proposal_studio",
        metamorphic_unit_digest=d("a"),
        buyer_segment_id="sa_sme_founders",
        jurisdiction="ZA",
        channel_id="OUTLOOK",
        offer_id="funding_proposal_reference_offer",
        currency="zar",
        price_minor=250000,
        period_start="2026-08-19T00:00:00+00:00",
        period_end="2026-09-19T00:00:00+00:00",
        world_lease_digest=d("b"),
        world_state_digest=d("c"),
        market_state_digest=d("d"),
        creative_profile_digest=d("e"),
        copy_profile_digest=d("f"),
        source_refs=("market-command:campaign-1",),
    )


def test_m2_phase1_contract_gate_passes(phase_receipt):
    assert phase_receipt["passed"] is True, phase_receipt
    assert phase_receipt["acceptance"] == M2_PHASE1_EXIT_TOKEN
    assert phase_receipt["parent_acceptance"] == "DIO_M2_COMMERCIAL_CONSTITUTION_FROZEN"
    assert phase_receipt["schema_count"] == 8
    assert len(SCHEMA_FILES) == 8
    assert phase_receipt["missing_schemas"] == []
    assert phase_receipt["invalid_schemas"] == []


def test_commercial_context_is_deterministic_and_world_bound(context):
    twin = CommercialContext(**{
        key: getattr(context, key)
        for key in context.__dataclass_fields__
        if key != "schema"
    })
    changed = CommercialContext(
        **{
            key: (d("9") if key == "world_state_digest" else getattr(context, key))
            for key in context.__dataclass_fields__
            if key != "schema"
        }
    )
    assert context.currency == "ZAR"
    assert context.context_digest == twin.context_digest
    assert context.context_digest != changed.context_digest
    assert context.to_dict()["world_lease_digest"] == d("b")


def test_commercial_context_rejects_invalid_time_and_price(context):
    payload = {key: getattr(context, key) for key in context.__dataclass_fields__ if key != "schema"}
    with pytest.raises(ValueError):
        CommercialContext(**{**payload, "period_end": payload["period_start"]})
    with pytest.raises(ValueError):
        CommercialContext(**{**payload, "price_minor": -1})


def test_offer_and_channel_describe_capability_without_minting_authority(context):
    offer = OfferState(
        offer_state_id="OFFSTATE-1",
        offer_id=context.offer_id,
        product_id=context.product_id,
        context_digest=context.context_digest,
        version="1.0.0",
        lifecycle=OfferLifecycle.HELD,
        price_hypothesis_id="PRICE-1",
        semantic_object_ref="LINGUA-OFFER-1",
        authority_ceiling="draft_only",
        claim_refs=("CLAIM-1",),
        evidence_refs=("EVIDENCE-1",),
    )
    channel = ChannelState(
        channel_state_id="CHANSTATE-1",
        channel_id=context.channel_id,
        context_digest=context.context_digest,
        access_state=ChannelAccessState.DRAFT_ONLY,
        read_capability_present=True,
        draft_capability_present=True,
        publish_capability_present=True,
        spend_capability_present=False,
        required_authority_refs=("SERAPH:SEND",),
    )
    assert offer.authority_created is False
    assert channel.publish_capability_present is True
    assert channel.authority_created is False
    with pytest.raises(ValueError):
        OfferState(
            offer_state_id="OFFSTATE-BAD", offer_id=context.offer_id, product_id=context.product_id,
            context_digest=context.context_digest, version="1", lifecycle=OfferLifecycle.HELD,
            price_hypothesis_id="PRICE-1", semantic_object_ref="LINGUA-1",
            authority_ceiling="draft_only", authority_created=True,
        )


def test_pricing_hypothesis_keeps_evidence_counts_bounded(context):
    pricing = PricingHypothesisState(
        pricing_state_id="PRICESTATE-1",
        hypothesis_id="PRICE-1",
        context_digest=context.context_digest,
        amount_minor=context.price_minor,
        currency=context.currency,
        evidence_state=PricingEvidenceState.OBSERVING,
        exposure_count=4,
        verified_payment_count=1,
        accepted_customer_count=0,
    )
    assert pricing.evidence_state == PricingEvidenceState.OBSERVING
    with pytest.raises(ValueError):
        PricingHypothesisState(
            pricing_state_id="BAD", hypothesis_id="PRICE-1", context_digest=context.context_digest,
            amount_minor=100, currency="ZAR", evidence_state=PricingEvidenceState.SUPPORTED,
            exposure_count=1, verified_payment_count=2,
        )


def test_customer_and_payment_lineage_are_distinct_objects(context):
    customer = CustomerLineage(
        customer_lineage_id="CUST-1",
        context_digest=context.context_digest,
        subject_digest=d("1"),
        independence=CustomerIndependence.INDEPENDENT_EXTERNAL,
        source_refs=("outlook:reply-1",),
    )
    payment = PaymentLineage(
        payment_lineage_id="PAY-1",
        context_digest=context.context_digest,
        order_id="ORDER-1",
        provider="DIO_EDGE",
        amount_minor=context.price_minor,
        currency=context.currency,
        payment_state=PaymentState.VERIFIED,
        customer_lineage_id=customer.customer_lineage_id,
        provider_event_refs=("edge:event-1",),
        live_order_refs=("edge:order-1",),
        verified_at="2026-08-20T12:00:00+00:00",
    )
    assert customer.customer_lineage_digest != payment.payment_lineage_digest
    assert payment.customer_lineage_id == customer.customer_lineage_id


def test_verified_payment_requires_provider_and_live_order_evidence(context):
    with pytest.raises(ValueError):
        PaymentLineage(
            payment_lineage_id="PAY-BAD", context_digest=context.context_digest,
            order_id="ORDER-1", provider="DIO_EDGE", amount_minor=100, currency="ZAR",
            payment_state=PaymentState.VERIFIED,
        )


def test_no_response_requires_closed_observation_window(context):
    with pytest.raises(ValueError):
        MarketObservation(
            observation_id="OBS-NO-1", context_digest=context.context_digest,
            observed_at="2026-08-22T00:00:00+00:00", kind=MarketObservationKind.NO_RESPONSE,
            source="MARKET_COMMAND", source_ref="campaign:1",
            window_start="2026-08-20T00:00:00+00:00", window_end="2026-08-22T00:00:00+00:00",
            window_closed=False,
        )
    observation = MarketObservation(
        observation_id="OBS-NO-2", context_digest=context.context_digest,
        observed_at="2026-08-22T00:00:00+00:00", kind=MarketObservationKind.NO_RESPONSE,
        source="MARKET_COMMAND", source_ref="campaign:1",
        window_start="2026-08-20T00:00:00+00:00", window_end="2026-08-22T00:00:00+00:00",
        window_closed=True,
    )
    assert observation.kind == MarketObservationKind.NO_RESPONSE


def test_payment_and_acceptance_observations_require_lineage(context):
    base = dict(
        context_digest=context.context_digest,
        observed_at="2026-08-21T00:00:00+00:00",
        source="MARKET_COMMAND",
        source_ref="campaign:1",
        window_start="2026-08-20T00:00:00+00:00",
        window_end="2026-08-22T00:00:00+00:00",
        window_closed=False,
    )
    with pytest.raises(ValueError):
        MarketObservation(observation_id="OBS-PAY", kind=MarketObservationKind.PAYMENT, **base)
    with pytest.raises(ValueError):
        MarketObservation(observation_id="OBS-ACC", kind=MarketObservationKind.ACCEPTANCE, **base)


def test_payment_alone_does_not_prove_wtp(context):
    settlement = CommercialSettlement(
        settlement_id="SETTLE-PAYMENT-ONLY",
        context_digest=context.context_digest,
        settled_at="2026-08-23T00:00:00+00:00",
        settlement_state=CommercialSettlementState.SETTLED,
        outcome=SettlementOutcome.GAIN,
        market_observation_digests=(d("2"),),
        customer_independence=CustomerIndependence.UNKNOWN,
        verified_payment=EvidenceClaimState.PROVED,
        customer_acceptance=EvidenceClaimState.UNPROVED,
        willingness_to_pay=EvidenceClaimState.UNPROVED,
        repeatability=EvidenceClaimState.UNPROVED,
        world_settlement_digest=d("3"),
        payment_lineage_digest=d("4"),
    )
    assert settlement.verified_payment == EvidenceClaimState.PROVED
    assert settlement.willingness_to_pay == EvidenceClaimState.UNPROVED
    assert settlement.authority_created is False


def test_wtp_refuses_self_payment_or_missing_acceptance(context):
    kwargs = dict(
        settlement_id="SETTLE-WTP-BAD",
        context_digest=context.context_digest,
        settled_at="2026-08-23T00:00:00+00:00",
        settlement_state=CommercialSettlementState.SETTLED,
        outcome=SettlementOutcome.GAIN,
        market_observation_digests=(d("2"),),
        verified_payment=EvidenceClaimState.PROVED,
        customer_acceptance=EvidenceClaimState.PROVED,
        willingness_to_pay=EvidenceClaimState.PROVED,
        repeatability=EvidenceClaimState.UNPROVED,
        world_settlement_digest=d("3"),
        customer_lineage_digest=d("5"),
        payment_lineage_digest=d("4"),
    )
    with pytest.raises(ValueError):
        CommercialSettlement(customer_independence=CustomerIndependence.OPERATOR_SELF, **kwargs)
    with pytest.raises(ValueError):
        CommercialSettlement(
            customer_independence=CustomerIndependence.INDEPENDENT_EXTERNAL,
            **{**kwargs, "customer_acceptance": EvidenceClaimState.UNPROVED},
        )


def test_repeatability_requires_three_independent_validated_engagements(context):
    base = dict(
        settlement_id="SETTLE-REPEAT",
        context_digest=context.context_digest,
        settled_at="2026-08-23T00:00:00+00:00",
        settlement_state=CommercialSettlementState.SETTLED,
        outcome=SettlementOutcome.GAIN,
        market_observation_digests=(d("2"),),
        customer_independence=CustomerIndependence.INDEPENDENT_EXTERNAL,
        verified_payment=EvidenceClaimState.PROVED,
        customer_acceptance=EvidenceClaimState.PROVED,
        willingness_to_pay=EvidenceClaimState.PROVED,
        repeatability=EvidenceClaimState.PROVED,
        world_settlement_digest=d("3"),
        customer_lineage_digest=d("5"),
        payment_lineage_digest=d("4"),
    )
    with pytest.raises(ValueError):
        CommercialSettlement(validated_engagement_count=2, distinct_independent_customer_count=2, **base)
    good = CommercialSettlement(validated_engagement_count=3, distinct_independent_customer_count=3, **base)
    assert good.repeatability == EvidenceClaimState.PROVED


def test_settled_commercial_state_requires_world_settlement_and_observation(context):
    with pytest.raises(ValueError):
        CommercialSettlement(
            settlement_id="SETTLE-NOWORLD", context_digest=context.context_digest,
            settled_at="2026-08-23T00:00:00+00:00",
            settlement_state=CommercialSettlementState.SETTLED,
            outcome=SettlementOutcome.UNKNOWN,
            market_observation_digests=(d("2"),),
            customer_independence=CustomerIndependence.UNKNOWN,
            verified_payment=EvidenceClaimState.UNPROVED,
            customer_acceptance=EvidenceClaimState.UNPROVED,
            willingness_to_pay=EvidenceClaimState.UNPROVED,
            repeatability=EvidenceClaimState.UNPROVED,
        )


def test_market_crystal_eligibility_only_follows_complete_settlement(context):
    partial = CommercialSettlement(
        settlement_id="SETTLE-PARTIAL", context_digest=context.context_digest,
        settled_at="2026-08-23T00:00:00+00:00",
        settlement_state=CommercialSettlementState.PARTIAL,
        outcome=SettlementOutcome.MIXED,
        market_observation_digests=(d("2"),),
        customer_independence=CustomerIndependence.UNKNOWN,
        verified_payment=EvidenceClaimState.UNPROVED,
        customer_acceptance=EvidenceClaimState.UNPROVED,
        willingness_to_pay=EvidenceClaimState.UNPROVED,
        repeatability=EvidenceClaimState.UNPROVED,
    )
    settled = CommercialSettlement(
        settlement_id="SETTLE-GOOD", context_digest=context.context_digest,
        settled_at="2026-08-23T00:00:00+00:00",
        settlement_state=CommercialSettlementState.SETTLED,
        outcome=SettlementOutcome.LOSS,
        market_observation_digests=(d("2"),),
        customer_independence=CustomerIndependence.UNKNOWN,
        verified_payment=EvidenceClaimState.UNPROVED,
        customer_acceptance=EvidenceClaimState.UNPROVED,
        willingness_to_pay=EvidenceClaimState.UNPROVED,
        repeatability=EvidenceClaimState.UNPROVED,
        world_settlement_digest=d("3"),
    )
    assert partial.market_crystal_eligible is False
    assert settled.market_crystal_eligible is True


def test_no_response_settlement_cannot_smuggle_positive_claims(context):
    with pytest.raises(ValueError):
        CommercialSettlement(
            settlement_id="SETTLE-NORESPONSE-BAD", context_digest=context.context_digest,
            settled_at="2026-08-23T00:00:00+00:00",
            settlement_state=CommercialSettlementState.SETTLED,
            outcome=SettlementOutcome.NO_RESPONSE,
            market_observation_digests=(d("2"),),
            customer_independence=CustomerIndependence.UNKNOWN,
            verified_payment=EvidenceClaimState.PROVED,
            customer_acceptance=EvidenceClaimState.UNPROVED,
            willingness_to_pay=EvidenceClaimState.UNPROVED,
            repeatability=EvidenceClaimState.UNPROVED,
            world_settlement_digest=d("3"),
            payment_lineage_digest=d("4"),
        )


def test_commercial_contracts_are_frozen(context):
    with pytest.raises(FrozenInstanceError):
        context.product_id = "something_else"
    assert phase1_contract_receipt(REPO_ROOT)["new_runtime_engine_created"] is False
