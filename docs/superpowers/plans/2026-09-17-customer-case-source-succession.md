# Customer Case Source Succession Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use test-driven development for every behaviour change.

**Goal:** Prevent new manuscript bytes from inheriting scope, quote or checkout truth derived from an older manuscript in the same conversation.

**Architecture:** Preserve monotonic historical customer cases. When a materially different source arrives after scope/commercial derivation, create a deterministic successor case, move only the conversation's current pointer, and let the new case proceed through the ordinary lifecycle.

**Tech Stack:** Python 3.13, pytest, JSON file state.

**Spec:** `docs/superpowers/specs/2026-09-17-customer-case-source-succession-design.md`

## Global Constraints

- Do not permit backwards customer-case stage transitions.
- Do not mutate historical scope or quote truth.
- Same SHA means continuity.
- Different SHA after derived scope/commercial truth means successor work.
- Source succession creates no authority.
- Do not touch `presence_core/voice.py`.
- Do not touch `portfolio_runtime.py`.
- Never stage `.pre-*` backups.

---

### Task 1: Deterministic successor customer case

**Files**
- Modify: `presence_core/customer_cases.py`
- Create: `tests/test_customer_case_source_succession.py`

**Behaviour**
- Add deterministic successor case ID generation.
- Add `create_successor_case(...)`.
- Preserve customer/product identity.
- Reset all work-derived state.
- Set `predecessor_case_id`.
- Maintain `conversation_case_history`.
- Move `conversations[conversation_id]` to the successor.

**TDD**
1. RED: scoped/quoted case A + source SHA B creates fresh case B.
2. RED: B has no inherited scope/quote/order/checkout.
3. RED: current conversation pointer resolves to B.
4. GREEN: implement minimum successor primitive.

---

### Task 2: Source-change detection in Presence engine

**Files**
- Modify: `presence_core/engine.py`
- Extend: `tests/test_customer_case_source_succession.py`

**Behaviour**
Before appending a newly quarantined attachment:
- inspect current scoped source SHA;
- if incoming SHA differs and current case contains derived scope/commercial truth, call `create_successor_case`;
- otherwise continue the existing case.

Then bind the current attachment through the normal quarantine path.

**TDD**
1. RED: quoted A + different B through the engine selects successor.
2. RED: successor reaches FILES_RECEIVED_QUARANTINED.
3. GREEN: minimal engine selection logic.

---

### Task 3: Same-byte replay continuity

**Files**
- Extend: `tests/test_customer_case_source_succession.py`

**Behaviour**
A new attachment receipt carrying the same SHA as the scoped source does not create a successor.

**TDD**
1. RED: same SHA with different attachment ID remains on case A.
2. GREEN: source comparison is SHA-based, not attachment-ID-based.

---

### Task 4: Commercial truth regression

**Files**
- Extend: `tests/test_customer_case_source_succession.py`
- Run existing presence/commercial tests

**Behaviour**
For successor B:
- `scope == {}`
- `quote_state == not_prepared`
- `payment_state == unverified`
- no `checkout_url`
- no prior order IDs
- `authority_created == false`

Case A retains its original quote exactly.

---

### Task 5: Presence regression verification

Run focused suites covering:
- customer-case succession
- presence engine
- router
- pricing/quote behaviour
- fulfilment authority
- bridge fulfilment completion

Only after all are green may the production service be restarted.

---

### Task 6: Resume real customer gauntlet

Using the already-uploaded article:

- ensure the new article resolves to a fresh successor case;
- perform fresh bounded scope;
- create fresh quote from that scope;
- suppress stale checkout;
- activate controlled test processing only from authenticated operator/test authority;
- execute Sophia Review;
- human release;
- Vesper async return;
- exact-artifact delivery;
- receipt/FRA/case verification.
