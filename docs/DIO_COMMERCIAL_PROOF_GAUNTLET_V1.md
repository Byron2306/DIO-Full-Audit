# DIO Commercial Proof Gauntlet v1

## Purpose

The Commercial Proof Gauntlet closes the gap between **professional capability** and **commercial truth** without allowing market research, free pilots, provider telemetry or customer messages to impersonate stronger evidence than they actually are.

The gauntlet begins from the frozen Professional Task Gauntlet result:

- examined implementation: `59a6c795eac284d435f9209c2c840406939188aa`
- 12 / 12 professional tasks verified
- portfolio fingerprint: `sha256:7b0e1f9e5ea6a0149dd585ccd13a8dca0dbc4dc3169f8b0229729804dd9512d8`
- exact receipt is preserved at `docs/proofs/professional_task_gauntlet/2026-08-18/PROFESSIONAL_TASK_GAUNTLET_RECEIPT.json`

That proof establishes controlled professional-task quality. It does not establish demand, payment, acceptance or repeatability.

## Commercial proof ladder

```text
professional-task quality
        ↓
market viability evidence
        ↓
verified positive-value payment
        ↓
independent paying-customer acceptance
        ↓
COMMERCIAL_VALIDATION_PROVED
        ↓
three independent validated engagements
        ↓
REPEATABLE_COMMERCIAL_PROOF_PROVED
```

The gates are deliberately independent.

### Market viability

`MARKET_VIABILITY_PROVED` requires a source-bound current research pack with:

- an explicit buyer segment;
- an explicit buyer problem;
- documented research methodology;
- at least three real, non-demo source URLs;
- at least two source domains;
- source observation dates within the configured freshness window;
- at least two source-bound competing offers;
- at least two source-bound positive-value price observations;
- at least two source-bound demand signals.

This proves only that the configured evidence threshold for a plausible commercial market has been met. It does **not** prove willingness to pay.

### Verified payment

A real payment is never accepted from a manually typed `state: paid` bundle.

`VERIFIED_PAYMENT_PROVED` requires `real_payment` mode plus a **live authenticated DIO Edge order read**. The order must:

- match the registered order ID;
- be in `paid` state;
- have a positive amount;
- match the bundle amount and currency;
- match the product code where supplied;
- remain bound to the commercial customer lineage.

The existing Edge gateway already rejects commerce orders with amounts below one minor currency unit and records provider payment events only after its payment-verification path. The Commercial Proof Gauntlet therefore consumes DIO Edge truth instead of accepting arbitrary provider claims.

A successful positive-value payment proves both:

- `VERIFIED_PAYMENT_PROVED`
- `WILLINGNESS_TO_PAY_PROVED`

### Zero-value professor pilot

The seeded bundle `config/commercial_proof/zero_value_professor_pilot.json` is intentionally free.

It produces:

```text
payment_flow_executed = true
verified_payment = NOT_APPLICABLE_ZERO_VALUE_PILOT
willingness_to_pay = WILLINGNESS_TO_PAY_UNPROVED
revenue_minor = 0
commercial_validation = COMMERCIAL_VALIDATION_UNPROVED
```

This is a feature, not a missing checkbox. A free self-pilot may prove plumbing, package handling and acceptance mechanics. It may never prove revenue or willingness to pay.

Run it with:

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
  -m scripts.run_commercial_proof_gauntlet \
  --bundle config/commercial_proof/zero_value_professor_pilot.json \
  --output /tmp/dio-commercial-proof-zero \
  --require-zero-pilot-ready
```

Expected acceptance token:

```text
DIO_COMMERCIAL_PROOF_ZERO_VALUE_PILOT_READY
```

### Customer acceptance

`CUSTOMER_ACCEPTANCE_PROVED` requires:

- a positive-value verified payment;
- an independent customer;
- customer-originated acceptance;
- the exact delivered artifact SHA-256;
- a source-bound acknowledgement from an Outlook reply, Telegram reply or customer portal acknowledgement;
- no unresolved refund or dispute;
- customer identity matching the paid transaction.

A zero-value pilot may record `ZERO_VALUE_PILOT_ACCEPTANCE_RECORDED`, but this cannot become paid-customer acceptance proof.

### Commercial validation

`COMMERCIAL_VALIDATION_PROVED` requires all of:

```text
professional_quality = verified
market_viability = MARKET_VIABILITY_PROVED
verified_payment = VERIFIED_PAYMENT_PROVED
willingness_to_pay = WILLINGNESS_TO_PAY_PROVED
customer_acceptance = CUSTOMER_ACCEPTANCE_PROVED
lineage = passed
```

The acceptance token is then:

```text
DIO_COMMERCIAL_VALIDATION_PROVED
```

### Repeatability

One accepted payment proves one commercial engagement.

`REPEATABLE_COMMERCIAL_PROOF_PROVED` requires at least **three distinct independent customers and three distinct validated orders**, each backed by a prior commercial-validation receipt hash.

## Real-payment execution

Real payment mode requires an Edge config because the runner performs the current authenticated order read itself:

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
  -m scripts.run_commercial_proof_gauntlet \
  --bundle /path/to/REAL_COMMERCIAL_PROOF_BUNDLE.json \
  --edge-config config/dio_edge.live.json \
  --output /tmp/dio-commercial-proof-real \
  --require-commercial-validation
```

If DIO Edge does not currently report the bound order as paid with the expected amount and currency, the gauntlet refuses verified-payment and commercial-validation claims.

## Authority boundary

The gauntlet is an evidence evaluator. It does not:

- create payment authority;
- issue refunds;
- send customer messages;
- publish externally;
- create demand;
- turn simulated telemetry into commercial evidence;
- turn a zero-value pilot into revenue;
- turn one customer into repeatable market proof.

Every receipt therefore keeps:

```text
authority_created = false
external_effects = false
```

## Unit-test truth

Tests use synthetic fixtures only to prove the state-machine invariants. Synthetic fixtures are not persisted as commercial evidence and cannot satisfy the real runner's live DIO Edge requirement for `real_payment` mode.
