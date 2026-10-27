# Canonical 68 Shared Capability Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect all 68 canonical offers to a deterministic shared professional-production capability plan.

**Architecture:** Add one registry module for shared provider truth, then compile route-specific required and optional stages into each Journey binding and execution profile. Keep the current route adapter as the dispatch boundary and preserve all human authority gates.

**Tech Stack:** Python 3, deterministic JSON hashing, pytest

**Spec:** `docs/superpowers/specs/2026-10-27-canonical-68-shared-capability-wiring-design.md`

## Global Constraints

- The canonical product census remains exactly 68.
- Shared capabilities create no release, send, pricing, publication, or spend authority.
- Optional capabilities never appear as required execution steps.
- Provider source paths must exist in the checked-out repository.

## Review Focus

- A missing provider file must fail capability registry construction.
- Every offer must include exactly one native route, Format Core, and Production Studio required stage.
- Document Studio must be marked route-required only for document and HOMS-learning routes.
- NicheFoundry must be marked route-required only for campaign routes and remain approval-gated elsewhere.
- Repeated compilation must produce identical hashes and ordered steps.

---

### Task 1: Shared capability registry

**Files:**
- Create: `presence_core/shared_capability_registry.py`
- Test: `tests/test_customer_journey_phase8.py`

**Interfaces:**
- Produces: `build_shared_capability_registry(root: Path) -> dict[str, dict[str, Any]]`
- Produces: `build_route_capability_plan(root: Path, route_id: str, route_provider: dict[str, Any]) -> list[dict[str, Any]]`

- [ ] Write tests for the four provider records, provider path validation, all-route availability, and route-composition requirement rules.
- [ ] Run the focused tests and confirm they fail because the registry does not exist.
- [ ] Implement the registry and deterministic ordered route plan.
- [ ] Run the focused tests and confirm they pass.

### Task 2: Bind and project the plan across all 68 offers

**Files:**
- Modify: `presence_core/product_binding_registry.py`
- Test: `tests/test_customer_journey_phase8.py`

**Interfaces:**
- Consumes: `build_shared_capability_registry` and `build_route_capability_plan` from Task 1.
- Produces: `binding["shared_capability_catalog"]`, `binding["capability_plan"]`, and an execution profile containing only independently enforceable steps.

- [ ] Write assertions across all 68 bindings for catalog coverage, stage ordering, authority fields, and conditional requirements.
- [ ] Update execution-profile assertions to require the native route plus required shared stages.
- [ ] Run the focused tests and confirm they fail against the one-capability profile.
- [ ] Compile the capability catalog and plan into each binding and project required stages into execution profiles.
- [ ] Run Phase 8 and fulfilment contract tests and confirm they pass.
- [ ] Run the relevant broader customer-journey suite and inspect the working-tree diff.

### Task 3: Execute the universal professional finish

**Files:**
- Create: `presence_core/shared_production_finish.py`
- Modify: `presence_core/fulfilment_contract.py`
- Test: `tests/test_customer_journey_phase4.py`

**Interfaces:**
- Produces: `finish_fulfilment_for_review(state_root, request, artifacts) -> dict[str, Any]`.
- Consumes: required Format Core and Production Studio capability IDs from the execution profile.

- [ ] Write a failing dispatch test requiring a real Format Core HTML artifact and Production Studio review manifest.
- [ ] Implement a provider-neutral review finisher over the route adapter's held artifact inventory.
- [ ] Invoke the finisher from dispatch only when both shared capability IDs are required.
- [ ] Refuse partial Format Core/Production Studio configurations.
- [ ] Run Phase 4 through Phase 8 tests and confirm the real files survive deliverable-manifest validation.

