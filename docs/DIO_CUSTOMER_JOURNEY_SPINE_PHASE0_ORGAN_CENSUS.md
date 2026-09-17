# DIO Customer Journey Spine — Phase 0 Organ Census & Constitution Freeze

**Date:** 2026-09-17  
**Branch:** `agent/vesper-slice6-production-foundation`  
**Phase:** 0  
**Gate state:** `IN_PROGRESS`  
**Completion rule:** Do not emit `PASS` until the full 68-product portfolio resolves to a known execution composition.

## Purpose

Phase 0 establishes the vocabulary and system census that the Customer Journey Spine is allowed to build on. It deliberately does **not** add a second product architecture, rewrite the historical 53-product anchor, or place specialist organ names directly into canonical product manifests.

Existing DIO law already separates:

- product/incarnation composition truth;
- reusable work/META capability truth;
- cross-organ composition;
- authority and execution identity;
- specialist organ implementation;
- customer/public/operator surfaces.

Phase 0 joins those truths into one auditable census before Journey Core implementation begins.

## Source hierarchy

Phase 0 uses the following existing sources rather than inventing replacements:

1. `config/products/manifests/*.json` — canonical product/incarnation requirements and composition authority.
2. `config/portfolio/constitution.json` — product-factory constitutional vocabulary.
3. `config/dio_fusion_registry.json` — canonical system census, disposition and authority boundaries.
4. `config/dio_composition_profiles.json` — governed cross-organ composition paths.
5. `config/dio_vertical_executors.json` — bounded specialist execution providers.
6. `config/atlas/dio_meta_incarnation_crosswalk.csv` — immutable historical 53-product lineage anchor.
7. the frozen 15-product canon extension — additional portfolio truth required to resolve the target 68 without mutating the historical 53.
8. `config/dio_product_portfolio.json` and product-layer registries — newer product/profile truth where applicable.

If two sources disagree, Phase 0 records the conflict. It may not silently merge identities or promote a candidate into execution truth.

## Frozen definitions

### `surface`

A human-, customer-, operator- or machine-facing ingress/egress projection through which a journey can be observed or acted upon. A surface may render state and collect input but does not become journey identity, product identity or authority merely because a conversation occurred there.

Examples: public website, Telegram, email, voice, API, GoldenEye / Control Deck.

### `journey`

The surface-neutral, canonical commercial lifecycle of one customer case across intake, scope, quote, settlement, fulfilment, review, release, delivery and closure. A journey owns continuity and state transitions; it is not equivalent to a Telegram thread, email thread, browser session or Vesper conversation.

### `organ`

A governed reusable specialist system or shared DIO primitive that contributes typed semantics, evidence, challenge, transformation, orchestration or execution to a journey. An organ does not become a product merely because it is reusable, and it does not gain authority merely because it participates in a composition.

### `incarnation`

A governed product manifestation that binds a buyer job / product identity to reusable work patterns, META primitives, profiles, capability requirements, execution composition, human gates and deliverable semantics. An incarnation is **not** a private customer-flow implementation.

### `authority`

A typed, bounded permission or decision right issued by the appropriate human, organisation, policy/kernel or capability authority. Evidence, model confidence, commercial state, organ output and conversation intent are not authority by themselves.

### `deliverable`

A customer-visible or customer-releasable artifact set produced by governed fulfilment and described by typed artifact metadata, lineage, hashes, visibility and release conditions. A deliverable may contain one or many artifacts and is distinct from internal receipts, logs and intermediate state.

## Organ census

The Journey Spine uses the existing fusion dispositions rather than inventing a new hierarchy.

| Organ / system | Phase 0 role | Disposition | Customer Journey responsibility | Authority boundary |
| --- | --- | --- | --- | --- |
| **Vesper Presence** | ingress / egress presence | shared primitive | intent interpretation, natural conversation, journey projection, allowed-action rendering | Presence is not kernel, product or release authority. |
| **Sophia / Integritas** | epistemic/review organ | governed organ | claim lineage, revision ancestry, reviewed knowledge work; initial reference fulfilment family | Machine support does not become human authorship/professional authority. |
| **Evidex** | evidence/provenance organ | governed organ | claim-source mapping, provenance, evidence packs, unresolved evidence visibility | Evidence assembly does not certify unsupported claims. |
| **VAMP** | performance/attainment evidence organ | governed organ | evidence-to-task / objective mapping, attainment structures, review support | Human performance judgment remains human. |
| **HOMS** | education assessment organ | governed organ | assessment, rubric/curriculum binding, moderation and learning-family execution | Educator/institution controls final academic authority. |
| **Learning Studio** | learning-product composition family | governed product layer over reusable organs | learning packs, learner transformations and education deliverables | Does not create educator/institutional authority. |
| **Document Studio** | document transformation plane | shared primitive | governed format/document transformations, artifact lineage and QA | Transformation integrity does not imply semantic/professional approval. |
| **NicheFoundry** | media/campaign production organ | governed organ | creative/media transforms, campaign assets and asset lineage | Publication and spend require separate authority. |
| **Lingua** | language transformation infrastructure | shared primitive | terminology/language transformation for journey and fulfilment outputs | Meaning/certification remains separately reviewed. |
| **Format Core** | presentation/rendering infrastructure | shared primitive | output geometry, render profiles, customer-facing formatting | Presentation may not silently alter governed meaning. |
| **BEAST** | evidence memory / governed compute organ | governed organ | source-bound custody, evidence crystallisation and proof-first compute | Storage/compute does not grant promotion or execution authority. |
| **Seraph** | adversarial challenge organ | governed organ | manipulation/hostility/adversarial challenge receipts | Challenge can block; it cannot release or autonomously execute response actions. |
| **Metatron** | coherence / orchestration challenge organ | governed organ | dissent, coherence and orchestration signals | Cannot bypass Valinor or human gates. |
| **ARDA** | execution identity / attestation organ | governed organ | attested execution identity beneath capability authority | Identity/attestation is not permission to execute. |
| **Legalis** | prerequisite/readiness organ | shared primitive | identity, requirement, deadline and platform/legal prerequisite evidence | `ALLOW` means configured prerequisites satisfied, not legal clearance. |
| **Market Command** | commercial/marketing coordination primitive | shared primitive | campaign lineage, lead attribution, planning and measurement inputs to journey creation | Outreach, publication and spend remain separately authorised. |
| **Sensorium** | market observation organ | governed observation capability | source-bound market/world observation feeding product/commercial evidence | Observation does not create market truth, product authority or execution authority. |
| **Hivenance Phoenix** | hypothesis/economic validation organ | governed organ | hypothesis registry, cost-aware validation, temporal/adversarial promotion evidence | Economic evidence may refuse promotion; capital deployment remains independently gated. |
| **Valinor** | kernel authority | shared authority primitive | capability authorization at runtime boundary | Sole kernel authority; kernel permission is still not legal/business/release authority. |
| **Obligation Core** | reusable obligation execution primitive | shared product/work primitive | requirement/obligation extraction and evidence-bound obligation state used by multiple product families | Obligation state does not itself authorize legal interpretation, fulfilment or release. |

## Cross-organ constitutional path

The existing composition profile already expresses the key separation the Journey Spine must preserve:

```text
Vesper ingress
→ Sophia epistemic lineage
→ Evidex provenance
→ BEAST custody
→ Seraph challenge
→ Metatron coherence/dissent
→ framework / Legalis readiness as required
→ human authority
→ DIO capability lease
→ Valinor kernel authority
→ ARDA execution identity
→ bounded specialist executor
→ Vesper egress
```

Not every journey requires every organ. Product/incarnation profiles select the required composition. What is invariant is that no skipped organ or model output may impersonate an authority layer that the selected composition requires.

## Product-to-organ binding law

Canonical product manifests remain organ-agnostic. Phase 0 therefore defines a separate binding relation:

```text
product / incarnation
    + required work patterns
    + META primitives
    + domain/framework/authority/output profiles
    + capability requirements
        ↓
Journey Spine fulfilment profile
        ↓
primary fulfilment organ / execution family
    + secondary supporting organs
    + shared primitives
    + human / legal / kernel / release gates
        ↓
known execution composition
```

A product is Phase-0-resolved only when all of the following are explicit:

- canonical product/incarnation identity;
- portfolio lineage (`historical53` or `frozen15_extension`);
- primary fulfilment family;
- zero or more secondary specialist organs;
- required shared primitives;
- authority gates;
- expected deliverable class;
- no product-specific commerce pipeline.

## Portfolio preservation law

The historical ATLAS crosswalk remains **53 rows exactly**. Phase 0 must not edit it to obtain 68.

The target portfolio is derived as:

```text
historical canonical crosswalk: 53
+ frozen canon extension:       15
-----------------------------------
Customer Journey target:        68
```

The join must preserve source lineage for every row so future ATLAS-generated candidates cannot accidentally become part of the commercial 68 merely because they are mechanically composable.

## Phase 0 validation matrix

| Gate | Required state |
| --- | --- |
| frozen definitions exist | PASS |
| major organ census exists | PASS |
| existing fusion dispositions preserved | PASS |
| product manifests remain organ-agnostic | PASS |
| historical 53 anchor mutated | **FALSE** |
| frozen 15 extension source identified and pinned | REQUIRED |
| 68 unique product/incarnation IDs assembled | REQUIRED |
| 68/68 have primary fulfilment family | REQUIRED |
| 68/68 have authority boundary | REQUIRED |
| 68/68 have deliverable class | REQUIRED |
| bespoke commerce pipelines | **0** |
| unknown / mystery execution compositions | **0** |

## Current gate assessment

At this commit the vocabulary and organ census are frozen, and the existing cross-organ composition law is compatible with the Journey Spine. The branch also preserves the 53-row historical distinction.

**Phase 0 is intentionally not declared complete yet.** The remaining Phase 0 work is the authoritative machine-readable 68-product dependency model. That model must pin the frozen +15 source and resolve every row to a fulfilment family without rewriting canonical manifests or pretending the historical 53 is the whole live portfolio.

The next Phase 0 artifact is therefore:

```text
config/customer_journey_spine/phase0_product_organ_bindings.json
```

with a validator that refuses:

- count other than 68;
- duplicate product IDs;
- missing source lineage;
- unknown organ/system IDs;
- missing primary fulfilment family;
- authority creation by composition;
- mutation/replacement of the historical 53 anchor.

Only after that validator passes may Phase 0 emit:

```text
DIO_CUSTOMER_JOURNEY_SPINE_PHASE0_READY
```
