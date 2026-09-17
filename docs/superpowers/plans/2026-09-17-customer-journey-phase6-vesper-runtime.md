# Customer Journey Phase 6 Vesper Journey Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Vesper the natural-language face of canonical JourneyCase state without allowing language, conversational guesses, product branches, or stale choices to manufacture journey truth or authority.

**Architecture:** Add a focused `vesper_journey_runtime` layer above Journey Core. It projects canonical cases into deterministic Vesper-facing views, binds every exposed action to the exact current case/stage with a non-authoritative action reference, validates actor class and current availability before any handler runs, delegates state changes to generic injected handlers, reloads canonical state after execution, and converts first-class journey events into surface-aware re-entry envelopes. Vesper may narrate this structure naturally, but raw text never directly mutates lifecycle state.

**Tech Stack:** Python 3, pathlib, hashlib, canonical JSON hashing, existing `journey_core` and `customer_cases` primitives, pytest, GitHub Actions.

**Spec:** `docs/DIO_CUSTOMER_JOURNEY_SPINE_MASTER_PLAN.md` Phase 6.

## Global Constraints

- Journey Core remains the authority for stage and `available_actions`.
- Vesper interprets and presents journey truth; it never manufactures commercial, settlement, fulfilment, release, spend, send, or generic authority.
- A raw conversational string is never an executable lifecycle command.
- An executable action must be explicit, currently available, actor-permitted, and bound to the exact current case/stage through a deterministic action reference.
- Stale action references are refused before a handler runs.
- Runtime dispatch is action-driven, never product-driven.
- Handler return values are advisory; post-action truth is reloaded from the canonical case store.
- Async events preserve the canonical case and preferred return surface and create no authority.
- Phase 6 does not replace the existing Presence transport stack or prove real organ fulfilment; those remain Phase 7/8 concerns.

---

### Task 1: Canonical Vesper journey view

**Files:**
- Create: `presence_core/vesper_journey_runtime.py`
- Create: `tests/test_customer_journey_phase6.py`

**Interfaces:**
- Consumes: `dio.customer_case.v1` plus Journey Core `available_actions(case)`.
- Produces: `build_vesper_journey_view(case: dict[str, Any]) -> dict[str, Any]`.

- [ ] Write failing tests proving the view mirrors the exact canonical stage/action set, emits deterministic stage-bound action refs, exposes only bounded customer-safe commercial facts, and creates no authority.
- [ ] Run the Phase 6 test file and verify RED because `presence_core.vesper_journey_runtime` does not exist.
- [ ] Implement the minimal view projector and action-policy metadata with no product-specific branches.
- [ ] Re-run the view tests and verify GREEN.

### Task 2: Surface-neutral case resolution and cross-channel continuation

**Files:**
- Modify: `presence_core/vesper_journey_runtime.py`
- Modify: `tests/test_customer_journey_phase6.py`

**Interfaces:**
- Produces: `resolve_vesper_journey(...) -> dict[str, Any]`.

- [ ] Add tests proving an existing surface resumes its bound case, an explicitly supplied canonical case ID may be bound to a new surface, and a new surface is never guessed onto another case from conversational similarity.
- [ ] Implement resolution strictly through Phase 1 `find_case_for_surface`, `create_journey_case`, and `bind_surface_to_case`.
- [ ] Verify web and Telegram style bindings resolve to one canonical case only when explicitly bound.

### Task 3: Typed action validation and generic dispatch

**Files:**
- Modify: `presence_core/vesper_journey_runtime.py`
- Modify: `tests/test_customer_journey_phase6.py`

**Interfaces:**
- Produces: `validate_vesper_action(...) -> dict[str, Any]` and `execute_vesper_action(...) -> dict[str, Any]`.
- Consumes: exact action ID, action ref, actor class, payload, and generic handler mapping.

- [ ] Add tests proving arbitrary text/`yes` is not an action, unavailable actions are refused, stale refs are refused, actor policy is enforced, and the handler is never called on refusal.
- [ ] Add a test proving the same generic action handler works for two different product identities without product branching.
- [ ] Implement validation and dispatch. Reload the canonical case after the handler and build the after-view from stored truth rather than trusting the handler return object.
- [ ] Verify the tests pass.

### Task 4: Async re-entry and full lifecycle projection

**Files:**
- Modify: `presence_core/vesper_journey_runtime.py`
- Modify: `tests/test_customer_journey_phase6.py`

**Interfaces:**
- Produces: `record_vesper_async_reentry(...) -> dict[str, Any]`.

- [ ] Add tests covering every Journey Core stage and verifying the Vesper view exposes exactly its canonical actions with no guessed extras.
- [ ] Add a preferred-return-surface test for a fulfilment-completed async event and prove no authority is created.
- [ ] Implement async re-entry by composing Phase 1 `record_journey_event` with the current Vesper view.
- [ ] Verify Phase 1 and Phase 6 tests together.

### Task 5: Acceptance workflow and evidence

**Files:**
- Create: `.github/workflows/dio-customer-journey-phase6.yml`
- Create: `docs/DIO_CUSTOMER_JOURNEY_PHASE6.md`

**Interfaces:**
- CI compiles Phase 6 and runs Phase 1 through Phase 6 journey-runtime compatibility coverage.
- Acceptance token: `DIO_CUSTOMER_JOURNEY_PHASE6_VESPER_RUNTIME_VERIFIED`.

- [ ] Add CI dependency installation, compile, Phase 1 + Phase 6 tests, and acceptance token.
- [ ] Document runtime schemas, no-raw-text-action law, actor/action-ref boundaries, cross-channel continuation, async re-entry, evidence, and non-claims.
- [ ] Run fresh local compile/tests and then verify the exact GitHub PR head in Actions before claiming Phase 6 complete.
