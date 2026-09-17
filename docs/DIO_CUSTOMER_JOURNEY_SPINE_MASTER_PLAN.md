# DIO Customer Journey Spine — Master Programme

**Frozen:** 2026-09-17  
**Programme:** Final DIO Commercial Spine  
**Target branch:** `agent/vesper-slice6-production-foundation`  
**Status:** MASTER PLAN FROZEN; PHASE 0 ACTIVE

## Governing law

> We do not wire 68 products individually to Vesper. We wire the major organs once to a shared Customer Journey Spine, then bind the 68 incarnations to those organ contracts.

The customer journey is the stable commercial spine. Products remain governed incarnations. Specialist systems remain governed organs or bounded executors. Vesper is the conversational ingress/egress presence, never an independent authority plane.

The target lifecycle is:

```text
lead
→ intake
→ scope
→ quote
→ settlement
→ fulfilment
→ review
→ release
→ delivery
→ close / follow-up
```

A product may vary the required inputs, scope model, price strategy, organ composition, human gates and deliverables. It must not create its own private commerce pipeline.

## Programme phases

| Phase | Objective | Build / change | Exit gate |
| --- | --- | --- | --- |
| **0. Organ Census & Constitution Freeze** | Establish what every major organ actually is | Inventory Vesper, Sophia, Evidex, VAMP, HOMS, Learning Studio, Document Studio, NicheFoundry, Lingua, Format, BEAST, Seraph, Metatron, ARDA, Legalis, Market Command, Sensorium, Hivenance, Valinor and Obligation Core. Map the full 68-product portfolio to primary and secondary organs. Freeze `surface`, `journey`, `organ`, `incarnation`, `authority`, `deliverable`. | 68/68 products resolve to a known execution composition. No mystery product and no bespoke customer-flow plumbing. |
| **1. Journey Core v1** | Make the customer case surface-neutral | Refactor case identity away from conversation-derived identity. Add surface bindings for Telegram, web, email, voice, API and Control Deck/operator. Preserve case history and successor-source semantics. Freeze typed journey stages and transition rules. | One canonical case can begin on one surface and continue on another without identity fragmentation. |
| **2. Intake, Scope & Quote Contract** | Make Vesper ask, scope and quote from governed truth | Freeze `IntakeRequirement`, `ScopeReceipt`, `QuoteRequest` and `QuoteResult`. Product profiles declare required/optional inputs, scope dimensions, pricing strategy and quote authority. | Vesper does not re-ask for supplied inputs, quote before sufficient scope, or invent price/scope from chat memory. |
| **3. Settlement & Commercial Truth** | Separate workflow progression from money truth | Introduce typed settlement classes such as `REAL_SETTLEMENT`, `CONTROLLED_TEST_SETTLEMENT` and `WAIVED`. Preserve external-funds, revenue, validation and authority flags separately and bind settlement to case + quote + product + source lineage. | Test settlement can unlock a controlled test without becoming revenue; real settlement emits exactly one fulfilment-release eligibility event. |
| **4. Universal Fulfilment Contract** | Give every execution family one journey-facing interface | Freeze `FulfilmentRequest` and `FulfilmentResult`; build the adapter registry. Start with Sophia, then Evidex, VAMP, HOMS, Document Studio and NicheFoundry. Composite products may invoke multiple organs but return one final fulfilment result. | Journey Core has no product-specific business logic. New incarnations are bound mainly by profile/configuration. |
| **5. Deliverable Manifest & Release v2** | Stop assuming one product equals one PDF | Freeze `DeliverableManifest`: N artifacts, hashes, MIME types, purpose, customer visibility, proof and release conditions. Preserve SHA-bound human approval and one-use release authority. | PDF, ZIP, DOCX, XLSX, MP4, captions, images and mixed packs use the same release machinery without weakening authority. |
| **6. Vesper Journey Runtime** | Make Vesper the commercial face without making her the authority | Vesper consumes Journey State and emits only currently allowed conversational actions: request input, clarify scope, present quote, provide checkout, report processing, surface `NEEDS_YOU`, deliver approved outputs, close/follow-up. Add asynchronous return events. | Vesper can carry a customer through the lifecycle without stitched phrases, hidden state guesses or conversation-derived authority. |
| **7. Organ Adapter Gauntlet** | Prove the spine against the organism | Run golden journeys for Sophia Review, Evidex Evidence Pack, VAMP Snapshot, HOMS assessment/marking, HOMS Learning pack, Document Studio transformation and NicheFoundry media/campaign fulfilment. | Each family reaches delivery through the same Journey Core and returns valid receipts without customer-flow hacks. |
| **8. 68-Product Binding & Final Commercial Gauntlet** | Bind the full portfolio | For every incarnation bind: product ID → fulfilment profile → required inputs → scope rules → price rules → organ composition → human gates → deliverable profile → release channels. Run static/schema validation over all 68 and controlled/live exemplars across representative classes. | **68/68 compile into the Customer Journey Spine**, with no duplicate commerce pipelines, unknown fulfilment routes or authority leakage. |

## The six canonical contracts

The programme converges commercial execution onto six contract families:

1. **`JourneyCase`** — who / what / where / current governed truth.
2. **`IntakeRequirement` + `ScopeReceipt`** — what DIO still needs / what work has been bounded.
3. **`Quote` + `SettlementReceipt`** — what was offered / what commercial condition was satisfied.
4. **`FulfilmentRequest`** — what the specialist organ is permitted and expected to do.
5. **`FulfilmentResult` + `DeliverableManifest`** — what was produced, with evidence, hashes and artifact semantics.
6. **`ReleaseAuthority` + `DeliveryReceipt`** — what may leave DIO / what actually reached the customer.

Everything else is an adapter, profile, authority receipt, evidence record or projection.

## Vesper law

```text
customer expression
        ↓
Vesper interprets intent
        ↓
Journey Core exposes current truth + permitted actions
        ↓
Vesper communicates naturally
        ↓
customer action
        ↓
Journey Core transitions deterministically
```

Vesper may understand that “yes, go ahead” expresses acceptance, but only the Journey Core may establish what object is currently accept-able and whether `ACCEPT_QUOTE` is an available action. Natural conversation therefore never substitutes for deterministic authority.

## Authority law

The Journey Spine must preserve DIO's separation of:

- evidence;
- world state;
- commercial state;
- professional/legal readiness;
- capability leases;
- execution identity;
- human decision authority;
- release authority;
- delivery evidence.

No aggregate `approved=true` is permitted to collapse those layers.

## Reference specimen: Sophia

A narrow Sophia reviewer-routing correction may be made as the Phase 0/1 reference specimen because the current known failure is classification/routing related. It must not become a new Sophia-specific commerce architecture.

```text
correct Sophia reviewer execution contract
→ prove the long-form review route
→ stop Sophia-specific customer-flow growth
→ build Journey Core contracts
→ wrap Sophia behind the universal fulfilment adapter
→ repeat for the other execution families
```

## Final commercial gauntlet

The final proof should admit a brand-new customer and preserve one canonical journey across surfaces:

```text
public surface
→ customer asks about product
→ Vesper explains from governed product truth
→ customer requests work
→ missing input requested
→ file arrives via Telegram / email / web
→ same canonical case
→ source hashed and custody preserved
→ scope derived
→ grounded quote presented
→ quote accepted
→ settlement verified
→ specialist fulfilment queued
→ governed execution completes
→ deliverable manifest created
→ human / release gate
→ Vesper returns proactively
→ approved artifacts delivered
→ delivery receipt
→ case CLOSED
```

Then swap the fulfilment family without changing the outer journey. Sophia, VAMP, Evidex and HOMS should differ in product profile and fulfilment adapter, not in commerce plumbing.

## Sequencing freeze

```text
Phase 0
→ narrow Sophia reference correction
→ Phase 1
→ Phase 2
→ Phase 3
→ Phase 4
→ Phase 5
→ Phase 6
→ Phase 7 organ gauntlet
→ Phase 8 full 68-product binding
```

Do not fan out into 68 bespoke integrations before the universal fulfilment contract exists.

## Programme success condition

DIO succeeds when 68 incarnations ride a small set of proven execution families through one surface-neutral, evidence-bound and authority-separated customer journey. The number of products must scale by manifest/profile binding, not by multiplying bespoke orchestration code.
