# DIO Paid Reference Products — Phase 11

## Purpose

Phase 11 proves that one product can traverse a complete commercial reference journey without collapsing commercial states into one flattering claim.

The first offer is `contractproof_reference_review`. Its controlled acceptance chain is:

```text
website seen
  -> offer information acknowledged
  -> mailer submitted
  -> controlled USD 1.00 test payment verified
  -> bounded ContractProof fulfilment
  -> proof integrity verified
  -> controlled journey resolved
```

## What “resolved” means

`RESOLVED_CONTROLLED_TEST` means every internal seam in the reference chain produced and bound its expected receipt. It does not mean that an external customer paid, accepted delivery, received value, or validated a market.

The test payment is written in the existing sandbox order and provider-event shapes. Phase 10 discovers it, verifies the matching event, and preserves it as controlled, non-qualifying evidence.

## Storefront

Run the localhost-only storefront:

```bash
python scripts/serve_paid_reference_phase11.py --output /tmp/dio-phase11-browser
```

Then open `http://127.0.0.1:8111`.

The page collects only reference intake information. It refuses card, bank, CVV and expiry fields. Clicking the final button submits the mailer to the local bounded endpoint and creates a controlled test-payment receipt. No live charge and no external email occur.

## Truth boundaries

- test payment is not attributed revenue;
- mailer submission is not qualified demand;
- payment is not fulfilment authority;
- fulfilment is not external-delivery authority;
- no card or bank data is collected;
- no market validation is claimed;
- the human fulfilment and disclosure gates remain intact.

## Acceptance

```bash
python -m pytest -q tests/test_paid_reference_phase11.py
python scripts/run_paid_reference_phase11.py --output /tmp/dio-phase11-paid-reference
```

Expected token:

```text
DIO_PAID_REFERENCE_PRODUCTS_READY
```

This phase earns a test-ready paid reference journey. Live checkout, real external delivery, customer-value confirmation and commercial promotion require their own evidence and human decisions.
