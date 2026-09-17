# DIO Customer Journey Spine Phase 4 — Universal Fulfilment Contract Implementation Plan

## Goal

Give Journey Core one stable, product-agnostic fulfilment interface while keeping specialist organ choreography behind bounded adapters selected by compiled execution profiles.

The core law is:

> Journey Core may know the fulfilment contract and the compiled execution profile. It must not know the internal call graph of a product.

## Existing truth preserved

Phase 4 builds on:

- Phase 1 canonical JourneyCase and strict lifecycle transitions;
- Phase 2 ScopeReceipt and canonical Quote truth;
- Phase 3 hash-bound SettlementReceipt and `fulfilment_eligible` truth;
- the existing product compiler, whose `dio.compiled_product.v1` output already contains composition fingerprints, capability plans, profile bindings, execution gates and output plans;
- the existing fulfilment/release code, which remains a later release/egress concern and is not replaced here.

## Scope

### Build

1. `dio.fulfilment_execution_profile.v1`
   - a bounded projection from compiled product truth into the fulfilment seam;
   - binds product identity, composition/compilation fingerprint, adapter ID/version, capability/provider lineage and output plan;
   - creates no authority.

2. `dio.fulfilment_request.v1`
   - binds canonical case, product, scope, quote and settlement lineage;
   - requires `PAYMENT_VERIFIED` plus a valid Phase 3 receipt with `fulfilment_eligible = true`;
   - binds exactly one execution profile;
   - creates no release authority.

3. `dio.fulfilment_result.v1`
   - one envelope returned by every adapter, including composites;
   - binds request hash, case/product/profile lineage;
   - supports held output artifact descriptors, evidence/proof references and internal organ-step lineage;
   - cannot create release or external-send authority.

4. Explicit adapter registry
   - dispatch is by `adapter_id` declared in the execution profile;
   - Journey Core never branches on `product_id`;
   - registry is passed explicitly for deterministic/testable dispatch rather than hidden mutable global state.

5. Journey integration
   - `PAYMENT_VERIFIED -> WORK_QUEUED -> PROCESSING -> REVIEW_READY` for successful completion;
   - the result is persisted under canonical case fulfilment state;
   - outputs remain HELD for Phase 5 release processing.

### Do not build

- no Phase 5 multi-artifact DeliverableManifest or release-authority redesign;
- no external send;
- no autonomous release;
- no changes to payment-provider transport code;
- no hardcoded Sophia/Evidex/VAMP/HOMS/NicheFoundry routing in Journey Core;
- no claim that the live Sophia 7070 reviewer-routing concern is resolved.

## TDD sequence

### RED contract

Add `tests/test_customer_journey_phase4.py` before production code. It must prove:

1. fulfilment refuses a case without canonical fulfilment-eligible settlement truth;
2. request lineage binds case/product/scope/quote/settlement/profile hashes and creates no authority;
3. two different product profiles can use the same adapter without product-specific Journey branching;
4. a composite adapter may report multiple internal organ steps but returns one canonical result envelope;
5. an adapter attempting to claim release/send/authority is refused;
6. successful dispatch drives the strict Journey lifecycle to `REVIEW_READY` and stores a HELD result.

Add a dedicated GitHub Actions workflow and observe collection failure because `presence_core.fulfilment_contract` does not yet exist.

### GREEN implementation

Implement only enough in `presence_core/fulfilment_contract.py` to satisfy the frozen contract.

## Execution-profile boundary

Phase 4 does not mutate the canonical product compiler schema. Instead it creates a deterministic fulfilment projection from an already-compiled product plus an explicitly registered adapter binding. This avoids forcing fulfilment transport concerns into the compiler while preserving compiler fingerprints and resolved capability/provider lineage.

The execution profile must reject:

- non-`dio.compiled_product.v1` input;
- product identity mismatch;
- missing composition/compilation fingerprints;
- empty adapter identity/version;
- compiler execution states that do not permit bounded execution for the selected profile.

A test-only execution profile may be constructed directly for contract tests, but production projection must retain compiler lineage.

## Result boundary

Adapter output is untrusted until normalized and validated by the fulfilment seam. In particular, adapters may not grant themselves:

- `release_authority`;
- `external_send_authority`;
- generic `authority_created`;
- customer-delivery completion.

Artifacts returned in Phase 4 are descriptors with `release_state = HELD`. Phase 5 owns transformation into the release/delivery contract.

## Sophia reference boundary

The repository already has a dedicated reviewer-oriented Sophia academic-review adapter and a separate live 7070 routing smoke. That is not equivalent to verified live reviewer routing. Therefore Phase 4 freezes the universal contract without activating Sophia as a production universal adapter. The live representative-review correction remains a named gate before the later organ-adapter gauntlet.

## Verification

Required before acceptance:

- observed RED GitHub Actions run;
- GREEN implementation run;
- exact final documentation-bearing head compiles and passes Phase 4 tests;
- Phase 3 -> Phase 4 compare contains only intended Phase 4 files;
- stacked PR targets `agent/dio-customer-journey-phase3` and is not merged automatically.

## Acceptance target

`DIO_CUSTOMER_JOURNEY_PHASE4_UNIVERSAL_FULFILMENT_CONTRACT_VERIFIED`
