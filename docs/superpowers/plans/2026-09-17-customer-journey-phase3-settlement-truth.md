# Customer Journey Phase 3 Settlement Truth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce one typed settlement contract that separates payment evidence, revenue truth, market-validation eligibility, and fulfilment eligibility without letting controlled tests or waivers masquerade as real customer settlement.

**Architecture:** Add a focused `presence_core/settlement_truth.py` layer on top of Phase 2 `JourneyCase` and canonical quote truth. It will issue hash-bound `SettlementReceipt` records for `REAL_SETTLEMENT`, `CONTROLLED_TEST_SETTLEMENT`, and `WAIVED`, update the canonical case through Journey Core transitions, and expose four independent truth fields: `external_funds_moved`, `revenue_recognised`, `market_validation_eligible`, and `fulfilment_eligible`. Existing provider-specific checkout/reconciliation code remains transport/evidence ingestion and does not itself define commercial truth.

**Tech Stack:** Python 3.12, pytest, GitHub Actions, existing `presence_core.customer_cases`, `presence_core.journey_core`, Phase 2 quote contracts.

**Spec:** `docs/DIO_CUSTOMER_JOURNEY_SPINE_MASTER_PLAN.md`, Phase 3 — Settlement & Commercial Truth.

## Global Constraints

- A workflow may proceed under an explicitly authorised controlled test without creating false revenue or payment truth.
- `REAL_SETTLEMENT`, `CONTROLLED_TEST_SETTLEMENT`, and `WAIVED` are distinct typed states.
- External funds moved, revenue recognition, market-validation eligibility, and fulfilment eligibility are separately typed facts.
- Quote lineage, case identity, product identity, and source/provider lineage remain bound into the receipt.
- Settlement never creates release authority.
- Controlled-test settlement is not revenue and is never market-validation eligible.
- Waiver is not payment and is never revenue or market-validation evidence.
- Real settlement requires positive externally moved funds and exact quote amount/currency/lineage match.
- All receipts are deterministic/hash-bound and authority boundaries remain explicit.

---

### Task 1: Freeze Phase 3 settlement contract in tests

**Files:**
- Create: `tests/test_customer_journey_phase3.py`
- Create: `.github/workflows/dio-customer-journey-phase3.yml`

**Interfaces:**
- Consumes: `create_journey_case`, Phase 2 `open_intake`, `record_intake_inputs`, `assess_scope`, `prepare_quote`.
- Produces expected public interfaces: `record_real_settlement`, `record_controlled_test_settlement`, `record_waived_settlement`, `settlement_truth`.

- [ ] **Step 1: Write a failing test for real settlement truth**

Create a bounded Phase 2 quote for `Professional Correspondence`, then call `record_real_settlement(...)` with provider evidence matching the quote. Assert:

```python
assert receipt["settlement_class"] == "REAL_SETTLEMENT"
assert receipt["external_funds_moved"] is True
assert receipt["revenue_recognised"] is True
assert receipt["market_validation_eligible"] is True
assert receipt["fulfilment_eligible"] is True
assert receipt["release_authority_created"] is False
assert case["stage"] == "PAYMENT_VERIFIED"
```

- [ ] **Step 2: Write a failing test for controlled-test truth**

Assert controlled test records:

```python
assert receipt["settlement_class"] == "CONTROLLED_TEST_SETTLEMENT"
assert receipt["external_funds_moved"] is False
assert receipt["revenue_recognised"] is False
assert receipt["market_validation_eligible"] is False
assert receipt["fulfilment_eligible"] is True
assert receipt["operator_self_transaction"] is True
```

and cannot be supplied with `external_funds_moved=True`.

- [ ] **Step 3: Write a failing test for waiver truth**

Assert waiver records:

```python
assert receipt["settlement_class"] == "WAIVED"
assert receipt["external_funds_moved"] is False
assert receipt["revenue_recognised"] is False
assert receipt["market_validation_eligible"] is False
assert receipt["fulfilment_eligible"] is True
assert receipt["waived_by"] == "operator:byron"
```

and requires a non-empty reason and operator identity.

- [ ] **Step 4: Write mismatch/refusal tests**

Verify real settlement refuses wrong case, quote, product, amount, currency, or non-positive funds; verify no settlement method accepts a case without canonical Phase 2 quote truth.

- [ ] **Step 5: Run the Phase 3 test workflow and preserve RED evidence**

Run through GitHub Actions:

```bash
python -m pytest -q tests/test_customer_journey_phase3.py
```

Expected: collection/import failure because `presence_core.settlement_truth` does not yet exist.

---

### Task 2: Implement one canonical settlement truth layer

**Files:**
- Create: `presence_core/settlement_truth.py`
- Test: `tests/test_customer_journey_phase3.py`

**Interfaces:**
- `record_real_settlement(state_root: Path, case_id: str, *, provider: str, provider_receipt_id: str, amount_minor: int, currency: str, external_funds_moved: bool, evidence_ref: str) -> dict[str, Any]`
- `record_controlled_test_settlement(state_root: Path, case_id: str, *, receipt_id: str, authorized_by: str, reason: str) -> dict[str, Any]`
- `record_waived_settlement(state_root: Path, case_id: str, *, receipt_id: str, waived_by: str, reason: str) -> dict[str, Any]`
- `settlement_truth(case: dict[str, Any]) -> dict[str, Any] | None`

- [ ] **Step 1: Resolve canonical quote truth from the case**

Require `case.stage == "QUOTE_READY"` and Phase 2 `commercial.quote_result.quote` with `schema == "dio.customer_quote.v2"`. Reject operator-review/no-quote cases.

- [ ] **Step 2: Build common deterministic lineage**

Every receipt includes:

```python
{
    "schema": "dio.settlement_receipt.v1",
    "case_id": case_id,
    "quote_id": quote["quote_id"],
    "quote_truth_sha256": quote["quote_truth_sha256"],
    "product_id": quote["product_id"],
    "amount_minor": int(Decimal(str(quote["amount"])) * 100),
    "currency": quote["currency"],
    "release_authority_created": False,
    "authority_created": False,
}
```

Hash the canonical receipt payload into `settlement_receipt_sha256`.

- [ ] **Step 3: Implement `REAL_SETTLEMENT`**

Require `external_funds_moved is True`, positive amount, exact quote amount/currency match, non-empty provider and provider receipt ID. Set:

```python
external_funds_moved = True
revenue_recognised = True
market_validation_eligible = True
fulfilment_eligible = True
```

- [ ] **Step 4: Implement `CONTROLLED_TEST_SETTLEMENT`**

No external funds parameter is accepted. Set:

```python
external_funds_moved = False
revenue_recognised = False
market_validation_eligible = False
fulfilment_eligible = True
operator_self_transaction = True
```

Require explicit `authorized_by` and `reason`.

- [ ] **Step 5: Implement `WAIVED`**

Set:

```python
external_funds_moved = False
revenue_recognised = False
market_validation_eligible = False
fulfilment_eligible = True
```

Require explicit `waived_by` and `reason`.

- [ ] **Step 6: Persist one canonical case projection**

Store the receipt under `case["settlement"]`, mirror only compatibility-safe fields into `case["commercial"]`, and transition `QUOTE_READY -> PAYMENT_PENDING -> PAYMENT_VERIFIED` through Journey Core so Phase 1 transition law remains authoritative. Never set `fulfilment_released=True` or release authority.

- [ ] **Step 7: Run tests GREEN**

```bash
python -m pytest -q tests/test_customer_journey_phase3.py
```

Expected: all Phase 3 tests pass.

---

### Task 3: Record acceptance and verify the exact branch head

**Files:**
- Create: `docs/DIO_CUSTOMER_JOURNEY_PHASE3.md`

**Interfaces:**
- Produces acceptance token `DIO_CUSTOMER_JOURNEY_PHASE3_SETTLEMENT_TRUTH_VERIFIED`.

- [ ] **Step 1: Document red/green lineage, receipt schema, and truth table**

Include the explicit matrix:

| Settlement class | External funds | Revenue | Market validation | Fulfilment eligible |
|---|---:|---:|---:|---:|
| REAL_SETTLEMENT | true | true | true | true |
| CONTROLLED_TEST_SETTLEMENT | false | false | false | true |
| WAIVED | false | false | false | true |

- [ ] **Step 2: Re-run compile and test gates on the documentation-bearing head**

```bash
python -m py_compile presence_core/settlement_truth.py tests/test_customer_journey_phase3.py
python -m pytest -q tests/test_customer_journey_phase3.py
```

Expected: zero failures.

- [ ] **Step 3: Compare Phase 2 to Phase 3**

Confirm the stack contains only Phase 3 plan/tests/workflow/settlement contract/acceptance documentation and no unrelated drift.

- [ ] **Step 4: Open a stacked PR against `agent/dio-customer-journey-phase2`**

Record the current-head test result, RED lineage, acceptance token, and explicit settlement truth boundaries.