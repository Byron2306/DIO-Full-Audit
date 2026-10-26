# DIO Reference Incarnation Gauntlet — Phase 7

## Status

Phase 7 proves the first reference portfolio as a factory property. It does not create another product. It observes four existing internal-proof incarnations under one adversarial acceptance contract:

1. ContractProof
2. TenderProof
3. GrantProof
4. PermitProof

## What the gauntlet proves

Every reference incarnation must compile twice to the same composition and compilation fingerprints, execute twice from the same fixed canonical inputs, reproduce its Obligation Bundle and proof fingerprints, and reproduce every rendered child-artifact hash.

The four compositions must remain distinguishable. Each must expose exactly WP01, WP05 and WP11 as `READY`; compiler execution must remain `NEEDS_YOU`; Work Pattern Runtime execution must remain `REFUSE`; human review must remain `NEEDS_YOU`; and external release must remain `REFUSE`.

Golden fixtures must retain at least one missing, partial, expired or review-required state. A gauntlet that makes inconvenient evidence disappear fails.

## Adversarial controls

- Executor providers are checked for exact product scope.
- The family registry and family runner must name the same three derived products.
- A TenderProof source is deliberately presented to GrantProof and must be refused before processing.
- All eight shared Obligation Core source files are hash-bound before the first incarnation and rechecked after the last.
- Four products must yield four distinct composition fingerprints.
- No test may create authority, external effects, award decisions, permit decisions or release.

The shared-core hashes are architectural custody pins, not claims that source code can never evolve. A deliberate later core change must update the registry through an explicit governed phase; silent drift fails.

## Receipt

The gauntlet writes:

```text
state/reference_incarnation_gauntlet/REFERENCE_INCARNATION_GAUNTLET_RECEIPT.json
```

It records each composition, compilation, obligation and proof identity; artifact hashes; mixed-truth counts; provider and source isolation; core integrity; authority boundaries; and the maturity ceiling.

The receipt proves controlled internal repeatability. It does not prove customer demand, external validity, legal correctness, procurement eligibility, grant allowability, regulatory compliance, revenue or scale.

## Acceptance

```bash
pytest -q tests/test_reference_incarnation_gauntlet_phase7.py
python3 scripts/run_reference_incarnation_gauntlet.py
```

Acceptance token:

```text
DIO_REFERENCE_INCARNATION_GAUNTLET_READY
```

The next phase may consolidate META runtime mechanics only after this reference portfolio remains green.
