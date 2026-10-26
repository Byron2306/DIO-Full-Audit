# DIO Customer Journey Spine — Phase 6

## Vesper Journey Runtime

**Status:** PASS / VERIFIED locally

**Acceptance token:** `DIO_CUSTOMER_JOURNEY_PHASE6_VESPER_RUNTIME_VERIFIED`

Phase 6 gives Vesper a deterministic commercial runtime over the canonical JourneyCase without making language itself authoritative.

The runtime boundary is:

```text
customer language
      ↓
Vesper interprets / presents
      ↓
canonical VesperJourneyView
      ↓
explicit action_id + stage-bound action_ref + actor_class
      ↓
Journey Core validation
      ↓
generic action handler
      ↓
reload canonical JourneyCase
      ↓
new VesperJourneyView
```

## Core law: language is not a lifecycle command

The new runtime deliberately has no API that executes raw conversational text. A string such as `yes`, `go ahead`, or `please proceed` is not a Journey action and has no state-transition semantics by itself.

Every executable action must instead be:

1. present in the current Journey Core `available_actions` set;
2. represented by an explicit canonical action ID;
3. accompanied by the exact action reference bound to the current case and stage;
4. requested by an actor class permitted for that action; and
5. dispatched through a registered generic action handler.

Stale action references are refused before handlers run.

## `dio.vesper_journey_view.v1`

The Vesper view is a non-authoritative projection over canonical case truth. It contains:

- canonical case ID;
- canonical product identity;
- current Journey stage;
- exactly the actions exposed by Journey Core;
- a deterministic stage-bound reference for each action;
- actor classes permitted to request each action;
- bounded customer-facing facts from intake, scope, quote, settlement, fulfilment, deliverable, and delivery state;
- explicit false authority flags.

The view contains no product-specific execution branch. The same runtime is used for every product identity.

## Actor boundary

Vesper is the conversational mediator, not an authority class.

The runtime distinguishes the canonical actor classes `customer`, `operator`, and `system`. For example:

- a customer may request `OPEN_INTAKE` when Journey Core exposes it;
- a customer cannot self-declare `VERIFY_SETTLEMENT`;
- release approval is not a conversational customer action;
- external delivery is a system action after the release contract has created the required authority.

The policy applies to action types, not products.

## Handler distrust

`execute_vesper_action(...)` validates the requested action before invoking a handler. The handler may compose the typed Phase 2–5 contracts, but its return object is never accepted as canonical journey truth.

After the handler returns, the runtime reloads the JourneyCase from storage and builds the next Vesper view from that canonical state.

A Phase 6 test deliberately uses a handler that returns a fake stage and `authority_created=True`; the runtime ignores those claims and reports only persisted canonical truth.

## Cross-channel continuity

`resolve_vesper_journey(...)` composes the Phase 1 surface binding contract.

- an already-bound web/Telegram-style surface resumes its existing case;
- an explicit canonical case ID may be bound to a new surface;
- a new surface is never guessed onto another case merely because the customer text or product looks similar;
- surface binding creates no authority.

This preserves the law that a conversation may bind to a case but may never become the case.

## Async re-entry

`record_vesper_async_reentry(...)` composes first-class Journey events with Phase 1 preferred return routing. A long-running fulfilment event can therefore return to the same canonical case and identify the preferred surface for Vesper to re-enter naturally.

The re-entry record creates no send, spend, fulfilment, release, or generic authority.

## Full lifecycle projection

Phase 6 tests every Journey stage from `NEW_LEAD` through `CLOSED` and verifies that Vesper sees exactly the canonical Journey Core action set for that stage, with no guessed extras.

This includes intake, scope, quoting, operator escalation, invoice states, settlement, fulfilment, review, release, delivery, and close.

## TDD evidence

Initial RED:

```text
ModuleNotFoundError: No module named 'presence_core.vesper_journey_runtime'
```

Phase 6 GREEN:

```text
8 passed in 0.08s
```

Phases 1 through 6 compatibility sweep:

```text
36 passed in 0.47s
```

## Explicit non-claims

Phase 6 does not:

- claim that arbitrary LLM interpretation is authority;
- infer cross-channel customer identity from similar text;
- replace the live web/Telegram/email transport stack;
- remove the legacy Presence engine's existing commercial response code;
- prove real organ fulfilment against Sophia, Evidex, VAMP, HOMS, Document Studio, Media, Market Command, or other organs;
- prove all 68 product bindings;
- perform a real external customer delivery.

Those are Phase 7 and Phase 8 gauntlet concerns.

## Exit gate

The runtime now exposes canonical lifecycle truth and only current typed actions to Vesper, refuses raw-text and stale-choice state mutations, preserves actor boundaries, continues one case across explicitly bound surfaces, and supports async re-entry without granting authority.

`DIO_CUSTOMER_JOURNEY_PHASE6_VESPER_RUNTIME_VERIFIED`
