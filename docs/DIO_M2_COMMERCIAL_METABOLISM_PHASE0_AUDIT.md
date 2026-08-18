# DIO M2 Commercial Metabolism — Phase 0 Audit

## Purpose

M2 begins from the verified Metamorphic Spine M1 parent. Phase M2-0 does not create a new marketing, payment, market-observation, learning or authority engine. It freezes the commercial constitution and inventories the existing organs that M2 must harvest.

Acceptance token:

```text
DIO_M2_COMMERCIAL_CONSTITUTION_FROZEN
```

## Audit conclusion

DIO is not entering M2 with an empty commercial stack. The repository already contains most of the substrate required for commercial metabolism:

- Commercial Truth Layer for evidence separation;
- Commercial Proof v1.1 for source-bound market/payment/acceptance truth;
- Paid Reference Products for controlled end-to-end commercial plumbing;
- Commerce Core orchestration and append-only commercial state;
- authenticated DIO Edge payment verification and local event materialisation;
- Market Command planning, measurements, attribution and governed content state;
- NicheFoundry + LINGUA commercial learning doctrine;
- LINGUA semantic lifecycle;
- Sensorium observation;
- BEAST evidence crystallisation;
- Seraph outbound gating;
- Legalis prerequisite evaluation;
- world lease and world settlement machinery.

M2 therefore follows the Harvest Law: compose and harden existing capabilities before inventing new engines.

## Constitutional commercial laws

```text
market research != willingness to pay
zero-value flow != revenue
self-payment != independent demand
verified payment != customer acceptance
verified payment != willingness to pay without independent acceptance
customer acceptance != repeatability
commercial success != authority
commercial failure != global product invalidity
silence is evidence only in its exact context
Market Command != egress authority
Seraph owns the commercial egress boundary
no market crystal before commercial settlement
commercial learning != direct execution/publication/spend
customer lineage != payment lineage
commercial facts are world-state bound
```

## Harvest ownership boundaries

### Commercial Truth Layer

Owns semantic separation among offer, demand, payment, fulfilment, delivery acceptance, value confirmation, repetition and economic evidence. Its law `Payment proves payment only` is normative for M2.

### Commercial Proof v1.1

Owns source-bound evaluation of market viability, authenticated payment, independent customer acceptance, WTP and validation gates. Positive payment alone remains WTP-unproved until independent source-bound customer acceptance corroborates the commercial lineage.

### DIO Edge

Owns provider-verification evidence for payment events and bound order state. Browser redirects never become payment truth. Provider events remain bound to amount, currency, merchant/order identity and verification evidence.

### Commerce Core

Owns workflow lineage and commercial state transitions. Its local advisory/triune machinery may inform workflow state, but it is not promoted to canonical Harmonics, Seraph, BEAST, world-state or authority ownership.

### Market Command

Owns planning state, campaign/content records, measurements and attribution. Automatic spend remains off. Campaign activation or approval state is not itself Seraph egress authority.

### NicheFoundry + LINGUA

Own commercial hypothesis/creative semantics and candidate learning. There is no direct learning-to-execution path. Positive reuse remains scoped and governed; repeated negative evidence may suppress an exact learned pattern without globally invalidating the product or channel.

### Sensorium

Owns observation of what happened, including response, rejection, silence and loss once M2 market episodes are introduced.

### BEAST

Owns evidence learning and crystallisation after settlement. Market success never mints authority.

### Seraph

Remains the commercial egress membrane for consequential release. PUBLISH, SEND, SPEND, PURCHASE, DEPLOY and DELIVER require independent authority decisions.

### Legalis

Evaluates configured legal/external prerequisites. `ALLOW` means prerequisites are satisfied; it is not a legal opinion and it does not create external-release authority.

### World State / Settlement

Commercial facts remain relative to the tested world, epoch, policy and market context. No market crystal may be promoted before a complete commercial settlement.

## Legacy semantic hazards found

Phase M2-0 deliberately preserves historical documents while refusing to inherit obsolete semantics from them.

### Hazard 1 — payment implied WTP

`docs/DIO_COMMERCIAL_PROOF_GAUNTLET_V1.md` contains the older statement that a successful positive-value payment proves both verified payment and willingness to pay.

This is quarantined by `products/commercial_proof_v1_1.py`, which requires independent customer acceptance before WTP promotion and explicitly excludes operator/self-payment as market WTP.

### Hazard 2 — one paid order labelled “someone will pay”

`docs/DIO_COMMERCIAL_OPERATING_PLAN.md` contains a historical evidence tier:

```text
Commercial | at least 1 verified paid order | Someone will pay
```

M2 does not use that wording as truth authority. It is quarantined by the Commercial Truth Layer and the stricter M2 constitution: payment proves payment only; independent customer identity, source-bound acceptance and later repeatability remain separate gates.

These hazards are retained as historical architecture, not silently rewritten. The M2 constitution must detect them and verify the stronger correction remains present.

## Phase boundary

M2-0 performs:

```text
AUDIT
HASH-BIND
CLASSIFY
QUARANTINE LEGACY SEMANTICS
FREEZE COMMERCIAL LAWS
```

It does not perform:

```text
PUBLISH
SEND
SPEND
PURCHASE
DEPLOY
DELIVER
CREATE PAYMENT
CREATE MARKET RESPONSE
CREATE CUSTOMER ACCEPTANCE
CREATE MARKET CRYSTAL
```

## Next phase

M2-1 introduces immutable commercial context and lineage contracts over this harvested substrate:

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

No M2-1 contract may erase the ownership boundaries frozen here.
