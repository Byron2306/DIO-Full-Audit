# Customer Journey Phase 7 Organ Adapter Gauntlet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove each of the eight Customer Journey organ families through the universal fulfilment/release contract without allowing mocks, historical artifacts, or host-unavailable code to masquerade as current executable readiness.

**Architecture:** Add a typed Phase 7 gauntlet registry and preflight beside the existing Journey Core. Every representative family has an explicit product, adapter binding, execution class, host requirements, release policy, and evidence requirements. A family may be `VERIFIED_NATIVE`, `NEEDS_HOST`, `NEEDS_BINDING`, or `REFUSE`; only current execution through a real bound organ can become `VERIFIED_NATIVE`. The Journey Core remains product-neutral.

**Tech Stack:** Python 3.11+, pytest, existing `presence_core` Journey contracts, repository organ adapters, GitHub Actions.

**Spec:** `docs/DIO_CUSTOMER_JOURNEY_SPINE_MASTER_PLAN.md` Phase 7.

## Global Constraints

- Preserve the eight master-plan representative journeys exactly.
- Never count mocks or monkeypatched organ calls as `VERIFIED_NATIVE`.
- Historical proof may support lineage but never current execution readiness.
- Host-bound organs must report `NEEDS_HOST` before Phase 4 dispatch, avoiding stranded `PROCESSING` cases.
- Every verified organ output must use real artifact bytes, SHA-256 custody, `HELD` release state, and false release/send/generic authority.
- Controlled-test settlement may prove lifecycle plumbing but must not be reported as revenue or market validation.
- Phase 8 is blocked until all eight families satisfy the Phase 7 exit gate.

---

### Task 1: Typed eight-family preflight

**Files:**
- Create: `presence_core/organ_adapter_gauntlet.py`
- Create: `tests/test_customer_journey_phase7.py`

**Interfaces:**
- Produces `ORGAN_FAMILIES`, `inspect_family()`, `phase7_preflight()` and typed verdict records.
- Consumers use the verdict before calling `dispatch_fulfilment()`.

- [ ] Write tests asserting exactly eight explicit families and refusing unbound/host-unavailable families.
- [ ] Run Phase 7 tests and verify RED because `presence_core.organ_adapter_gauntlet` does not exist.
- [ ] Implement the minimal typed registry and preflight.
- [ ] Verify GREEN.

### Task 2: Native organ execution adapter contract

**Files:**
- Modify: `presence_core/organ_adapter_gauntlet.py`
- Modify: `tests/test_customer_journey_phase7.py`

**Interfaces:**
- Produce `execute_verified_family()` which accepts only a real registered binding that passed preflight and normalizes actual artifacts into the Phase 4 adapter result shape.

- [ ] Add tests that reject unknown executors, missing artifacts, wrong hashes, or leaked authority.
- [ ] Verify RED.
- [ ] Implement artifact custody and authority checks.
- [ ] Verify GREEN.

### Task 3: Bind repository-native representative organs

**Files:**
- Modify: `presence_core/organ_adapter_gauntlet.py`
- Modify: `tests/test_customer_journey_phase7.py`

**Interfaces:**
- Bind each family only to a repository entrypoint that can be executed in the current environment without monkeypatching the organ itself.

- [ ] Bind deterministic CI-native entrypoints and execute them against temporary state/output roots.
- [ ] Mark true runtime/host dependencies `NEEDS_HOST` with exact reason and required entrypoint.
- [ ] Mark unresolved families `NEEDS_BINDING` rather than inventing an adapter.
- [ ] Assert no non-executed family is counted as verified.

### Task 4: Golden journey integration for every verified family

**Files:**
- Modify: `tests/test_customer_journey_phase7.py`

**Interfaces:**
- Compose existing Phase 1–6 contracts around every `VERIFIED_NATIVE` family.

- [ ] Drive cross-channel case continuity, Phase 2 intake/scope/quote, Phase 3 controlled settlement, Phase 4 fulfilment, Phase 5 manifest/release/delivery receipt, and Phase 6 Vesper view.
- [ ] Assert real artifact bytes and exact SHA lineage.
- [ ] Assert no forbidden authority leakage at any organ boundary.

### Task 5: Acceptance evidence and CI

**Files:**
- Create: `docs/DIO_CUSTOMER_JOURNEY_PHASE7.md`
- Create: `.github/workflows/dio-customer-journey-phase7.yml`

- [ ] Record per-family verdicts with evidence and blockers.
- [ ] Run Phase 1–7 compatibility tests in CI.
- [ ] Emit `DIO_CUSTOMER_JOURNEY_PHASE7_ORGAN_ADAPTER_GAUNTLET_VERIFIED` only if all eight families are `VERIFIED_NATIVE` and satisfy the complete exit gate.
- [ ] Otherwise emit a truthful partial/blocker report and do not advance to Phase 8.
