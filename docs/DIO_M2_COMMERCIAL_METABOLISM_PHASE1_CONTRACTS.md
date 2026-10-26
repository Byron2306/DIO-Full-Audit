# DIO M2 Commercial Metabolism — Phase 1 Contracts

## Purpose

M2-1 converts the commercial constitution into immutable, hash-bound commercial objects. It does not create a new commercial runtime. Existing DIO owners remain unchanged: DIO Edge verifies payment, Market Command observes and attributes, LINGUA/NicheFoundry own commercial semantics, Sensorium observes, BEAST crystallises settled evidence, Legalis evaluates prerequisites and Seraph owns consequential egress.

Acceptance token:

```text
DIO_M2_COMMERCIAL_CONTRACTS_READY
```

## Contract set

Eight commercial contract types are introduced:

```text
CommercialContext
OfferState
ChannelState
PricingHypothesisState
CustomerLineage
PaymentLineage
MarketObservation
CommercialSettlement
```

All are frozen dataclasses with deterministic SHA-256 fingerprints and matching Draft 2020-12 JSON Schemas.

## CommercialContext

A commercial fact is never context-free. `CommercialContext` binds:

- metamorphic product identity;
- buyer segment;
- jurisdiction;
- channel;
- offer;
- exact price and currency;
- observation period;
- world lease;
- world-state digest;
- market-state digest;
- creative profile;
- copy profile;
- source references.

Changing world state, price, segment, channel, creative or copy changes the context digest. Evidence earned in one context therefore cannot silently become universal truth.

## Offer and channel state

`OfferState` records lifecycle, claims, evidence, semantic object and authority ceiling. It has no mechanism for creating authority.

`ChannelState` separates the existence of a technical capability from authority to use it. A channel may have publication or spend capability present while still being `DRAFT_ONLY`, `BLOCKED` or awaiting Seraph authority. `authority_created` is constitutionally fixed to `false`.

## Pricing hypothesis

`PricingHypothesisState` records an evidence snapshot rather than an automatic pricing optimiser. Its closed states are:

```text
UNTESTED
EXPOSED
OBSERVING
SUPPORTED
WEAKENED
REFUTED
```

Exposure, verified-payment and accepted-customer counts remain separate. A payment count cannot exceed exposure and customer acceptance cannot exceed verified payments in the bound pricing lineage.

## Customer and payment lineage

Customer identity and payment truth are deliberately different objects.

`CustomerLineage` binds a pseudonymous subject digest, source evidence and one of:

```text
UNKNOWN
OPERATOR_SELF
RELATED
INDEPENDENT_EXTERNAL
```

`PaymentLineage` binds order, provider, amount, currency, provider-event evidence and authenticated live-order evidence. A `VERIFIED` payment requires both provider event and live order evidence plus a timestamp.

Payment lineage may refer to customer lineage, but the two digests can never collapse into one commercial fact.

## Market observation

`MarketObservation` records what was observed in an exact window. Closed observation kinds include response events plus explicit `REJECTION`, `NO_RESPONSE`, `LOSS`, `REFUND` and `DISPUTE`.

`NO_RESPONSE` may only be recorded when its observation window is closed. It is therefore contextual negative evidence rather than an invented zero or a global product verdict.

Payment observations require a payment-lineage reference. Acceptance observations require a customer-lineage reference.

## Commercial settlement

`CommercialSettlement` keeps these claims separate:

```text
verified payment
customer acceptance
willingness to pay
repeatability
```

A settled commercial episode must bind at least one market observation and a completed world settlement.

WTP may be `PROVED` only when:

```text
verified payment = PROVED
customer acceptance = PROVED
customer independence = INDEPENDENT_EXTERNAL
```

Repeatability may be `PROVED` only after WTP is proved and at least three validated engagements from at least three independent customers are bound.

A `NO_RESPONSE` settlement may not carry proved payment, acceptance, WTP or repeatability.

## Crystal boundary

`market_crystal_eligible` is only true after a complete `SETTLED` commercial settlement with a world-settlement digest and preserved authority. Eligibility does not mint a crystal and never creates authority. BEAST remains responsible for crystallisation in a later M2 phase.

## Authority boundary

Every M2-1 contract is descriptive evidence state. M2-1 performs no:

```text
PUBLISH
SEND
SPEND
PURCHASE
DEPLOY
DELIVER
PAYMENT CREATION
CUSTOMER CREATION
MARKET CRYSTAL MINTING
AUTHORITY PROMOTION
```

## Acceptance

Run:

```bash
python -m pytest -q tests/test_m2_phase1_commercial_contracts.py
python scripts/run_m2_phase1.py
```

The gate requires the verified M2-0 parent, eight valid schemas, exact closed vocabularies, separate customer/payment lineage, world binding, no direct authority creation and zero external effects.

## Next phase

M2-2 should bind these contracts to the existing commercial organs rather than inventing replacements:

```text
Market Command campaign/content state
        ↓
CommercialContext + OfferState + ChannelState
        ↓
LINGUA commercial semantic projection
        ↓
held/released market episode
        ↓
MarketObservation + CustomerLineage + PaymentLineage
        ↓
CommercialSettlement
```

The objective is to make existing commercial execution and observation produce the new immutable M2 objects with complete lineage.
