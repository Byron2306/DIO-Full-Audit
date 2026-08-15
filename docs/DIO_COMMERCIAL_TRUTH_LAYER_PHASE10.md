# DIO Phase 10 — Commercial Truth Layer

Phase 10 prevents DIO from compressing unrelated commercial events into flattering claims.

The layer preserves a strict evidence ladder:

```text
offer → qualified demand → verified attributed payment → fulfilment → delivery acceptance
      → customer value confirmation → independent repetition → economic evidence
```

No arrow is automatic.

## Core laws

- Absence is `UNKNOWN`, not zero, failure or success.
- Payment proves payment only.
- An unbound payment is not product revenue.
- Payment does not prove fulfilment.
- Delivery does not prove customer value.
- One positive customer case does not prove repeatability.
- Repeatability does not prove sustainable economics.
- Internal, sandbox and controlled cases do not prove market validation.
- Different currencies remain separate; DIO never invents a cross-currency total.
- Commercial evidence never changes maturity or creates authority.

## Repository truth found by Phase 10

The current repository contains a provider-verified live PayPal payment of USD 1.00. The associated order has no canonical product, governed case or customer binding and fulfilment was not released.

Phase 10 therefore records:

```text
VERIFIED_UNATTRIBUTED_PAYMENT
```

It does not assign that value to ContractProof, TenderProof, GrantProof, PermitProof or any other product. It also preserves controlled commercial transactions as controlled evidence, not customer validation.

## Economic-proof threshold

Economic evidence requires at least two independent external customers. Every qualifying case must include verified payment, fulfilment, delivery acceptance, customer value confirmation, cost and labour evidence. Same-currency contribution must be positive and an authorised human commercial review must be recorded.

Even then, the layer reports evidence support only. It never promotes canonical product maturity automatically.

## GoldenEye integration

GoldenEye reads the Phase 10 snapshot through `GET /api/commercial-truth`. The surface remains read-only and its server rejects POST.

Generate state:

```bash
python scripts/run_control_deck_phase9.py --output state/control_deck
python scripts/run_commercial_truth_phase10.py --output state/commercial_truth
```

Serve GoldenEye:

```bash
python scripts/serve_goldeneye_portfolio.py --host 127.0.0.1 --port 8766
```

## Acceptance

```bash
python -m pytest -q tests/test_commercial_truth_phase10.py
python scripts/run_commercial_truth_phase10.py --output /tmp/dio-phase10-commercial-truth
```

The final acceptance token is:

```text
DIO_COMMERCIAL_TRUTH_LAYER_READY
```
