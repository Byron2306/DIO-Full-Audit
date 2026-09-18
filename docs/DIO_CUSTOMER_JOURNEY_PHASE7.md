# DIO Customer Journey Spine — Phase 7 Organ Adapter Gauntlet

Status: **PASS / 8 OF 8 GOLDEN JOURNEYS VERIFIED**  
Branch: `agent/dio-customer-journey-phase7`  
Phase 8: **UNBLOCKED**  
Acceptance: `DIO_CUSTOMER_JOURNEY_PHASE7_ORGAN_ADAPTER_GAUNTLET_VERIFIED`

## Purpose

Phase 7 proves the shared Customer Journey Spine against the actual DIO organism rather than only contract fixtures.

The exit gate requires two proof levels for every representative family:

1. **ORGAN_EXECUTION_PROVED** — a current organ implementation executes on a clean runner, produces fresh artifacts, and those exact artifact bytes are SHA-256 sealed under the Phase 7 contract with `HELD` release state and no authority leakage.
2. **GOLDEN_JOURNEY_PROVED** — the real organ output is driven through the canonical shared journey: surface ingress, same-case cross-channel binding, source custody, intake, sufficient scope, grounded quote, typed settlement, family-level compiled execution profile, hash-bound fulfilment dispatch, manifest, exact human approval, one-use release authority, controlled delivery, delivery receipt, Vesper re-entry and case closure.

Both proof levels now pass for all eight representative families.

## Final scorecard

| Family | Representative commercial product | Organ execution | Golden journey | Current witness |
|---|---|---:|---:|---|
| Sophia Review | Sophia Review | **PROVED** | **PROVED** | Canonical `Byron2306/Sophia-AI@c1aa915560599f7d6cef0ff41e6a7b0787334376` booted Presence 7070 with Ollama `qwen2.5:0.5b`, executed live specialist review, sealed the fresh review witness, and closed the canonical journey. |
| Evidex | Evidex EvidenceOps | **PROVED** | **PROVED** | Canonical `Byron2306/Evidex@c2754b37ca32e803d84e733b5d59207fdcb17841` executed the Evidence Pack engine on a clean runner; fresh output bytes were sealed and delivered through the shared controlled journey. |
| VAMP | VAMP Performance | **PROVED** | **PROVED** | Repository-native VAMP snapshot executed against a fresh fixture database; current JSON and ZIP bytes entered the real request/profile hashes and reached `CLOSED`. |
| HOMS Assessment | HOMS Assess | **PROVED** | **PROVED** | Canonical `Byron2306/NoEdge-Multi-Hymark@a3ea3f627d860fc7b13e2d95f6632f914938c8de` executed the real assessment workflow; the current workflow artifact completed the canonical journey. |
| HOMS Learning | HOMS Learning Studio | **PROVED** | **PROVED** | The same canonical HOMS run completed LearningAgent persistence; current `knowledge_base.pkl` bytes were independently bound into a second canonical journey. |
| Document Studio | Document Studio Edit | **PROVED** | **PROVED** | Repository-native Document Studio executed a real Ollama `qwen2.5:1.5b` technical-edit lane, passed deterministic fact-preservation and Format Core completeness QA, produced a held review pack, sealed exact output bytes and closed the journey. |
| NicheFoundry | Campaign Lab | **PROVED** | **PROVED** | Pinned `Byron2306/NicheFoundry@7528d8cdee17c5b6fbe35236b71b8e2191bb108a` executed the canonical backend autopilot and bound fresh campaign artifacts into the shared journey. The repair commit remains an explicit pinned dependency rather than hidden trust. |
| Obligation / Assurance | GrantProof | **PROVED** | **PROVED** | Real `dio_grantproof` execution produced its six-file proof pack while preserving `NEEDS_YOU` human fulfilment and `REFUSE` external-release semantics; those exact bytes completed the controlled golden journey. |

**Organ execution proof: 8 / 8 families.**  
**Full golden journey proof: 8 / 8 families.**

## Canonical Phase 7 journey

Every final proof uses the same customer-lifecycle machinery:

```text
web surface ingress
  → canonical JourneyCase
  → explicit Telegram binding to the same case
  → controlled customer source captured through attachment quarantine
  → source SHA-256 bound into the execution profile
  → IntakeRequirement
  → sufficient ScopeReceipt
  → governed Quote or explicit operator quote approval
  → CONTROLLED_TEST_SETTLEMENT
  → Phase 7 family execution-profile compilation
  → FulfilmentRequest
  → real representative organ execution
  → SHA-bound FulfilmentResult
  → Vesper async re-entry on the preferred surface
  → DeliverableManifest
  → exact-manifest NEEDS_YOU approval
  → one-use ReleaseAuthority
  → injected controlled-test delivery
  → DeliveryReceipt
  → CLOSED
```

The controlled source and controlled delivery are lifecycle proofs, not claims that a real customer or public network endpoint participated in CI.

## Authority and commercial truth

The final acceptance run proves:

- `CONTROLLED_TEST_SETTLEMENT_ONLY=true`
- `EXTERNAL_FUNDS_MOVED=false`
- `EXTERNAL_NETWORK_SEND=false`
- no revenue recognition from the controlled gauntlet;
- no execution result creates release authority;
- exact manifest approval remains separate from fulfilment success;
- release authority is one-use and channel-bounded;
- customer-case closure follows a recorded delivery receipt;
- Vesper projects canonical journey truth and creates no authority.

Phase 7 therefore proves governed lifecycle plumbing and live organ execution. It does **not** claim market validation, real revenue, autonomous external delivery, professional/legal clearance, or Phase 8's 68-product manifest binding.

## Family-level compilation boundary

Phase 7 compiles a deterministic **family execution profile** from:

- the canonical 68-product commercial registry identity;
- the frozen Phase 7 family/adapter registry;
- exact adapter version and source path;
- exact external repository commit where applicable;
- customer-source custody SHA-256.

It deliberately records `canonical_product_manifest_binding = PHASE8_PENDING`.

That is not a loophole: Phase 7 proves the eight real organ families through the common spine. **Phase 8 remains responsible for binding all 68 product incarnations to their final product/compiler manifests and fulfilment profiles.** Phase 7 does not manufacture `dio.compiled_product.v1` objects to pretend that Phase 8 has already happened.

## Defects discovered and repaired by the gauntlet

### 1. Operator quote resume conflict

Journey Core permitted:

`NEEDS_YOU → QUOTE_READY`

but the lower customer-case persistence guard rejected the transition as numerically “backwards”.

Repair: preserve monotonic protection generally while explicitly permitting the typed quote-resume transition.

### 2. Phase 2 → Phase 4 product identity mismatch

Phase 2 scope truth correctly carries both a machine `product_id` and canonical `product_name`. Phase 4 incorrectly compared the machine ID to the JourneyCase commercial name.

Repair: Phase 4 validates the canonical product name while retaining the machine identifier as scoped product identity.

### 3. Upstream receipt hashes were shape-checked but not recomputed

Phase 4 previously checked that scope, quote and settlement digests looked like SHA-256 values without independently recomputing all three receipts at the fulfilment seam.

Repair: scope, quote and settlement receipts are now rehashed and rejected on mismatch before a `FulfilmentRequest` may be built.

### 4. Weak local-model Document Studio edits

Ollama could return structurally plausible edits with wrong paragraph IDs or dropped protected facts.

Repair: the local-provider bridge now conservatively quarantines unsafe paragraph edits. Missing, duplicated, misidentified or fact-dropping edits fall back to exact source text and emit high-severity QA flags. The downstream Document Studio validator remains unchanged and authoritative.

### 5. Format Core revised-title omission

When a technical edit legitimately changed the first title paragraph, Format Core's DOCX renderer always skipped that semantic title because it assumed the cover title was identical.

Repair: the renderer skips the first title block only when it is semantically identical to the cover title. A revised first title is rendered and semantic-completeness QA remains strict.

## Independent CI witness

Final passing Phase 7 push run:

- Run: `35290677179`
- Head: `78eb700cd13977351510a28f13ca4959bcbf949b`
- Conclusion: **success**

Successful jobs:

- shared Phase 7 contract, VAMP and Obligation/GrantProof proofs;
- canonical Evidex execution + golden journey;
- canonical HOMS Assessment + HOMS Learning execution + two golden journeys;
- canonical NicheFoundry execution + golden journey;
- live Document Studio Ollama execution + held review pack + golden journey;
- live Sophia 7070/Ollama specialist review + golden journey;
- final Phase 7 acceptance gate.

The final acceptance job emitted:

```text
ORGAN_EXECUTION_PROVED=8/8
GOLDEN_JOURNEY_PROVED=8/8
CONTROLLED_TEST_SETTLEMENT_ONLY=true
EXTERNAL_FUNDS_MOVED=false
EXTERNAL_NETWORK_SEND=false
DIO_CUSTOMER_JOURNEY_PHASE7_ORGAN_ADAPTER_GAUNTLET_VERIFIED
```

The shared-contract repairs were also revalidated by the dedicated Phase 2 and Phase 4 workflows on the final code line before this documentation closure.

## Phase 8 handoff

Phase 7 is complete.

Phase 8 may now begin the **68-Product Binding & Final Commercial Gauntlet**. Its job is not to rebuild these journeys. It must bind every verified product incarnation onto this already-proven spine and prove:

```text
product ID
→ journey archetype
→ fulfilment profile
→ required / optional inputs
→ scope rules
→ pricing profile
→ quote authority
→ settlement rules
→ final compiled organ composition
→ human / professional / legal gates
→ deliverable profile
→ release conditions
→ delivery channels
```

The Phase 8 exit gate remains:

> **68/68 products compile into the Customer Journey Spine with no bespoke commerce plumbing, no unknown fulfilment route and no authority leakage.**
