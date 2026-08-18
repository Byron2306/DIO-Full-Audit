# DIO M2 Commercial Metabolism — Phase 2 LINGUA Commercial Projection

## Purpose

M2-2 turns verified product proof into bounded buyer-facing commercial meaning without converting proof gaps into claims.

Acceptance token:

```text
DIO_M2_LINGUA_COMMERCIAL_PROJECTION_READY
```

This phase creates no publication, send, spend, payment, delivery or market-response event.

## Source hierarchy

The projection is derived from:

```text
verified M1 Funding Proposal Studio identity
        ↓
M2-0 commercial constitution
        ↓
M2-1 immutable CommercialContext
        ↓
structured source-bound claim catalogue
        ↓
existing LINGUA semantic lifecycle
        ↓
HELD OfferState + CommercialProjection
```

The projection does not own egress authority. Seraph remains the consequential release boundary.

## Claim states

Every configured commercial claim resolves to exactly one state:

- `SUPPORTED` — current source-bound proof supports the statement inside the exact CommercialContext;
- `HELD_UNPROVED` — the statement could become supportable later but the required evidence does not yet exist;
- `REFUSE` — the statement conflicts with constitutional or authority boundaries.

Only `SUPPORTED` claims are eligible for buyer copy.

## Current reference truth

Supported M1-derived claims include:

- Funding Proposal Studio can prepare a controlled funding proposal pack;
- it is a governed metamorphic composition;
- the reference composition completed world settlement and BEAST crystallisation;
- the same governed identity spans product and capability roles;
- the verified reference run remained controlled-artifact-only with no external effects.

The following remain explicitly held:

```text
substantive Finance → Article → Correspondence content dataflow
market demand
independent customer acceptance
willingness to pay
commercial validation
repeatability
ROI
```

The first item is deliberately reserved for M3 Emergent Synthesis.

Constitutionally refused claims include guaranteed funding outcomes, automatic submission, implicit external-action authority and authority widening from commercial success.

## LINGUA reuse

M2-2 registers the held offer as a normal versioned LINGUA semantic object using `adapters.lingua.lifecycle.register_product_source`.

The semantic object contains separate units for:

- title;
- buyer promise;
- proof boundary;
- commercial boundary;
- authority boundary.

Changed source meaning therefore changes the LINGUA source hash rather than silently overwriting the prior projection.

## Deterministic phrase guard boundary

M2-2 includes a deterministic guard for configured phrases such as unsupported WTP, commercial validation, ROI, guaranteed funding and automatic submission language.

This is a narrow release-preflight mechanism. It does **not** claim general or autonomous natural-language claim inference.

```text
autonomous_natural_language_claim_inference_claimed = false
```

A phrase-clean result still creates no publication or send authority.

## World and context binding

Every claim binds the exact `CommercialContext` digest. The context includes product identity, buyer segment, jurisdiction, channel, offer, price/currency, test period, world lease, world state, market state, creative profile and copy profile.

A changed context produces a different projection identity.

## Acceptance boundary

M2-2 proves:

```text
M1 proof → bounded commercial meaning
LINGUA semantic object reused
SUPPORTED / HELD_UNPROVED / REFUSE separated
M3 content-dataflow claim held
market-success claims held
constitutional claims refused
context change changes projection identity
no authority created
no external effects
```

It does not prove market response, payment, acceptance, WTP, validation, repeatability or commercial learning.
