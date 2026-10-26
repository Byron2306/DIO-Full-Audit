# DIO Customer Journey Spine — Phase 4 Universal Fulfilment Contract

Status: **PASS / VERIFIED**

Acceptance: `DIO_CUSTOMER_JOURNEY_PHASE4_UNIVERSAL_FULFILMENT_CONTRACT_VERIFIED`

Branch: `agent/dio-customer-journey-phase4`

## Objective

Phase 4 gives Journey Core one stable fulfilment interface while preserving specialist product and organ choreography behind bounded adapters.

The governing law is:

> Journey Core may know the fulfilment contract and the compiled execution profile. It must not know the internal call graph of a product.

A product may internally invoke one organ or many organs. The Journey Spine sees one governed request and one governed result.

## Canonical contracts

Phase 4 introduces three contracts.

### `dio.fulfilment_execution_profile.v1`

A deterministic projection from canonical `dio.compiled_product.v1` truth into the fulfilment seam.

It binds:

- canonical compiler product identity;
- current Journey product identity projection;
- composition fingerprint;
- compilation fingerprint;
- explicit adapter identity and version;
- resolved execution-capability/provider lineage;
- compiler execution gate;
- compiled output plan;
- explicit no-release/no-send/no-generic-authority boundaries;
- `execution_profile_sha256`.

The projection accepts compiler execution state `ALLOW` or `NEEDS_YOU`. `NEEDS_YOU` remains compatible because the Journey invocation itself is an explicit bounded initiation event. `REFUSE` and `NEEDS_IMPLEMENTATION` cannot be projected into an executable fulfilment profile.

The projection does not modify the canonical compiler schema and does not create an executor or authority that the compiler did not already resolve.

### `dio.fulfilment_request.v1`

A request can be created only when the canonical JourneyCase is at `PAYMENT_VERIFIED` and carries all of the following compatible truth:

- sufficient Phase 2 `dio.scope_receipt.v1`;
- customer-presentable Phase 2 `dio.customer_quote.v2`;
- Phase 3 `dio.settlement_receipt.v1` with `fulfilment_eligible = true`;
- a hash-valid fulfilment execution profile for the same Journey product.

The request binds:

- `case_id`;
- Journey product identity;
- `scope_receipt_sha256`;
- `quote_id` and `quote_truth_sha256`;
- settlement class and `settlement_receipt_sha256`;
- `execution_profile_sha256`;
- adapter identity/version;
- the immutable execution-profile projection;
- explicit no-release/no-send/no-generic-authority boundaries;
- `fulfilment_request_sha256`.

Creation advances the strict Journey lifecycle:

```text
PAYMENT_VERIFIED
    ↓
WORK_QUEUED
```

### `dio.fulfilment_result.v1`

Every bounded adapter returns through one result envelope regardless of internal organ composition.

The result binds:

- canonical case and Journey product identity;
- original fulfilment-request hash;
- execution-profile hash;
- adapter identity/version;
- completion status;
- artifact descriptors;
- evidence/proof references;
- internal organ-step lineage;
- explicit no-release/no-send/no-generic-authority boundaries;
- `fulfilment_result_sha256`.

A successful result advances:

```text
WORK_QUEUED
    ↓
PROCESSING
    ↓
REVIEW_READY
```

The canonical case stores both the request and result under its fulfilment state.

## Adapter dispatch boundary

Dispatch is keyed only by `adapter_id` from the execution profile.

The adapter registry is supplied explicitly to the fulfilment seam. This keeps dispatch deterministic and testable and avoids a hidden mutable global registry.

Journey Core does not branch on `product_id`.

The Phase 4 gauntlet proves the same adapter can serve two different product identities without product-specific Journey logic.

Composite adapters are equally valid: an adapter may report multiple internal organ steps while still returning one canonical fulfilment result.

## Authority boundary

Adapters are treated as untrusted at the universal seam.

Phase 4 refuses an adapter that attempts to assert any of:

- release authority;
- external-send authority;
- generic authority.

Artifact descriptors must remain:

`release_state = HELD`

Therefore Phase 4 completion means **specialist work reached governed review-ready state**. It does not mean the work may be delivered to the customer.

Phase 5 owns DeliverableManifest and release-authority semantics.

## Existing fulfilment code

The existing `presence_core/fulfilment_egress.py` remains specialist/reference plumbing. It contains Sophia-specific local fulfilment and review-ready output preparation and is not redefined as the universal Journey API.

Likewise, `presence_core/fulfilment_release.py` remains a later release concern. Phase 4 does not widen or bypass its release gates.

Future bounded adapters may wrap existing specialist pipelines while presenting the universal Phase 4 request/result contract outward.

## Product compiler relationship

The existing product compiler already provides the correct upstream constitutional boundary:

- products request capabilities, not organs;
- providers are resolved deterministically;
- execution-required capability resolution is explicit;
- composition and compilation are fingerprinted;
- execution gates remain typed.

Phase 4 consumes that truth rather than inventing a second product-routing system.

A fulfilment execution profile therefore acts as a narrow adapter projection over compiler truth, not as a replacement compiler.

## Current product-identity compatibility projection

The current commercial Journey Spine stores its canonical product reference as the human-readable 68-product name, while canonical compiled manifests use machine product IDs.

Phase 4 therefore projects:

`compiled product name -> Journey product identity`

while retaining the machine `compiled_product_id` separately.

This is an explicit compatibility seam, not an assertion that name matching is the final portfolio identity model. Phase 8 owns the complete 68-product binding and can replace this projection with an explicit canonical mapping without changing the universal fulfilment contract.

## Sophia boundary

Phase 4 does **not** claim that the live Sophia 7070 reviewer-routing concern is resolved.

The repository contains a reviewer-oriented academic-review adapter and a separate live routing smoke, but that is not yet equivalent to a verified production representative-review route.

Sophia therefore remains gated from production universal-adapter activation until that live reviewer-routing proof is closed. This does not block freezing and verifying the universal fulfilment contract itself.

## TDD evidence

### RED

GitHub Actions run `35270101459` on pre-implementation head `f86c927e1f1a1ff0bc95e927f558ff639971dcbc` compiled the existing Phase 4 test contract and failed during collection exactly because the implementation did not yet exist:

```text
ModuleNotFoundError: No module named 'presence_core.fulfilment_contract'
1 error in 0.17s
```

### GREEN implementation head

GitHub Actions run `35270327390` on implementation head `8108d147998e393ab68147cfd9fee7d8f5a175aa` compiled the Phase 4 contracts and returned:

```text
......                                                                   [100%]
6 passed in 0.13s
```

The six tests prove:

1. fulfilment refuses a JourneyCase without canonical fulfilment-eligible settlement truth;
2. the request binds case, scope, quote, settlement and execution-profile lineage without creating authority;
3. one adapter can serve different products without product-specific Journey branching;
4. a composite adapter can expose multiple organ steps through one canonical result;
5. an adapter cannot self-grant release, send or generic authority;
6. successful dispatch drives the strict Journey lifecycle to `REVIEW_READY` and persists a HELD result.

## Exit gate

Phase 4 passes when all of the following are true:

- [x] one universal fulfilment request contract exists;
- [x] one universal fulfilment result contract exists;
- [x] compiled product fingerprints remain bound into execution profile truth;
- [x] execution-capability/provider lineage remains explicit;
- [x] adapter dispatch is explicit and product-agnostic at Journey level;
- [x] composite organ choreography is hidden behind one result envelope;
- [x] fulfilment requires Phase 3 eligibility truth;
- [x] strict Journey transitions remain authoritative;
- [x] adapter output cannot create release/send/generic authority;
- [x] all Phase 4 artifacts remain HELD;
- [x] existing specialist fulfilment/release code is preserved rather than bypassed;
- [x] Sophia live reviewer routing remains an explicit unresolved activation gate.

## Result

**PASS — Phase 4 Universal Fulfilment Contract is verified.**

Acceptance token:

`DIO_CUSTOMER_JOURNEY_PHASE4_UNIVERSAL_FULFILMENT_CONTRACT_VERIFIED`

This verifies the universal fulfilment seam and dispatch semantics. It does not claim every specialist organ has already been wrapped as a live adapter. The broad organ-adapter gauntlet remains a later programme phase.

The programme may proceed to **Phase 5 — Deliverable Manifest & Release v2** after exact current-head verification.
