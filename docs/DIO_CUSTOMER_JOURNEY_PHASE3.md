# DIO Customer Journey Spine — Phase 3 Settlement & Commercial Truth

Status: **PASS / VERIFIED**

Acceptance: `DIO_CUSTOMER_JOURNEY_PHASE3_SETTLEMENT_TRUTH_VERIFIED`

Branch: `agent/dio-customer-journey-phase3`

## Objective

Phase 3 separates workflow progression from economic truth.

DIO must never infer that a case reaching `PAYMENT_VERIFIED` means the same thing as:

- external customer funds moved;
- revenue was recognised;
- the event is eligible as market-validation evidence;
- fulfilment may proceed.

Those facts now live in one canonical, hash-bound `SettlementReceipt`.

## Canonical settlement contract

Schema:

`dio.settlement_receipt.v1`

Supported settlement classes:

- `REAL_SETTLEMENT`
- `CONTROLLED_TEST_SETTLEMENT`
- `WAIVED`

Each receipt binds:

- canonical `case_id`;
- canonical Phase 2 `quote_id`;
- `quote_truth_sha256`;
- canonical product identity;
- quoted amount and currency;
- provider / source lineage;
- settlement class;
- external-funds truth;
- revenue truth;
- market-validation eligibility;
- fulfilment eligibility;
- explicit authority boundaries;
- `settlement_receipt_sha256`.

## Economic truth matrix

| Settlement class | External funds moved | Revenue recognised | Market-validation eligible | Fulfilment eligible |
|---|---:|---:|---:|---:|
| `REAL_SETTLEMENT` | true | true | true | true |
| `CONTROLLED_TEST_SETTLEMENT` | false | false | false | true |
| `WAIVED` | false | false | false | true |

## Architectural boundary

`PAYMENT_VERIFIED` remains a **journey workflow stage**.

It is not itself economic truth.

The canonical `SettlementReceipt` is the economic truth object.

This means a controlled test may legitimately advance an authorised test journey without pretending that money moved, revenue occurred, or market demand was validated.

Likewise, a waiver can authorise fulfilment without becoming payment evidence.

## Real settlement

`REAL_SETTLEMENT` requires all of the following:

- canonical Phase 2 quote truth exists;
- external funds are explicitly verified as moved;
- settlement amount is positive;
- amount matches the canonical quote exactly;
- currency matches the canonical quote exactly;
- provider identity is present;
- provider receipt identity is present;
- evidence reference is present.

Only then does the receipt record:

- `external_funds_moved = true`
- `revenue_recognised = true`
- `market_validation_eligible = true`
- `fulfilment_eligible = true`

No release authority is created.

## Controlled test settlement

`CONTROLLED_TEST_SETTLEMENT` requires:

- canonical Phase 2 quote truth;
- explicit `authorized_by` identity;
- explicit reason;
- explicit receipt identity.

It records:

- `external_funds_moved = false`
- `revenue_recognised = false`
- `market_validation_eligible = false`
- `fulfilment_eligible = true`
- `operator_self_transaction = true`

This is the governed test path. It cannot be counted as real revenue or willingness-to-pay evidence.

## Waived settlement

`WAIVED` requires:

- canonical Phase 2 quote truth;
- explicit `waived_by` identity;
- explicit reason;
- explicit receipt identity.

It records:

- `external_funds_moved = false`
- `revenue_recognised = false`
- `market_validation_eligible = false`
- `fulfilment_eligible = true`

A waiver is therefore fulfilment authority context, not payment or market evidence.

## Journey integration

Settlement uses the strict Phase 1 Journey Core lifecycle:

```text
QUOTE_READY
    ↓
PAYMENT_PENDING
    ↓
PAYMENT_VERIFIED
```

The case stores the canonical receipt under `case["settlement"]`.

Compatibility-safe projections are mirrored under `case["commercial"]`, including:

- settlement class;
- receipt hash;
- payment state;
- payment evidence reference;
- external-funds truth;
- revenue truth;
- market-validation eligibility;
- fulfilment eligibility.

The following remain false in Phase 3:

- `fulfilment_released`
- `fulfilment_authority_created`
- `release_authority_created`
- generic `authority_created`

Phase 3 therefore makes a case **eligible** for fulfilment. It does not queue, execute, or release specialist work. That belongs to Phase 4 and later authority gates.

## Provider boundary

Existing `presence_core/commerce.py` remains the provider-specific checkout and payment-evidence ingestion layer.

Phase 3 deliberately does not make PayPal, checkout state, or a provider response the owner of commercial semantics.

Provider evidence may support creation of a `REAL_SETTLEMENT` receipt, but the canonical typed receipt owns DIO's economic truth.

## TDD evidence

### RED

GitHub Actions run `35268899681` on head `2c94df3ed8326945fc356b550a51c5c0166e131f` failed during test collection exactly because the Phase 3 implementation did not exist:

```text
ModuleNotFoundError: No module named 'presence_core.settlement_truth'
1 error in 0.21s
```

### GREEN implementation head

GitHub Actions run `35269032975` on implementation head `b7e233bca4d166a1a07bee810c89534531c7b425` compiled the Phase 3 contracts and returned:

```text
.....                                                                    [100%]
5 passed in 0.19s
```

The tests cover:

1. real settlement money/revenue/market/fulfilment truth;
2. controlled-test non-money/non-revenue semantics;
3. explicit waived settlement semantics;
4. refusal of false funds, wrong amount, and wrong currency;
5. refusal to settle without canonical Phase 2 quote truth.

## Exit gate

Phase 3 passes when all of the following are true:

- [x] settlement class is typed;
- [x] external funds are separately represented;
- [x] revenue recognition is separately represented;
- [x] market-validation eligibility is separately represented;
- [x] fulfilment eligibility is separately represented;
- [x] controlled tests cannot become revenue;
- [x] controlled tests cannot become market-validation evidence;
- [x] waivers cannot become payment or revenue evidence;
- [x] real settlement requires exact canonical quote match;
- [x] settlement binds case, quote, product and source lineage;
- [x] settlement receipt is hash-bound;
- [x] settlement creates no release authority;
- [x] strict Journey Core transitions remain authoritative.

## Result

**PASS — Phase 3 Settlement & Commercial Truth is verified.**

Acceptance token:

`DIO_CUSTOMER_JOURNEY_PHASE3_SETTLEMENT_TRUTH_VERIFIED`

The programme may proceed to **Phase 4 — Universal Fulfilment Contract** after fresh current-head verification.