# DIO Customer Journey Spine — Phase 1 Surface-Neutral Journey Core

Status: **PASS / VERIFIED**  
Branch: `agent/dio-customer-journey-phase1`  
Phase 0 prerequisite: `DIO_CUSTOMER_JOURNEY_PHASE0_ORGAN_CENSUS_FROZEN`

## Acceptance token

`DIO_CUSTOMER_JOURNEY_PHASE1_SURFACE_NEUTRAL_CORE_VERIFIED`

## Objective

Create one canonical customer/commercial case identity that survives surface and conversation changes, exposes deterministic lifecycle actions, accepts only typed journey transitions, and can route asynchronous return events back into the same case without creating authority.

Phase 1 does not implement Phase 2 intake/scope/quote semantics. It creates the stable case and event seam those semantics will use.

## Before-state proven by RED

The legacy customer-case implementation derived the case identifier from `conversation_id` and had no Phase 1 surface-neutral API.

A contract-only branch, `agent/dio-customer-journey-phase1-tests`, ran the Phase 1 tests against the legacy implementation before the new core existed.

GitHub Actions run `35267162026` failed during test collection with:

```text
ImportError: cannot import name 'available_actions' from 'presence_core.customer_cases'
1 error in 0.19s
```

That run establishes the required red state.

## Implementation

### `presence_core/journey_core.py`

Phase 1 adds a surface-neutral layer over the established customer-case storage rather than creating a second commercial ledger.

The module provides:

- `create_journey_case(...)`
- `bind_surface_to_case(...)`
- `find_case_for_surface(...)`
- `available_actions(...)`
- `transition_case(...)`
- `record_journey_event(...)`

### Canonical identity

`create_journey_case` creates the canonical `case_id` independently of Telegram, web, email, voice or any conversation identifier.

Surface bindings are attached afterwards. A surface therefore discovers or projects an existing journey rather than becoming the journey's identity.

### One-to-many surface bindings

A case stores explicit `surface_bindings`. The case index separately maps the tuple:

```text
surface + external_user_id + conversation_id
    ↓
canonical case_id
```

Multiple bindings may resolve to the same case. A binding is refused if it is already owned by another case.

Conversation IDs continue to be written into the legacy conversation index for backward-compatible discovery, but they no longer define new Journey Core case identity.

### Preferred return route

A case may identify one `preferred_return_binding_id`. First-class journey events resolve that binding into a return route containing:

- surface;
- external user identity;
- conversation identity;
- binding identity.

This is routing metadata only. It creates no send, release or execution authority.

### Typed lifecycle transitions

Phase 1 adds an explicit transition graph. `transition_case` refuses a lifecycle jump that is not declared from the current stage.

This is stricter than the legacy monotonic helper, which preserved ordering but could permit arbitrary forward skips.

Legacy helpers remain untouched for compatibility. New Journey Spine code uses the strict Phase 1 transition API.

### Deterministic available actions

`available_actions(case)` is a deterministic projection of canonical case stage. Vesper can therefore ask the Journey Core what may happen next instead of guessing permitted actions from conversational context.

Examples:

```text
NEW_LEAD  -> QUALIFY, OPEN_INTAKE
QUALIFIED -> OPEN_INTAKE
PAYMENT_PENDING -> VERIFY_SETTLEMENT
RELEASE_APPROVAL -> DELIVER
CLOSED -> no actions
```

Available actions are possibilities inside the journey state machine. They are not authority grants.

### First-class journey events

`record_journey_event` records a deterministic event identity over:

- canonical case ID;
- event type;
- payload;
- event sequence.

Each event carries the canonical `case_id`, its resolved return route, and `authority_created: false`.

This establishes the Phase 1 seam for long-running fulfilment to return later without losing the customer case.

## Cross-channel acceptance gauntlet

The Phase 1 test suite proves:

1. canonical case identity is independent from surface/conversation identity;
2. web and Telegram bindings resolve to one case;
3. two surface bindings survive on the same stored case;
4. available actions are deterministic;
5. allowed lifecycle transitions succeed;
6. undeclared forward lifecycle jumps are refused;
7. an asynchronous fulfilment-completed event returns to the preferred Telegram binding;
8. recording an event creates no authority.

## Sophia reference-organ boundary inspection

The master programme required Sophia's reviewer role to be isolated from tutoring/pedagogy before using it as the reference fulfilment organ in later phases.

The current `adapters/sophia/review_pipeline.py` contains no tutor or pedagogy route. `adapters/sophia/README.md` defines the adapter as an academic review pipeline from manuscript/research question through governed discovery, citation/reference audit, claim/source support mapping, reviewer commentary and human approval.

No code mutation was made solely to manufacture a distinction already present in the current adapter. The later fulfilment contract must bind specifically to this review adapter and must not substitute Sophia Tutor or learning routes.

## Verification

GitHub Actions run `35267331692` executed on CPython 3.12 and completed successfully.

```text
python -m py_compile \
  presence_core/customer_cases.py \
  presence_core/journey_core.py \
  tests/test_customer_journey_phase1.py

python -m pytest -q tests/test_customer_journey_phase1.py
.... [100%]
4 passed in 0.11s
```

## Phase 1 exit gates

| Gate | Result |
|---|---|
| Canonical case ID independent of surface/conversation | PASS |
| Multiple surface bindings resolve to one case | PASS |
| Cross-channel case continuity | PASS |
| Deterministic `available_actions` | PASS |
| Strict typed journey transitions | PASS |
| Invalid forward transition refused | PASS |
| First-class async event return routing | PASS |
| Event recording creates authority | REFUSE / false |
| Legacy customer-case storage reused | PASS |
| Sophia reviewer lane isolated from tutor/pedagogy | PASS by inspection |
| Phase 1 CI | 4 passed |

## Phase 1 result

**PASS — Surface-neutral Journey Core v1 is verified.**

The programme may proceed to **Phase 2: Intake, Scope and Quote contracts**. Phase 2 must consume this canonical case identity and deterministic action surface; it must not reintroduce product-specific or channel-specific commercial state.
