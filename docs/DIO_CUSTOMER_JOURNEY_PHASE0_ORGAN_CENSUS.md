# DIO Customer Journey Spine — Phase 0 Organ Census

Status: **PASS / FROZEN**  
Branch basis: `snapshot/dio-spine-2026-09-17`  
Purpose: freeze the organ/product/customer-journey constitution before Phase 1 Journey Core implementation.

## Acceptance token

`DIO_CUSTOMER_JOURNEY_PHASE0_ORGAN_CENSUS_FROZEN`

## Phase 0 conclusion

DIO does **not** need 68 bespoke Vesper/customer pipelines.

The verified commercial portfolio resolves as:

```text
53 historical canonical incarnations
+ 15 frozen canon extensions
= 68 unique commercial products
```

Every product can be classified into one of eight customer-journey execution archetypes. No product requires a separate customer-journey protocol. Product-specific differences belong in profiles, compiled fulfilment composition, intake/scope declarations, pricing rules and authority gates.

This is an architecture classification only. It does not promote the maturity of products whose source maturity is candidate, seeded, internal or unproved, and it does not imply market validation or external-release authority.

---

## Source-of-truth hierarchy

Phase 0 freezes the following source hierarchy:

1. `config/atlas/dio_meta_incarnation_crosswalk.csv` — immutable historical **53-product** anchor.
2. `products/canon_extension_product_grade.py` and its verified summary/proof machinery — frozen **15-product** canon extension.
3. `products/commercial_pricing_registry.py` — explicit commercial profile for all **68 unique products**.
4. Canonical product manifests / compiler — capability and profile requirements; manifests do not hard-code organ implementations.
5. Product/organ adapters — bounded implementation providers.
6. Customer Journey Spine — customer lifecycle truth only; it does not replace product composition truth.

The pricing registry must continue to reject drift if the 53 historical rows, 15 extension rows, or explicit 68 pricing profiles cease to reconcile.

---

## Governing commercial architecture

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
Compiled Product Execution Profile
        ↓
Bounded organ composition
        ↓
FulfilmentResult + DeliverableManifest
        ↓
Release authority
        ↓
Vesper / email / web / API egress
        ↓
DeliveryReceipt + close
```

---

## Constitutional definitions

- **Surface** — Telegram, web, email, voice, API, Control Deck or another transport. A surface carries the journey; it does not define commercial truth.
- **Presence** — Vesper. Vesper understands intent and presents journey truth. Vesper does not manufacture scope, price, settlement, fulfilment success or authority.
- **Journey Core** — canonical customer/commercial case and lifecycle, independent of any one conversation or surface.
- **Product** — sellable compiled composition of capabilities, work patterns and profiles.
- **Incarnation** — concrete named product variation proving the shared factory in a particular domain.
- **Fulfilment organ** — bounded specialist worker that performs governed customer work and returns a result.
- **Shared organ** — reusable intelligence, evidence, rendering, challenge, governance or execution machinery used by fulfilment organs.
- **Deliverable** — one or more customer-facing artifacts bound to proof and release conditions.
- **Authority** — separately typed permission. Successful reasoning, execution, payment, rendering or learning does not create authority by implication.

## Frozen design laws

1. **Vesper interprets and presents journey truth; she does not manufacture journey truth.**
2. **Organs perform bounded work; they do not own the customer lifecycle.**
3. **Surfaces transport the journey; they do not define it.**
4. **Products may declare requirements and fulfilment behaviour, but may not implement bespoke customer-journey plumbing.**
5. **The Journey Core dispatches compiled product execution profiles, not hard-coded organ call chains.**
6. **Learning may change future recommendations; learning never grants new authority.**
7. **Anything may be transformed or represented differently except authority, which must remain explicit and typed.**
8. **Pricing evidence is not quote authority; payment is not fulfilment; fulfilment is not release; delivery is not customer value.**

---

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

Role: customer communication, intent interpretation, semantic continuity and expression. Surface/conversation identities bind to a case; they do not define case identity.

### 3. Journey and commerce

- Journey Case
- Intake
- Scope
- Quote
- Settlement / Commerce
- Fulfilment dispatch
- Release
- Delivery receipt

Role: canonical customer lifecycle and commercial truth.

### 4. Primary fulfilment organs

| Organ | Fulfilment role | Typical inputs | Typical outputs | Human / authority posture |
|---|---|---|---|---|
| Sophia | review / diagnostic / research | manuscript, research question, bounded processing authority | anchored review, citation/claim audit, research pack | final release human-gated; remote processing separately authorised |
| Evidex | evidence assembly | source set, evidence/job context | manifest, source list, evidence/proof pack | evidence sufficiency is not professional/legal judgment |
| VAMP | evidence mapping / coverage | institutional profile, objectives, evidence | coverage snapshot, gaps, mappings | not an employee rating or employment decision |
| HOMS | assessment support | learner work, rubric/memo/guide | marking/assessment support | educator owns final marks and feedback |
| HOMS Learning | learning-content production | curriculum/domain/source profile | guides, worksheets, assessments, lessons, media | educator/content review as configured |
| Document Studio | transformation / publication | source document, service, language/domain profile | edit, translation, conversion, redline, rendered assets | translation requires proficient human review |
| NicheFoundry | campaign / media production | brief, product truth, audience/offer profile | campaign/content/media packs | publication and spend remain separately gated |
| Obligation / Assurance stack | proof / readiness / regulated assurance | requirements, controls, evidence, authority profile | proof/readiness/assurance packs | no legal/regulatory/award authority created by the pack |

### 5. Shared intelligence, proof and execution organs

| Organ | Role in the spine | Must not become |
|---|---|---|
| BEAST | evidence custody, crystallisation, reusable verified capability/evidence memory | execution or market-validation authority |
| Lingua | semantic continuity, multilingual meaning, conversation semantics and expression | commercial-state authority |
| Format Core | canonical semantic content → PDF/DOCX/HTML/site/media projection | source of substantive truth or release authority |
| Evidex kernel | evidence sufficiency/provenance support | automatic professional judgment |
| Seraph | adversarial challenge / dissent pressure | final authority |
| Metatron | coherence, reconciliation and integration support | final authority |
| Legalis | typed prerequisite readiness over identity, evidence, operator checks and deadlines | legal clearance merely because prerequisites pass |
| Valinor | kernel-level authority binding | evidence or recommendation |
| ARDA | attested execution identity | permission to execute merely because an executor exists |

---

## Eight execution archetypes

The 68-product portfolio closes over eight journey-level fulfilment archetypes.

| ID | Archetype | Canonical intake shape | Scope basis | Typical deliverable | Default gate posture |
|---|---|---|---|---|---|
| A | Assessment & learning | scripts/content + rubric/curriculum/profile | learner, assessment, topic, curriculum unit | assessment/learning pack | educator/content review |
| B | Scholarly review & research | manuscript/question/source context | page, source, milestone, topic | anchored review/research pack | authorship + processing + human release |
| C | Evidence & performance | evidence set + objectives/claims/records | evidence item, objective, project/outcome | evidence/coverage pack | provenance + human judgment boundary |
| D | Obligation, assurance & regulated trust | obligations/controls/evidence/authority context | requirement/control/clause/system/incident | proof/readiness/assurance pack or room | professional/legal/authority gates as profile requires |
| E | Document, publication & professional output | source content + output/language/channel profile | page/document/package/site/output | document/publication/site/correspondence bundle | semantic/visual QA + release gate |
| F | Market & opportunity intelligence | market question/signals/sources/eligibility context | segment/scan/opportunity | research/opportunity/offer pack | evidence-grade + no autonomous outreach/spend |
| G | Campaign, launch & media | approved product truth + audience/channel/assets | campaign/channel/asset | campaign/media/launch pack | editorial/publication/spend gates |
| H | Presence & case service | customer interaction + case state + available actions | customer case / conversation binding | response/action projection / handoff | Journey Core and typed authority decide action |

The archetype is a **journey adapter family**, not a replacement for the product compiler. A product may compose several internal organs while exposing one archetype-compatible fulfilment request/result contract to the Journey Core.

---

## Complete 68-product journey binding

`Primary organs` below are architectural execution-family bindings. They do not claim that every candidate product has already reached production maturity.

### Historical 53

| # | Product | Source suite/family | Archetype | Primary organ composition |
|---:|---|---|---|---|
| 1 | HOMS Assess | Education & Research / HOMS | A | HOMS + Evidex/Format support |
| 2 | HOMS Exam | Education & Research / HOMS | A | HOMS + Format |
| 3 | HOMS Moderate | Education & Research / HOMS | A | HOMS + assurance review |
| 4 | HOMS Curriculum | Education & Research / HOMS | A | HOMS Learning + curriculum profiles |
| 5 | HOMS Learning Studio | Education & Research / HOMS | A | HOMS Learning + Document Studio/NicheFoundry as required |
| 6 | HOMS Accreditation | Education & Research / HOMS + META | D | HOMS + Evidex + assurance stack |
| 7 | Sophia Review | Education & Research / Sophia | B | Sophia + Evidex/Format |
| 8 | Sophia Research | Education & Research / Sophia | B | Sophia research lane + Evidex |
| 9 | Sophia Supervisor | Education & Research / Sophia | B | Sophia milestone/review lane |
| 10 | Sophia Integrity | Education & Research / Sophia + META | B | Sophia + assurance/challenge |
| 11 | Sophia Tutor | Education & Research / Sophia | A | Sophia learning lane + Lingua |
| 12 | VAMP Performance | Enterprise Operations / VAMP | C | VAMP + Evidex |
| 13 | PromotionProof | Enterprise Operations / VAMP | C | VAMP + Evidex |
| 14 | CPDProof | Enterprise Operations / VAMP | C | VAMP + Evidex |
| 15 | ProjectProof | Enterprise Operations / VAMP | C | VAMP + Obligation/Evidex |
| 16 | ImpactProof | Public & Programme Ops / VAMP | C | VAMP + Evidex |
| 17 | Evidex EvidenceOps | Evidence & Assurance / Evidex | C | Evidex |
| 18 | AuditProof | Evidence & Assurance / META | D | Evidex + assurance stack |
| 19 | VendorProof | Evidence & Assurance / META | D | Evidex + assurance/Legalis as profile requires |
| 20 | TenderProof | Public & Programme Ops / META | D | Obligation Core + Evidex + authority profile |
| 21 | GrantProof | Public & Programme Ops / META | D | Obligation Core + Evidex |
| 22 | DonorProof | Public & Programme Ops / VAMP + Evidex | D | VAMP + Evidex + Obligation Core |
| 23 | ProgrammeProof | Public & Programme Ops / VAMP + META | D | VAMP + Obligation/assurance stack |
| 24 | QualityProof | Evidence & Assurance / META | D | Evidex + quality/assurance stack |
| 25 | CertificationProof | Evidence & Assurance / META | D | Evidex + quality/assurance stack |
| 26 | PolicyProof | Evidence & Assurance / META | D | Obligation Core + assurance stack |
| 27 | ContractProof | Evidence & Assurance / META | D | Obligation Core + Evidex + Format |
| 28 | DiligenceRoom | Evidence & Assurance / META Room | D | Evidex + Room + Format |
| 29 | AssuranceRoom | Evidence & Assurance / META Room | D | assurance stack + Room |
| 30 | DIO AI Assurance | AI & Digital Trust / META + BEAST + Seraph | D | assurance stack + BEAST + Seraph |
| 31 | ModelProof | AI & Digital Trust / BEAST + META | D | BEAST + assurance/proof stack |
| 32 | Agent Authority | AI & Digital Trust / META Authority | D | authority profile + Valinor/ARDA boundary |
| 33 | ReleaseProof | AI & Digital Trust / BEAST + META | D | BEAST + assurance/authority stack |
| 34 | ChangeProof | AI & Digital Trust / BEAST + META | D | BEAST + Evidex/assurance stack |
| 35 | AI IncidentRoom | AI & Digital Trust / Seraph + META | D | Seraph + incident/assurance Room |
| 36 | CriticalAI Assurance | AI & Digital Trust / BEAST + Seraph + ARDA | D | BEAST + Seraph + authority/execution attestation |
| 37 | CyberAssurance | AI & Digital Trust / Seraph + META | D | Seraph + assurance stack |
| 38 | ControlDrift | AI & Digital Trust / META Assurance | D | monitoring + assurance stack |
| 39 | SupplierCyberProof | AI & Digital Trust / VendorProof + Seraph | D | VendorProof composition + Seraph |
| 40 | IncidentProof | AI & Digital Trust / Seraph + META | D | Seraph + proof stack |
| 41 | DORA Vendor Assurance | Evidence & Assurance / VendorProof + Legalis | D | VendorProof composition + Legalis |
| 42 | DIO RegOps | Public & Programme Ops / Legalis + META | D | Legalis + Obligation/authority stack |
| 43 | PermitProof | Public & Programme Ops / Legalis + META | D | Legalis + Obligation/authority stack |
| 44 | Document Studio Edit | Demand & Presence / Document Studio | E | Document Studio + Format |
| 45 | Document Studio Localize | Demand & Presence / Document Studio + Lingua | E | Document Studio + Lingua + BEAST/Format |
| 46 | Document Studio Publish | Demand & Presence / Format Core | E | Format Core + Document Studio |
| 47 | Accessible Publish | Demand & Presence / Format Core | E | Format Core + accessibility/quality checks |
| 48 | DossierOps | Demand & Presence / Document Studio + Room | E | Document Studio + Evidex/Room |
| 49 | Market Radar | Demand & Presence / NicheFoundry + Hivenance | F | Hivenance + NicheFoundry + Market Command |
| 50 | Opportunity Foundry | Demand & Presence / NicheFoundry + Hivenance | F | Hivenance + NicheFoundry |
| 51 | Offer Lab | Demand & Presence / NicheFoundry + Hivenance | F | Hivenance + NicheFoundry + assurance |
| 52 | Campaign Lab | Demand & Presence / NicheFoundry + Hivenance | G | NicheFoundry + Hivenance + Market Command |
| 53 | Vesper Desk | Demand & Presence / Vesper | H | Vesper + Lingua + Journey Core |

### Frozen 15-product canon extension

| # | Product | Commercial family | Archetype | Primary organ composition |
|---:|---|---|---|---|
| 54 | Article Publication | publication_professional | E | Document Studio + Format + Sophia/Evidex review as configured |
| 55 | Article Publication Studio | publication_professional | E | Document Studio + Format + NicheFoundry media as configured |
| 56 | Contract Desk | publication_professional | D | Obligation Core + Document Studio + Evidex |
| 57 | Corporate Readiness | readiness_assurance | D | Evidex + assurance/Legalis profile |
| 58 | EntrepreneurProof | opportunity_venture | C | Evidex/VAMP evidence-readiness composition |
| 59 | Finance Readiness | readiness_assurance | D | VAMP/Evidex + finance readiness composition |
| 60 | Finance Readiness Studio | readiness_assurance | D | VAMP/Evidex + Sophia/Document Studio finance composition |
| 61 | FundingFinder | opportunity_venture | F | Hivenance/market research + Evidex provenance |
| 62 | InvestorProof | opportunity_venture | C | Evidex/VAMP + investor evidence composition |
| 63 | Launch Studio | launch_orchestration | G | NicheFoundry + Document Studio/Format + Market Command |
| 64 | POPIA Readiness | readiness_assurance | D | Legalis + Evidex + privacy assurance profile |
| 65 | Professional Correspondence | publication_professional | E | Document Studio + Lingua/Format |
| 66 | Professional Correspondence Studio | publication_professional | E | Document Studio + Lingua/Format |
| 67 | Report & Pitch Studio | publication_professional | E | Document Studio + Format + Evidex/Sophia as configured |
| 68 | Site Studio | publication_professional | E | Document Studio + Format Core + NicheFoundry assets as configured |

### Census result

- Historical products mapped: **53 / 53**
- Canon extensions mapped: **15 / 15**
- Total mapped: **68 / 68**
- Unknown journey archetypes: **0**
- Products requiring bespoke customer-lifecycle code: **0**

---

## Archetype inheritance contract

Product rows should not duplicate all journey behaviour. Each product inherits the common journey contract from its archetype and supplies profile-specific declarations.

### A — Assessment & learning

**Intake:** learner work/content, rubric/curriculum/instructions.  
**Scope:** scripts, assessment packages, topics, curriculum units, milestones.  
**Fulfilment:** HOMS/Sophia learning composition.  
**Deliverables:** assessment support, feedback, learning packs, teaching assets.  
**Gate:** educator/content-owner review where consequential judgment is involved.

### B — Scholarly review & research

**Intake:** manuscript/question/sources and processing consent/authority.  
**Scope:** manuscript pages, sources, claims, milestones.  
**Fulfilment:** Sophia with evidence/provenance support.  
**Deliverables:** anchored diagnostic/research packs.  
**Gate:** authorship preservation, remote-processing authority where applicable, human release.

### C — Evidence & performance

**Intake:** evidence records/files plus objective/claim/project context.  
**Scope:** evidence item, objective, project/outcome, readiness item.  
**Fulfilment:** VAMP/Evidex composition.  
**Deliverables:** coverage/evidence/readiness packs.  
**Gate:** evidence sufficiency and human judgment boundaries remain explicit.

### D — Obligation, assurance & regulated trust

**Intake:** requirements/controls/clauses/evidence/system or incident context.  
**Scope:** requirement, clause, control, vendor, system, incident, programme.  
**Fulfilment:** Obligation/Evidex/assurance stack with Legalis/BEAST/Seraph/authority organs as required by profile.  
**Deliverables:** proof/readiness/assurance packs and evidence rooms.  
**Gate:** legal/professional decisions and consequential authority remain external typed gates.

### E — Document, publication & professional output

**Intake:** source content, language, audience, output/channel/accessibility profile.  
**Scope:** pages, words, documents, correspondence items, publication/site package.  
**Fulfilment:** Document Studio + Lingua/Format and optional review/evidence organs.  
**Deliverables:** DOCX/PDF/HTML/site/translation/redline/correspondence bundles.  
**Gate:** semantic/visual QA, human language review where required, release authority.

### F — Market & opportunity intelligence

**Intake:** market question, signal/source set, eligibility or opportunity criteria.  
**Scope:** market segment, scan, opportunity, offer variant.  
**Fulfilment:** Hivenance/Sensorium/NicheFoundry/Market Command research composition.  
**Deliverables:** opportunity/research/offer packs.  
**Gate:** observation is not demand; recommendation is not outreach/spend authority.

### G — Campaign, launch & media

**Intake:** approved product truth, audience, channel, offer, asset brief.  
**Scope:** campaign, launch channel, asset set.  
**Fulfilment:** NicheFoundry + Format/Document Studio + Market Command.  
**Deliverables:** campaign packs, media, video, captions, carousel, launch assets.  
**Gate:** editorial approval, external publication/send and spend separately authorised.

### H — Presence & case service

**Intake:** customer message/event plus canonical case state.  
**Scope:** customer case and current available actions.  
**Fulfilment:** Vesper + Lingua rendering over Journey Core truth.  
**Deliverables:** conversational response, request for missing input, quote presentation, status, delivery handoff.  
**Gate:** Vesper never promotes conversational inference into quote/payment/release/external-action authority.

---

## Commercial profile inheritance

All 68 products already have explicit governed commercial profiles in `products/commercial_pricing_registry.py`.

The Journey Spine therefore does **not** need product-specific quote code. It consumes the canonical pricing profile, which declares:

- eligible buyer classes;
- primary and secondary scope units;
- pricing model;
- governed reference band;
- enterprise pricing mode;
- autonomous quote ceiling;
- industrial-scale support;
- quote-authority mode (`bounded_estimate` or `operator_review`).

The registry also preserves these boundaries:

- reference pricing is a commercial hypothesis, not validated willingness to pay;
- quote issue authority is distinct from pricing evidence;
- invoice issue authority is false unless separately created;
- external send authority is false unless separately created;
- HiveNance/learning may propose pricing refinements but cannot mutate quote authority directly.

Therefore Vesper's pricing behaviour can be generic:

```text
sufficient scope
   ↓
canonical pricing profile
   ↓
pricing recommendation / governed reference
   ↓
quote authority policy
   ↓
QUOTE_READY or NEEDS_YOU
   ↓
Vesper presents canonical result
```

---

## Universal contract targets for Phase 1+

The census closes around six shared contracts:

1. `JourneyCase`
2. `IntakeRequirement` + `ScopeReceipt`
3. `Quote` + typed `SettlementReceipt`
4. `FulfilmentRequest`
5. `FulfilmentResult` + `DeliverableManifest`
6. `ReleaseAuthority` + `DeliveryReceipt`

The Journey Core should not directly orchestrate every internal organ. The stable seam is:

```text
Journey Core
    ↓
Compiled Product Execution Profile
    ↓
Bounded organ composition
    ↓
FulfilmentResult
```

---

## Structural findings queued for later phases

### Phase 1 — Journey Core

1. Current customer-case identity is derived from conversation identity. Target: independent case identity with one-to-many surface/conversation bindings.
2. A case must survive channel changes: web → email attachment → Telegram conversation → email delivery must remain one journey.
3. Journey state must expose deterministic `available_actions` for Vesper rather than relying on conversational guesswork.

### Phase 2 — Intake, scope and quote

4. Product/archetype profiles declare required inputs and sufficient-scope conditions.
5. Vesper asks only for missing inputs.
6. Quote generation consumes canonical scope and pricing policy; it does not infer commercial truth from chat text.

### Phase 3 — Settlement

7. Settlement truth and workflow progression must be separate typed concepts: real settlement, controlled test, waived/other explicit states.
8. External funds moved, revenue recognition, market-validation eligibility and fulfilment eligibility remain distinct.

### Phase 4 — Universal fulfilment

9. Major fulfilment organs need one standard request/result envelope.
10. Product-specific organ composition stays behind compiled product execution profiles.
11. Sophia's product-review role must be isolated from generic tutoring/pedagogy before it is used as the reference adapter.

### Phase 5 — Deliverable Manifest / Release

12. Current fulfilment release assumes a single PDF. Replace with multi-artifact `DeliverableManifest` containing per-artifact hash, MIME type, purpose, proof and release conditions.
13. Preserve artifact-SHA-bound human approval and one-use release authority.

### Phase 6 — Vesper runtime

14. Vesper becomes a projection over Journey Core truth and available actions.
15. Long-running fulfilment must return via first-class async events so Vesper can proactively re-enter the originating case and deliver the result.

---

## Phase 0 exit verification

| Gate | Result |
|---|---|
| Historical 53 preserved as historical anchor | PASS |
| Frozen 15 extension preserved separately | PASS |
| 68 unique commercial profiles present | PASS |
| Major organs classified | PASS |
| Shared/governance organs separated from customer lifecycle | PASS |
| All 68 products assigned a journey archetype | PASS |
| Missing journey archetype | NONE |
| Product requires bespoke quote/payment/release pipeline | NONE |
| Authority boundaries preserved by design | PASS |
| Phase 1 blockers explicitly recorded | PASS |

## Phase 0 result

**PASS — DIO Customer Journey Organ Census and 68-product journey binding are frozen.**

The implementation programme may proceed to **Phase 1: Surface-neutral Journey Core v1** without first building product-specific Vesper integrations.
