# DIO Customer Journey Spine — Phase 7 Organ Adapter Gauntlet

Status: **PARTIAL / ORGAN EXECUTION GAUNTLET VERIFIED IN PART**  
Branch: `agent/dio-customer-journey-phase7`  
Phase 8: **BLOCKED**

## Purpose

Phase 7 proves the shared Customer Journey Spine against the actual DIO organism rather than only contract fixtures.

This document deliberately distinguishes two proof levels:

1. **ORGAN_EXECUTION_PROVED** — a current organ implementation executed on a clean runner, produced fresh artifacts, and those artifact bytes were SHA-256 sealed under the Phase 7 contract with `HELD` release state and no authority leakage.
2. **GOLDEN_JOURNEY_PROVED** — the organ has additionally been driven by a canonical Customer Journey case through intake, scope, quote, settlement, compiled fulfilment dispatch, manifest, release authority, delivery receipt and closure.

A successful organ execution is necessary but is **not** by itself the Phase 7 exit gate.

## Current scorecard

| Family | Representative | Execution proof | Golden journey | Current evidence / blocker |
|---|---|---:|---:|---|
| Sophia Review | Sophia Review | BLOCKED | BLOCKED | Canonical live reviewer inference remains host-bound. DIO has the reviewer-routing correction, while the main Sophia repository exposes the 7070/Ollama runtime. These must be reconciled and exercised live before universal activation. |
| Evidex | Evidex EvidenceOps | **PROVED** | PENDING | Canonical `Byron2306/Evidex` commit `c2754b37ca32e803d84e733b5d59207fdcb17841` executed `evidence_pack_engine.cli generate` with AI disabled and produced a current evidence ZIP that passed Phase 7 byte custody. |
| VAMP | VAMP Performance | **PROVED** | PENDING | Repository-native VAMP snapshot pipeline executed against a fresh fixture database and produced current JSON + ZIP artifacts sealed by Phase 7. |
| HOMS Assessment | HOMS Assess | **PROVED** | PENDING | Canonical `Byron2306/NoEdge-Multi-Hymark` commit `a3ea3f627d860fc7b13e2d95f6632f914938c8de` executed the real demo WorkflowEngine. Assessment, moderation, reporting and data-save steps completed; current HTML/JSON/CSV/workflow artifacts were sealed. |
| HOMS Learning | HOMS Learning Studio | **PROVED** | PENDING | The same canonical HOMS run completed the LearningAgent step and persisted a current `knowledge_base.pkl`; the learning artifact and workflow receipt were separately sealed. |
| Document Studio | Document Studio transformation/publication | BLOCKED | BLOCKED | The current full edit/translation pipeline is provider-bound to configured Sophia/Gemini or NIM runtime. Format Core rendering alone is not being relabelled as a Document Studio proof. |
| NicheFoundry | Campaign / media fulfilment | **PROVED** | PENDING | Canonical NicheFoundry exposed a real ffmpeg voice-label bug during the gauntlet. Repair commit `7528d8cdee17c5b6fbe35236b71b8e2191bb108a` passed research → eSpeak narration → ffmpeg mix → proxy render → captions → thumbnail → render QA → Phase 7 byte sealing. Repair is isolated in NicheFoundry PR #4 and is not merged. |
| Obligation / Assurance | GrantProof representative | **PROVED** | PENDING | Real `dio_grantproof` runner produced its six-file proof pack. It preserved `NEEDS_YOU` human fulfilment and `REFUSE` external release, with no authority, waiver, legal opinion, award/permit decision or external effect created. |

**Organ execution proof: 6 / 8 families.**  
**Full golden journey proof: 0 / 8 families completed to the Phase 7 exit gate.**

## Phase 7 execution contract

The gauntlet contract is implemented in:

`presence_core/organ_adapter_gauntlet.py`

It defines the eight frozen families and the verdict vocabulary:

- `VERIFIED_NATIVE`
- `NEEDS_HOST`
- `NEEDS_BINDING`
- `REFUSE`

Current execution evidence must bind:

- exact family and adapter identity;
- adapter version;
- canonical fulfilment-request SHA-256;
- canonical execution-profile SHA-256;
- fresh execution state;
- current artifact bytes;
- SHA-256 for every artifact;
- `HELD` release state;
- non-empty execution evidence references;
- false release, external-send and generic authority.

Historical specimens, mocks and source-code presence do not qualify as current execution proof.

## Cross-repository execution law

Phase 7 may bind a canonical external organ repository, but only when the repository and commit are explicit.

Pinned canonical roots currently used:

| Family | Repository | Commit |
|---|---|---|
| Evidex | `Byron2306/Evidex` | `c2754b37ca32e803d84e733b5d59207fdcb17841` |
| HOMS Assessment | `Byron2306/NoEdge-Multi-Hymark` | `a3ea3f627d860fc7b13e2d95f6632f914938c8de` |
| HOMS Learning | `Byron2306/NoEdge-Multi-Hymark` | `a3ea3f627d860fc7b13e2d95f6632f914938c8de` |
| NicheFoundry | `Byron2306/NicheFoundry` repair branch | `7528d8cdee17c5b6fbe35236b71b8e2191bb108a` |

The external repository binding itself creates no trust. The clean runner still has to execute the pinned code and seal fresh artifacts.

## Independent CI witness

DIO Phase 7 Actions run:

`35286321879`

Head:

`416a77f5986f92ab5d2eb3d6c25ea8fc6bfd96da`

Conclusion:

`success`

The run independently passed four jobs:

- Phase 7 contract + repository-native proofs;
- canonical Evidex execution;
- canonical HOMS Assessment + Learning execution;
- canonical NicheFoundry media execution.

The NicheFoundry media proof completed in approximately 102 seconds and passed the exact current-artifact test.

## NicheFoundry defect found by the gauntlet

The first media run established a valid research-boundary refusal for an over-specific MediaWiki query. After correcting the test topic to the canonical entity `Rosetta Stone`, the gauntlet exposed a real ffmpeg filtergraph defect:

`[voice]` was consumed as the sidechain input and then reused by `amix`.

The repair introduces:

`asplit=2[voice_sidechain][voice_mix]`

so sidechain compression and final narration mixing consume independent streams.

The repair is isolated in:

`Byron2306/NicheFoundry#4`

It has **not** been merged by the Customer Journey programme.

## Remaining blockers

### Sophia

Required before `ORGAN_EXECUTION_PROVED`:

- boot the canonical 7070 Presence/Ollama runtime;
- carry forward the DIO product-review routing correction;
- run representative long-form product/manuscript review;
- prove zero generic-pedagogy misroute for the representative review lane;
- seal the current review artifact under the Phase 7 execution contract.

### Document Studio

Required before `ORGAN_EXECUTION_PROVED`:

- execute the real Document Studio transformation/publication lane with its configured provider runtime; or
- establish an already-existing provider-free Document Studio publication entrypoint that genuinely owns the family output.

A Format Core render by itself is insufficient because Phase 7 must prove the specialist family, not merely one shared renderer.

## Next gate: golden journey promotion

The six proved organs still use Phase 7 test-bound request/profile digests at the execution-evidence seam. The next work is to replace those placeholders with hashes generated by real Customer Journey contracts:

```text
JourneyCase
  → IntakeRequirement
  → sufficient ScopeReceipt
  → canonical Quote / governed operator gate
  → CONTROLLED_TEST_SETTLEMENT
  → compiled execution profile
  → FulfilmentRequest
  → real organ execution
  → FulfilmentResult
  → DeliverableManifest v2
  → exact-manifest human approval
  → one-use ReleaseAuthority
  → controlled test delivery
  → DeliveryReceipt
  → CLOSED
```

Only after every major family reaches that route may Phase 7 emit its final programme acceptance token and unblock Phase 8.

## Acceptance posture

Phase 7 is **not complete**.

The following final acceptance token is intentionally **NOT emitted** yet:

`DIO_CUSTOMER_JOURNEY_PHASE7_ORGAN_ADAPTER_GAUNTLET_VERIFIED`

Current verified statement:

> Six of the eight major fulfilment families have fresh, clean-run organ-execution proof under a shared SHA-bound, authority-negative Phase 7 contract. Sophia and Document Studio remain explicit blockers, and all six proved families still require promotion through complete canonical golden customer journeys before Phase 7 may pass.
