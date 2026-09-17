# DIO Customer Journey Spine — Phase 0 Organ Census

Status: **IN PROGRESS**  
Branch basis: `snapshot/dio-spine-2026-09-17`  
Purpose: freeze the organ/product/customer-journey constitution before Phase 1 Journey Core implementation.

## Phase 0 objective

DIO is not wiring 68 independent products to Vesper. Phase 0 identifies the smaller set of fulfilment archetypes and shared organs that the 68 product incarnations compose, then freezes the contract between those organs and one surface-neutral Customer Journey Spine.

The governing commercial architecture is:

```text
Market / demand sensing
        ↓
Surface ingress
        ↓
Vesper + Lingua
        ↓
Canonical Journey Case
        ↓
Intake → Scope → Quote → Settlement / authority
        ↓
Compiled product execution profile
        ↓
Bounded organ composition
        ↓
FulfilmentResult + DeliverableManifest
        ↓
Release authority
        ↓
Vesper / email / web / API egress
        ↓
Delivery receipt + close
```

## Constitutional definitions

- **Surface** — Telegram, web, email, voice, API, Control Deck or another transport. A surface carries the journey; it does not define commercial truth.
- **Presence** — Vesper. Vesper understands intent and presents journey truth. Vesper does not manufacture scope, price, settlement, fulfilment success or authority.
- **Journey Core** — the canonical customer/commercial case and lifecycle, independent of any one conversation or surface.
- **Product** — a sellable compiled composition of capabilities, work patterns and profiles.
- **Incarnation** — a concrete named product variation proving the shared factory in a specific domain.
- **Fulfilment organ** — a bounded specialist worker that performs governed customer work and returns a result.
- **Shared organ** — reusable intelligence, evidence, rendering, challenge, governance or execution machinery used by fulfilment organs.
- **Deliverable** — one or more customer-facing artifacts bound to proof and release conditions.
- **Authority** — a separately typed permission. Successful reasoning, execution, payment, rendering or learning does not create authority by implication.

## Frozen design laws

1. **Vesper interprets and presents journey truth; she does not manufacture journey truth.**
2. **Organs perform bounded work; they do not own the customer lifecycle.**
3. **Surfaces transport the journey; they do not define it.**
4. **Products may declare requirements and fulfilment behaviour, but may not implement bespoke customer-journey plumbing.**
5. **The Journey Core dispatches compiled product execution profiles, not hard-coded organ call chains.**
6. **Learning may change future recommendations; learning never grants new authority.**
7. **Anything may be transformed or represented differently except authority, which must remain explicit and typed.**

## Organ bands

### 1. Market and demand sensing

- Sensorium
- Hivenance
- Market Command
- NicheFoundry market/campaign functions

Role: observation, hypothesis generation, opportunity ranking, attribution and campaign intelligence. These systems may influence recommendations and future experiments, but do not widen commercial or execution authority.

### 2. Presence and interaction

- Vesper / Presence Core
- Lingua
- Telegram, web, email, voice and operator bindings

Role: customer communication, intent interpretation, semantic continuity and expression. Surface/conversation identity must bind to a case rather than define case identity.

### 3. Journey and commerce

- Customer Case
- Scope
- Quote
- Settlement / Commerce
- Fulfilment dispatch
- Release and delivery receipt

Role: canonical customer lifecycle and commercial truth.

### 4. Primary fulfilment organs

| Organ | Fulfilment archetype | Typical inputs | Typical outputs | Human / authority posture |
|---|---|---|---|---|
| Sophia | Review / diagnostic | manuscript, research question, approved sources / processing authority | anchored diagnostic review, citation/claim audit, review pack | final delivery human-gated; remote processing separately authorised |
| Evidex | Evidence assembly | source set, evidence/job context | evidence manifest, source list, proof/KPI skeleton, evidence pack | evidence sufficiency is not professional/legal judgment |
| VAMP | Evidence mapping / coverage | institutional profile, task/objective structure, evidence records | evidence coverage snapshot, gaps, candidate mappings | not an employee rating or employment decision |
| HOMS | Assessment support | learner batch, rubric/memo/guide, optional gradebook/instructions | marking support, feedback/assessment artifacts | educator approves final marks and feedback |
| HOMS Learning | Learning-content production | curriculum/domain inputs, source material, profile | guides, worksheets, assessments, lessons, media | educator/content review as configured |
| Document Studio | Document transformation | source document, service, language/domain profile | edit, translation, conversion, redline, QA and rendered assets | translation requires proficient human language review |
| NicheFoundry | Campaign / media production | campaign brief, product truth, audience/offer profile | campaign packs, copy, media, video, creative assets | human editorial/publication/spend gates remain separate |
| Obligation / Proof family | Deterministic proof compilation | source-bound requirements and evidence | structured proof/evidence packs across contract/tender/grant/permit/etc. | no legal/regulatory/award authority; external release separately gated |

## Shared intelligence, proof and execution organs

| Organ | Role in the spine | Must not become |
|---|---|---|
| BEAST | evidence custody, crystallisation, reusable verified capability/evidence memory | execution authority or market-validation authority |
| Lingua | semantic continuity, multilingual meaning, conversation semantics and expression | commercial state authority |
| Format Core | projection from canonical semantic content into PDF/DOCX/HTML/site/media forms | source of substantive truth or release authority |
| Evidex kernel | evidence sufficiency/provenance support | automatic professional judgment |
| Seraph | adversarial challenge / attack / dissent pressure | final authority |
| Metatron | coherence, reconciliation and integration support | final authority |
| Legalis | typed prerequisite readiness over identity, evidence, operator checks and deadlines | legal clearance merely because prerequisites pass |
| Valinor | kernel-level authority binding | evidence or recommendation |
| ARDA | attested execution identity | permission to execute merely because an executor exists |

## Emerging fulfilment architecture

The Journey Core should not directly orchestrate every internal organ. The intended seam is:

```text
Journey Core
    ↓
Compiled Product Execution Profile
    ↓
Bounded organ composition
    ↓
FulfilmentResult
```

A product manifest continues to describe **requirements** rather than hard-code organ implementations. The compiler/runtime resolves the bounded providers.

## Universal contract targets for later phases

Phase 0 does not implement these yet, but the census indicates six shared contracts are sufficient for the commercial spine:

1. `JourneyCase`
2. `IntakeRequirement` + `ScopeReceipt`
3. `Quote` + typed `SettlementReceipt`
4. `FulfilmentRequest`
5. `FulfilmentResult` + `DeliverableManifest`
6. `ReleaseAuthority` + `DeliveryReceipt`

## Structural findings already queued for Phase 1+

1. Current case identity is still derived from conversation identity. Target: an independent case with one-to-many surface/conversation bindings.
2. Current fulfilment release assumes a single PDF artifact. Target: multi-artifact `DeliverableManifest` with per-artifact hash, MIME type, purpose, proof and release conditions.
3. Major fulfilment organs do not yet share one standard request/result contract.
4. Vesper still contains too much product-specific conversation/state logic instead of projecting canonical journey state and available actions.
5. Settlement truth and workflow progression need separate types so controlled tests, waivers and real external payments cannot be conflated.
6. Async fulfilment completion must be first-class so Vesper can return proactively to the originating case after long-running work.

## Known verified portfolio extension

The frozen 15-product canon extension is:

1. Article Publication
2. Article Publication Studio
3. Contract Desk
4. Corporate Readiness
5. EntrepreneurProof
6. Finance Readiness
7. Finance Readiness Studio
8. FundingFinder
9. InvestorProof
10. Launch Studio
11. POPIA Readiness
12. Professional Correspondence
13. Professional Correspondence Studio
14. Report & Pitch Studio
15. Site Studio

These 15 are ProductGrade/proof verified in the snapshot, while commercial validation remains explicitly unproved and no authority/external effects are created by that verification.

## Remaining Phase 0 work

Phase 0 is not complete until the full verified 68-product portfolio is bound into execution families. For every incarnation the final matrix must record:

- product/incarnation ID and family;
- primary fulfilment archetype;
- secondary/shared organs;
- required intake;
- sufficient-scope dimensions;
- pricing/quote model;
- authority/consent prerequisites;
- execution profile;
- deliverable types;
- human review/release gate;
- supported egress surfaces.

### Exit condition

**PASS only when all 68 products resolve to a known execution family and no product requires bespoke customer-journey plumbing.**

If a product does not fit an existing archetype, Phase 0 must identify and define the missing archetype before Phase 1 begins.
