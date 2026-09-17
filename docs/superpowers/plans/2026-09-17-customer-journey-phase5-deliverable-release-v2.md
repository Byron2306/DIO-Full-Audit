# Customer Journey Phase 5 Deliverable Manifest & Release v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-PDF release assumption with one hash-bound, format-neutral N-artifact delivery manifest, typed human release authority, one-use delivery authority, and an exact delivery receipt.

**Architecture:** Phase 5 consumes only canonical Phase 4 `dio.fulfilment_result.v1` state at `REVIEW_READY`. A new v2 release module validates each held file against its declared SHA, builds and persists one canonical `DeliverableManifest`, creates no authority during manifest construction, then converts an exact SHA-bound resolved `Needs You` approval into a channel-scoped one-use release authority. Delivery uses an injected transport boundary; only explicit successful transport evidence consumes authority and advances the JourneyCase to `DELIVERED`.

**Tech Stack:** Python 3, pathlib, hashlib, JSON canonical hashing, pytest, existing Journey Core/Needs You/state primitives.

**Spec:** `docs/DIO_CUSTOMER_JOURNEY_SPINE_MASTER_PLAN.md` Phase 5.

## Global Constraints

- Support N artifacts and do not special-case PDF.
- Every released artifact must remain byte-for-byte bound to its approved manifest SHA.
- Manifest construction creates no release, send, payment, or generic authority.
- Human approval binds the exact manifest SHA, not a filename or product label.
- Release authority is scoped to one case, one manifest, and permitted delivery channels.
- Successful delivery consumes authority exactly once; replay is refused.
- Failed transport does not mark the case delivered and does not consume authority.
- Preserve proof of exactly which artifact hashes left DIO.
- Do not mutate legacy `presence_core/fulfilment_release.py` in Phase 5.

---

### Task 1: Canonical N-artifact DeliverableManifest

**Files:**
- Create: `presence_core/deliverable_release_v2.py`
- Create: `tests/test_customer_journey_phase5.py`

**Interfaces:**
- Consumes: canonical case at `REVIEW_READY` with stored `dio.fulfilment_result.v1`.
- Produces: `build_deliverable_manifest(state_root: Path, case_id: str) -> dict[str, Any]`.

- [ ] Write failing tests for canonical Phase 4 lineage, multiple artifact formats, exact file SHA verification, manifest hashing, and zero authority creation.
- [ ] Run the Phase 5 test file and verify RED because the v2 module does not exist.
- [ ] Implement the minimal manifest builder and persistence.
- [ ] Run the Phase 5 test file and verify the manifest tests pass.

### Task 2: Exact-manifest human release authority

**Files:**
- Modify: `presence_core/deliverable_release_v2.py`
- Modify: `tests/test_customer_journey_phase5.py`

**Interfaces:**
- Consumes: persisted `dio.deliverable_manifest.v2` plus resolved `Needs You` approval whose evidence contains the exact manifest SHA.
- Produces: `create_manifest_release_authority(...) -> dict[str, Any]`.

- [ ] Write failing tests proving unresolved/refused/non-SHA-bound approvals create no authority and exact approval moves `REVIEW_READY -> RELEASE_APPROVAL`.
- [ ] Implement channel-scoped authority with `consumed=False`, manifest SHA binding, explicit human approval evidence, and no unrelated authority.
- [ ] Verify the tests pass.

### Task 3: Byte revalidation, delivery receipt, and replay refusal

**Files:**
- Modify: `presence_core/deliverable_release_v2.py`
- Modify: `tests/test_customer_journey_phase5.py`

**Interfaces:**
- Consumes: unconsumed v2 release authority and injected callable transport.
- Produces: `deliver_manifest(...) -> dict[str, Any]` with `dio.delivery_receipt.v2` only on successful external send.

- [ ] Write failing tests for post-approval artifact mutation, wrong channel, failed transport, successful multi-file send, exact receipt contents, and replay refusal.
- [ ] Implement pre-send file rehashing, channel validation, transport invocation, failed-attempt persistence, successful receipt persistence, authority consumption, and `RELEASE_APPROVAL -> DELIVERED`.
- [ ] Verify Phase 5 tests and relevant legacy release tests together.

### Task 4: Acceptance documentation and workflow

**Files:**
- Create: `.github/workflows/dio-customer-journey-phase5.yml`
- Create: `docs/DIO_CUSTOMER_JOURNEY_PHASE5.md`

**Interfaces:**
- CI runs compile plus the Phase 5 contract tests.
- Acceptance token: `DIO_CUSTOMER_JOURNEY_PHASE5_DELIVERABLE_RELEASE_V2_VERIFIED`.

- [ ] Add Phase 5 workflow.
- [ ] Document schemas, laws, test evidence, and explicit non-claims.
- [ ] Run compile and test verification fresh before completion.
