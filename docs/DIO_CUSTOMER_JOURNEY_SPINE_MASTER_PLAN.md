# DIO Customer Journey Spine — Master Programme

Status: **PROGRAMME COMPLETE / PHASES 0–8 VERIFIED**  
Branch basis: `agent/dio-customer-journey-phase8`  
Programme owner: DIO commercial organism  
Phase 0 acceptance: `DIO_CUSTOMER_JOURNEY_PHASE0_ORGAN_CENSUS_FROZEN`  
Phase 7 acceptance: `DIO_CUSTOMER_JOURNEY_PHASE7_ORGAN_ADAPTER_GAUNTLET_VERIFIED`  
Phase 8 acceptance: `DIO_CUSTOMER_JOURNEY_PHASE8_68_PRODUCT_BINDING_VERIFIED`

## Programme thesis

DIO will **not** wire 68 products individually to Vesper.

DIO will wire the major organs once to a shared **Customer Journey Spine**, then bind the 68 product incarnations to those organ contracts through profiles, compiled execution compositions and typed authority gates.

The outer customer journey remains stable even when the specialist fulfilment organ changes.

```text
surface ingress
    ↓
Vesper + Lingua
    ↓
Journey Core
    ↓
intake / scope / quote / settlement
    ↓
compiled product execution profile
    ↓
bounded fulfilment organ composition
    ↓
FulfilmentResult + DeliverableManifest
    ↓
release authority
    ↓
Vesper / email / web / API egress
    ↓
DeliveryReceipt + close
```

The intended commercial consequence is that 68 products become 68 governed manifests riding a small number of proven execution families rather than 68 separate commerce systems.

---

## Non-negotiable constitutional laws

1. **Vesper interprets and presents journey truth; she does not manufacture journey truth.**
2. **Organs perform bounded work; they do not own the customer lifecycle.**
3. **Surfaces transport the journey; they do not define commercial truth.**
4. **Products may declare requirements and fulfilment behaviour, but may not implement bespoke customer-journey plumbing.**
5. **The Journey Core dispatches compiled product execution profiles, not hard-coded organ call chains.**
6. **Learning may alter future recommendations; learning never grants new authority.**
7. **Authority remains explicit and typed. Execution success, payment, evidence, rendering, recommendation or learning does not imply authority.**
8. **Pricing evidence is not quote authority; payment is not fulfilment; fulfilment is not release; delivery is not customer value.**
9. **The historical 53-product anchor remains immutable history. The frozen 15-product extension remains a separate canon layer.**
10. **The Customer Journey Spine owns customer lifecycle truth only. It does not replace the Product Compiler, organ contracts, evidence plane or authority plane.**

---

## Canonical commercial truth hierarchy

The programme preserves the Phase 0 source-of-truth hierarchy:

1. `config/atlas/dio_meta_incarnation_crosswalk.csv` — historical 53-product anchor.
2. `products/canon_extension_product_grade.py` — frozen 15-product canon extension.
3. `products/commercial_pricing_registry.py` — explicit commercial profiles for all 68 unique products.
4. Canonical product manifests / Product Compiler — capability and profile requirements.
5. Product and organ adapters — bounded execution providers.
6. Customer Journey Spine — canonical customer lifecycle and commercial-case truth.

No later phase may mutate historical portfolio truth merely to simplify journey implementation.

---

## Frozen vocabulary

### Surface

A transport such as Telegram, web, email, voice, API or Control Deck/operator interaction. A surface carries a journey; it does not define it.

### Presence

Vesper. Presence interprets intent, renders deterministic journey truth conversationally and maps customer language onto currently permitted actions.

### Journey Core

The canonical customer/commercial case and lifecycle, independent of any one conversation, channel or surface.

### Product

A sellable compiled composition of capabilities, work patterns and profiles.

### Incarnation

A concrete named product variation proving or packaging the shared product factory in a particular domain.

### Fulfilment organ

A bounded specialist worker that performs governed customer work and returns a standard result.

### Shared organ

Reusable intelligence, evidence, rendering, challenge, governance, execution or authority machinery used by fulfilment organs.

### Deliverable

One or more customer-facing artifacts bound to hashes, evidence, purpose and release conditions.

### Authority

A separately typed permission. Authority may never be inferred merely because reasoning, payment, execution, rendering or learning succeeded.

---

## Organ census

### Market and demand sensing

- Sensorium
- Hivenance
- Market Command
- NicheFoundry market/campaign functions

These organs observe, hypothesise, rank opportunities, learn and support attribution. They do not create quote, spend, release or execution authority.

### Presence and interaction

- Vesper / Presence Core
- Lingua
- Telegram
- Web
- Email
- Voice
- Operator / Control Deck bindings

These organs provide interaction, semantic continuity and expression. Conversation identity is not canonical case identity.

### Journey and commerce

- Journey Case
- Intake
- Scope
- Quote
- Settlement / Commerce
- Fulfilment dispatch
- Release
- Delivery receipt

These components own canonical lifecycle truth.

### Primary fulfilment families

- Sophia
- Evidex
- VAMP
- HOMS
- HOMS Learning Studio
- Document Studio
- NicheFoundry
- Obligation / Assurance stack

### Shared intelligence, proof, execution and governance organs

- BEAST
- Lingua
- Format Core
- Evidex kernel
- Seraph
- Metatron
- Legalis
- Valinor
- ARDA
- Obligation Core

These are reusable organism capabilities. They must not silently become owners of commercial lifecycle state.

---

## Eight journey execution archetypes

All 68 products resolve to these journey-level fulfilment families:

| ID | Archetype | Typical fulfilment | Default authority posture |
|---|---|---|---|
| A | Assessment & learning | HOMS / HOMS Learning / Sophia learning lanes | educator or content review |
| B | Scholarly review & research | Sophia + Evidex / Format | authorship, processing and human-release gates |
| C | Evidence & performance | Evidex / VAMP | provenance and human-judgment boundary |
| D | Obligation, assurance & regulated trust | Obligation Core + Evidex + assurance/governance organs | professional, legal and typed authority gates |
| E | Document, publication & professional output | Document Studio + Lingua / Format | semantic, visual, language and release QA |
| F | Market & opportunity intelligence | Hivenance + Sensorium + NicheFoundry + Market Command | evidence-grade recommendation, no autonomous outreach/spend |
| G | Campaign, launch & media | NicheFoundry + Format / Document Studio + Market Command | editorial, publication and spend gates |
| H | Presence & case service | Vesper + Lingua over Journey Core | Journey Core and typed authority decide actions |

An archetype is a **journey adapter family**, not a replacement for Product Compiler composition. One product may invoke several internal organs while exposing one stable `FulfilmentRequest` / `FulfilmentResult` boundary to the Journey Core.

---

# Phased programme

## Phase 0 — Organ Census & Constitution Freeze

**Status: PASS / FROZEN**

### Objective

Establish what every major organ is, separate commercial lifecycle ownership from specialist execution, map all 68 products to known execution compositions, and freeze the vocabulary required by later phases.

### Completed work

- inventoried the major commercial, fulfilment, shared, governance and authority organs;
- preserved the historical 53-product anchor;
- preserved the frozen 15-product canon extension separately;
- reconciled the commercial portfolio to 68 unique products;
- classified the portfolio into eight execution archetypes;
- mapped every product to a primary organ composition;
- separated shared/governance organs from customer-lifecycle ownership;
- froze `surface`, `presence`, `journey`, `product`, `incarnation`, `fulfilment organ`, `shared organ`, `deliverable` and `authority` definitions;
- recorded the six universal contract targets;
- recorded known structural work for later phases.

### Exit gate

Every one of the 68 products resolves to a known execution composition. There is no mystery product that requires bespoke customer-journey plumbing.

### Acceptance

`DIO_CUSTOMER_JOURNEY_PHASE0_ORGAN_CENSUS_FROZEN`

Authoritative Phase 0 evidence: `docs/DIO_CUSTOMER_JOURNEY_PHASE0_ORGAN_CENSUS.md`.

---

## Reference correction — Sophia reviewer specimen

**Position in programme:** immediately after Phase 0 and before using Sophia as the universal-fulfilment reference adapter.

### Objective

Correct the known Sophia product-review routing problem in which product/manuscript review can be swallowed by generic pedagogy in the 7070 path.

### Rule

This is a **reference correction**, not permission to continue expanding Sophia-specific commerce code.

```text
fix Sophia reviewer execution contract
        ↓
prove representative long-form review works
        ↓
STOP Sophia-specific commerce integration growth
        ↓
continue shared Journey Spine programme
```

### Exit gate

A representative product/manuscript review routes into the correct Sophia reviewer execution contract and produces the expected anchored output without relying on product-specific customer-flow code.

---

## Phase 1 — Journey Core v1

### Objective

Make the customer case truly **surface-neutral**.

### Build

- introduce a canonical `JourneyCase` identity independent of conversation identity;
- introduce one-to-many surface/conversation bindings;
- support Telegram, web, email, voice, API and operator bindings as transports over the same case;
- preserve existing case history and successor/source lineage;
- define typed lifecycle stages and permitted transitions;
- expose deterministic `available_actions` for the Presence layer;
- define first-class events so a long-running fulfilment operation can return into the correct case.

### Core law

A conversation may bind to a case. A conversation may never *be* the case.

### Exit gate

One case can begin on web, receive an email attachment, continue on Telegram and later deliver by email while remaining one canonical journey with intact lineage.

---

## Phase 2 — Intake, Scope & Quote Contract

### Objective

Make Vesper know exactly when to ask, when scope is sufficient and when a quote may be presented.

### Build

Freeze and implement shared contracts:

- `IntakeRequirement`
- `ScopeReceipt`
- `QuoteRequest`
- `QuoteResult` / canonical `Quote`

Product or archetype profiles declare:

- required inputs;
- optional inputs;
- accepted input classes;
- sufficient-scope conditions;
- scope dimensions and units;
- pricing strategy;
- quote authority mode;
- autonomous quote ceiling where permitted.

Vesper consumes those declarations and renders them conversationally. She does not reconstruct them from chat memory.

### Exit gate

Vesper never asks for an input already supplied, never quotes before scope is sufficient and never invents price or scope from conversational inference.

---

## Phase 3 — Settlement & Commercial Truth

### Objective

Separate workflow progression from money truth.

### Build

Introduce typed settlement classes such as:

- `REAL_SETTLEMENT`
- `CONTROLLED_TEST_SETTLEMENT`
- `WAIVED`
- other explicit governed states where genuinely needed

Keep separately typed fields for:

- external funds moved;
- revenue / commercial recognition;
- market-validation eligibility;
- fulfilment eligibility;
- quote lineage;
- case identity;
- product identity;
- source/provider lineage.

### Core law

A workflow may proceed under an explicitly authorised controlled test without creating false revenue or payment truth.

### Exit gate

A controlled-test settlement can unlock only its authorised test path and can never appear as real revenue. A real settlement creates exactly the governed fulfilment-release eligibility event defined by the case and quote.

---

## Phase 4 — Universal Fulfilment Contract

### Objective

Give every specialist product organ one stable interface to the Journey Core.

### Build

Freeze:

- `FulfilmentRequest`
- `FulfilmentResult`

Build an adapter registry around **compiled product execution profiles**.

Reference adapter sequence:

1. Sophia
2. Evidex
3. VAMP
4. HOMS
5. HOMS Learning
6. Document Studio
7. NicheFoundry
8. Obligation / Assurance compositions

Composite products may invoke several internal organs but must return one canonical fulfilment result envelope.

### Core law

The Journey Core does not need to know the internal call graph of a product.

### Exit gate

A new incarnation can bind to the commercial journey primarily through profile/config plus a bounded fulfilment adapter, without adding product-specific business logic to Journey Core.

---

## Phase 5 — Deliverable Manifest & Release v2

### Objective

Stop assuming every product produces one PDF.

### Build

Replace the single-document release assumption with a `DeliverableManifest` supporting N artifacts. Each artifact records at minimum:

- artifact ID;
- filename / logical name;
- SHA / content hash;
- MIME type;
- purpose;
- customer visibility;
- provenance / proof binding;
- release conditions;
- source/derivation lineage as required.

Preserve:

- artifact-SHA-bound human approval;
- typed release authority;
- one-use release authority where applicable;
- delivery-channel constraints;
- proof of what actually left DIO.

### Exit gate

PDF, ZIP, DOCX, XLSX, MP4, captions, images and mixed multi-file packs use the same release machinery without weakening authority or custody.

---

## Phase 6 — Vesper Journey Runtime

### Objective

Make Vesper function as the natural commercial face over deterministic commercial state.

### Runtime model

```text
Customer says something
        ↓
Vesper interprets intent
        ↓
Journey Core exposes canonical truth + available actions
        ↓
Vesper communicates naturally
        ↓
Customer chooses / supplies / asks
        ↓
Journey Core validates and changes state
```

Vesper may render only actions currently exposed by canonical journey state, such as:

- request missing input;
- clarify scope;
- answer a product question;
- present a quote;
- accept a quote when permitted;
- provide checkout/payment instructions;
- report processing state;
- surface `NEEDS_YOU`;
- deliver approved outputs;
- close or follow up.

Long-running fulfilment returns through first-class async events linked to the canonical case, allowing Vesper to proactively re-enter the originating journey.

### Exit gate

Vesper can walk a customer through the full lifecycle without hand-stitched phrases, ambiguous “yes” logic or conversational state guesses.

---

## Phase 7 — Organ Adapter Gauntlet

### Objective

Prove the common spine against the actual organism rather than only contract fixtures.

### Golden journey families

Run at least one complete governed journey for:

- Sophia Review;
- Evidex Evidence Pack / EvidenceOps;
- VAMP Snapshot / evidence mapping;
- HOMS assessment / marking support;
- HOMS Learning pack;
- Document Studio transformation/publication;
- NicheFoundry media/campaign fulfilment;
- representative Obligation / Assurance product.

### Required proof per journey

Each golden journey should prove:

- surface ingress;
- canonical case binding;
- source/attachment custody;
- intake sufficiency;
- scope receipt;
- grounded quote;
- typed settlement state;
- compiled fulfilment dispatch;
- fulfilment result;
- deliverable manifest;
- human / authority gate where required;
- delivery;
- delivery receipt;
- case closure;
- no authority leakage.

### Exit gate

Each major fulfilment family reaches delivery through the same Journey Core and standard contract family without organ-specific customer-flow hacks.

---

## Phase 8 — 68-Product Binding & Final Commercial Gauntlet

**Status: PASS / 68 OF 68 PRODUCTS BOUND**  
**Acceptance: `DIO_CUSTOMER_JOURNEY_PHASE8_68_PRODUCT_BINDING_VERIFIED`**  
**Authoritative evidence: `docs/DIO_CUSTOMER_JOURNEY_PHASE8.md`**

### Objective

Bind the full verified portfolio to the shared Customer Journey Spine.

### Per-incarnation binding

For every product, freeze and validate:

```text
product ID
→ journey archetype
→ fulfilment profile
→ required / optional inputs
→ scope sufficiency rules
→ pricing profile
→ quote authority
→ settlement rules
→ compiled organ composition
→ human / professional / legal gates
→ deliverable profile
→ release conditions
→ delivery channel options
```

### Validation

- schema/static validation across all 68 products;
- no duplicate commerce pipelines;
- no unknown fulfilment routes;
- no product-owned journey lifecycle;
- no authority leakage;
- no silent portfolio drift from 53 + 15 truth;
- representative live/controlled end-to-end journeys across all archetypes.

### Exit gate

**68/68 products compile into the Customer Journey Spine with no bespoke commerce plumbing, no unknown fulfilment route and no authority leakage.**

**Exit gate result: PASS.** The verified Phase 8 registry resolves all 68 products across eight archetypes and ten fulfilment routes. Archetypes F and H received fresh controlled end-to-end proofs in Phase 8; A, B, C, D, E and G retain the exact pinned Phase 7 acceptance witness.

---

# The six canonical shared contracts

The full programme converges on six contract families.

## 1. JourneyCase

Owns:

- canonical case identity;
- customer / actor bindings;
- product intent;
- current journey stage;
- surface bindings;
- lineage;
- canonical journey truth;
- currently available actions.

## 2. IntakeRequirement + ScopeReceipt

Owns:

- what DIO still needs;
- which inputs have been satisfied;
- the bounded work definition;
- scope units and dimensions;
- provenance of the scope decision.

## 3. Quote + SettlementReceipt

Owns:

- what was offered;
- why the price/scope is grounded;
- quote authority;
- which commercial condition was actually satisfied;
- explicit distinction between real settlement and controlled test state.

## 4. FulfilmentRequest

Owns:

- what the specialist organ is permitted and expected to do;
- authoritative source inputs;
- scope;
- execution profile;
- case/product lineage;
- relevant authority envelope.

## 5. FulfilmentResult + DeliverableManifest

Owns:

- what work actually completed;
- result state;
- generated artifacts;
- hashes;
- provenance;
- evidence/proof bindings;
- release prerequisites.

## 6. ReleaseAuthority + DeliveryReceipt

Owns:

- which artifacts may leave DIO;
- which channel may be used;
- which human/authority decision permitted release;
- what actually reached the customer;
- delivery identity and timestamp / receipt lineage.

Everything else should be an adapter, profile, authority receipt, event or projection over these contracts.

---

# Presence semantics

Vesper must remain expressive while the state machine underneath remains deterministic.

Bad pattern:

```text
if customer_message_contains_yes and maybe_price_was_discussed:
    create_order()
```

Target pattern:

```text
journey.stage = QUOTE_READY
journey.available_actions = [
    ACCEPT_QUOTE,
    ASK_QUESTION,
    CHANGE_SCOPE,
]

customer: "Yes, go ahead."
        ↓
Vesper maps intent to ACCEPT_QUOTE
        ↓
Journey Core validates ACCEPT_QUOTE is currently permitted
        ↓
typed state transition
```

Natural language may be probabilistic. **Authority and lifecycle transitions are not.**

---

# Final success gauntlet

The programme is complete only when an unfamiliar customer can traverse a real representative journey without hidden operator stitching.

Reference path:

```text
Facebook / site / public discovery
→ "What does Sophia Review do?"
→ Vesper explains canonical product truth
→ customer requests a manuscript review
→ Vesper requests only missing inputs
→ source arrives by Telegram / email / web
→ same canonical case
→ source is hashed and custody-bound
→ scope derived and receipted
→ grounded quote produced
→ customer accepts
→ settlement verified
→ Sophia queued asynchronously through universal fulfilment
→ anchored review completes and validates
→ DeliverableManifest created
→ human / release gate
→ Vesper proactively returns to the originating journey
→ approved files delivered
→ DeliveryReceipt written
→ case CLOSED
```

Then repeat the outer journey with:

- VAMP;
- Evidex;
- HOMS;
- Document Studio;
- NicheFoundry;
- Obligation / Assurance.

If the outer journey remains invariant and only the compiled product profile and fulfilment adapter change, the programme has achieved its architectural goal.

---

# Programme sequencing

Canonical order:

```text
Phase 0 — Organ Census & Constitution Freeze        PASS / FROZEN
    ↓
Sophia reference reviewer correction
    ↓
Phase 1 — Journey Core v1
    ↓
Phase 2 — Intake, Scope & Quote Contract
    ↓
Phase 3 — Settlement & Commercial Truth
    ↓
Phase 4 — Universal Fulfilment Contract
    ↓
Phase 5 — Deliverable Manifest & Release v2
    ↓
Phase 6 — Vesper Journey Runtime
    ↓
Phase 7 — Organ Adapter Gauntlet
    ↓
Phase 8 — 68-Product Binding & Final Commercial Gauntlet
```

Do not jump directly to individually wiring the full 68 before the universal fulfilment seam exists. Product-specific integration growth before Phase 4 creates exactly the duplicate plumbing this programme is intended to eliminate.

---

# Programme-wide invariants

Every phase must preserve all of the following:

- `ALLOW` never means legal clearance unless an actual legal authority says so;
- `PASS` never implies market validation;
- evidence never silently creates execution authority;
- execution never silently creates release authority;
- learning never silently modifies production authority;
- settlement truth cannot be fabricated to advance workflow;
- conversation memory cannot become commercial truth merely because it sounds plausible;
- external send/publication/spend remains separately authorised;
- source and artifact hashes remain bound through fulfilment and release;
- the 53 historical products and 15 canon extensions remain separately auditable;
- maturity classification remains separate from journey compatibility;
- one successful reference product cannot promote another product's maturity by analogy.

---

# Phase acceptance ledger

| Stage | Status | Acceptance criterion |
|---|---|---|
| Phase 0 | **PASS / FROZEN** | 68/68 mapped to known execution archetypes and organ compositions; no mystery commerce path |
| Sophia reference correction | Pending | product/manuscript reviewer route isolated and proven |
| Phase 1 | Pending | one canonical case survives cross-surface journey |
| Phase 2 | Pending | deterministic intake/scope/quote without chat-state invention |
| Phase 3 | Pending | typed settlement truth separated from workflow progression |
| Phase 4 | Pending | stable universal fulfilment request/result seam across specialist organs |
| Phase 5 | Pending | multi-artifact delivery and SHA-bound release authority |
| Phase 6 | Pending | Vesper completes lifecycle as projection over Journey Core truth |
| Phase 7 | Pending | each major fulfilment family passes the common journey gauntlet |
| Phase 8 | Pending | 68/68 bind and validate with no duplicate commerce pipelines or authority leakage |

---

# Immediate next action

With Phase 0 frozen, the next implementation specimen is the **Sophia reviewer execution correction**, followed by **Phase 1: surface-neutral Journey Core v1**.

The Sophia correction must remain deliberately narrow. Its purpose is to ensure the reference fulfilment lane is sound before the generic Journey Core and universal fulfilment contracts are built. It is not a reason to add more Sophia-specific commerce plumbing.

---

## Related authoritative documents

- `docs/DIO_CUSTOMER_JOURNEY_PHASE0_ORGAN_CENSUS.md` — frozen Phase 0 organ/product binding evidence.
- `docs/DIO_PRODUCT_CONSTITUTION.md` — product constitution.
- `docs/DIO_COMMERCIAL_OPERATING_PLAN.md` — broader commercial operating context.
- `docs/DIO_PRESENCE_ARCHITECTURE.md` — Presence/Vesper architecture context.
- `docs/DIO_LINGUA_SHARED_ORGAN_AND_BEAST.md` — Lingua/shared-organ boundary context.
- `docs/METATRON_COMMERCIAL_ORCHESTRATION_AUDIT.md` — orchestration audit context.
- `docs/DIO_LEGALIS.md` — legal-readiness boundary.
- `products/commercial_pricing_registry.py` — portfolio pricing and quote-policy source.
- `config/atlas/dio_meta_incarnation_crosswalk.csv` — historical 53-product anchor.
- `products/canon_extension_product_grade.py` — frozen 15-product extension.

---

**Master programme rule:** build the commercial spine once, bind the organs once, and let governed product incarnations ride those contracts. The portfolio scales by composition, not by copying customer pipelines.
