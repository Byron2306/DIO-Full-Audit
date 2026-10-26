# DIO Phase 12 — Profile-driven Expansion

Phase 12 proves that DIO can add a materially different product incarnation through source-bound profiles and declared provider scope while preserving the existing compiler, shared Obligation Core, proof contract and human authority boundary.

## New incarnation

**DIO PolicyProof** is the fifth canonical reference incarnation.

It adds:

- `framework.policy_assurance`, a source-bound framework profile;
- a canonical product manifest using all six profile classes;
- policy-specific source and evidence fixtures;
- an exactly scoped `product.executor.policyproof` capability;
- one bounded family-definition entry.

It does not add another obligation engine, evidence engine, proof runtime or generic executor.

## Profile axes

Every Phase 12 incarnation must bind exactly these six classes:

1. domain
2. framework
3. authority
4. connector
5. output
6. commercial

The framework profile supplies domain vocabulary, review states, deadline semantics, human decision boundaries and forbidden claims. Compiler bindings retain profile ID, version, path and SHA-256 custody.

## Gauntlet

The acceptance runner:

1. reruns the complete four-product Phase 7 gauntlet;
2. compiles all five products twice;
3. requires five distinct composition fingerprints;
4. validates complete profile-axis binding and the expected framework identity;
5. executes PolicyProof twice against fixed canonical input;
6. compares semantic, proof and rendered-artifact identities;
7. verifies input immutability;
8. refuses a TenderProof source submitted to PolicyProof;
9. verifies the profile-index digest equals the compiler-bound digest;
10. preserves `NEEDS_YOU` human gates and `REFUSE` external release.

## Claim boundary

A pass establishes deterministic internal profile-driven expansion for five reference incarnations. It does not establish policy compliance, legal sufficiency, external validation, customer value, repeatability, revenue or scale.

## Run

```bash
python -m pytest -q tests/test_profile_expansion_phase12.py
python scripts/run_profile_expansion_phase12.py \
  --output /tmp/dio-phase12-profile-expansion
```

Expected token:

```text
DIO_PROFILE_DRIVEN_EXPANSION_READY
```
