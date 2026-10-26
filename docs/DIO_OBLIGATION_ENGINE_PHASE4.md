# DIO Obligation Engine — Phase 4

## Status

Phase 4 earns the first shared **Obligation Core** runtime for DIO.

The engine is deliberately smaller than a product and more reusable than a vertical:

```text
authoritative source
      ↓
source-bound obligation candidates
      ↓
canonical normalization
      ↓
explicit deadlines
      ↓
explicit evidence bindings
      ↓
bounded fulfilment states
      ↓
Governed Case projection
      ↓
HUMAN fulfilment / escalation authority
```

It does **not** create ContractProof execution, legal authority, compliance authority, waiver authority, filing authority, external release authority, or autonomous action.

The governing doctrine remains:

> META products are compositions over the organism, not new organisms.

And for Phase 4 specifically:

> Obligation Core can establish source-bound operational evidence state. It cannot turn that state into a legal or compliance verdict.

## What becomes earned

The capability catalog advances from `1.1.0` to `1.2.0`.

The following capabilities move from `planned` to `available`:

- `obligation.extract`
- `obligation.normalize`
- `obligation.deadlines`
- `obligation.evaluate`

All four resolve through one shared provider:

```text
provider_id       = obligation_core_v1
provider_ref      = dio/obligations/engine.py
provider_kind     = shared_runtime
product_scope     = ["*"]
execution_capable = false
```

The wildcard is intentional. Obligation Core is the reusable engine for the Obligation work pattern, not a ContractProof-specific implementation.

## What remains unearned

Phase 4 does not earn:

- `product.executor.contractproof`
- a generic product executor
- ContractProof external release
- ContractProof proof-room applicability
- TenderProof execution
- GrantProof execution
- PermitProof execution
- any legal/compliance decision authority

Therefore ContractProof still compiles with:

```text
composition      = ALLOW
planning         = NEEDS_IMPLEMENTATION
execution        = REFUSE
human_review     = NEEDS_YOU
external_release = REFUSE
```

The planning gate remains incomplete because `proof.room.compile` is still unavailable for ContractProof and the product executor is still planned.

## Package shape

```text
dio/
  obligations/
    __init__.py
    models.py
    extractor.py
    normalizer.py
    deadlines.py
    evidence.py
    status.py
    engine.py
```

The module split is deliberate:

- `models.py` freezes state vocabulary, source rules, identifiers and canonical hashing;
- `extractor.py` creates bounded source-bound obligation candidates;
- `normalizer.py` produces the canonical obligation bundle;
- `deadlines.py` derives deadlines only from explicit normalized dates;
- `evidence.py` binds explicitly addressed evidence;
- `status.py` derives bounded fulfilment states;
- `engine.py` composes the pipeline, validates fingerprints and projects into Governed Case.

No vertical runtime exists inside this package.

## Canonical state vocabulary

The seven machine-produced states are:

```text
SATISFIED
PARTIAL
MISSING
CONTESTED
EXPIRED
NOT_YET_DUE
NEEDS_REVIEW
```

These states describe bounded operational evidence state. They do not mean legal compliance.

The following verdicts are explicitly reserved and forbidden as Obligation Core outputs:

```text
COMPLIANT
LEGAL
VALID
APPROVED
```

Those words require authority outside this engine.

## Extraction law

Phase 4 v0.1 accepts an authoritative source object containing a source identity, source reference, SHA-256 and clause list.

Two candidate routes exist.

### Explicit structured obligation

A clause with:

```json
{"obligation": true}
```

may become an explicit source-bound candidate. The engine preserves the source text and supplied metadata.

It does not rewrite the clause into new legal meaning.

### Conservative deontic candidate

A non-explicit clause may become a candidate only when it contains a strong marker such as:

```text
shall
must
is required to
are required to
will be required to
```

A deontic candidate is always:

```text
review_required = true
status          = NEEDS_REVIEW
```

It cannot self-promote into a fulfilment judgement.

Weak language such as `should` is not automatically promoted by v0.1.

## Source binding

Every obligation carries:

- source ID;
- source reference;
- source SHA-256;
- source locator;
- original source text.

Stable obligation IDs are derived from the source identity, locator and text.

The resulting bundle is tamper-evident through:

```text
fingerprint = sha256(canonical bundle without fingerprint field)
```

Identical bounded inputs, including the same explicit evaluation timestamp, reproduce the same bundle fingerprint.

## Deadline law

Deadline identification does not mine prose for dates in v0.1.

It uses only explicit normalized fields:

- `due_at`
- `expires_at`

Deadline states are operational:

```text
open
due
overdue
expired
```

This prevents a date-looking token in prose from silently becoming an authoritative deadline.

## Evidence binding law

Evidence is explicit in v0.1.

Each evidence record must name one or more canonical obligation IDs.

The engine does not semantically auto-match arbitrary documents to obligations.

This is intentional:

```text
similarity ≠ evidence binding
retrieval relevance ≠ fulfilment
existing file ≠ trusted evidence
```

Evidence bindings preserve:

- evidence ID;
- evidence kind;
- source reference;
- supports/contradicts relation;
- trust state;
- freshness state.

Only `trusted_for_review` supporting evidence that is not stale or expired can satisfy an explicit evidence requirement.

## Evaluation law

Evaluation order is fail-closed.

A review-required candidate remains `NEEDS_REVIEW`.

Trusted current contradictory evidence produces `CONTESTED`.

An explicit expiry timestamp in the past produces `EXPIRED`.

When explicit evidence requirements exist:

- all requirements covered by usable evidence → `SATISFIED`;
- some covered → `PARTIAL`;
- none covered and the due date is still in the future → `NOT_YET_DUE`;
- none covered otherwise → `MISSING`.

If no explicit evidence requirements exist, the engine returns `NEEDS_REVIEW` rather than inventing a sufficiency rule.

Every evaluation carries:

```text
human_gate = NEEDS_YOU
```

## Governed Case projection

`project()` maps canonical obligations into `dio.governed_case.v2` requirements using `kind = obligation`.

It may:

- create requirements;
- create requirement deadlines through the existing Governed Case API;
- link existing supporting evidence;
- raise material contradiction challenges;
- append an obligation bundle event reference.

It may not mutate:

- gates;
- actions;
- decisions.

The implementation snapshots those three authority surfaces before projection and verifies byte-equivalent canonical state afterward.

Projection emits a receipt containing:

```text
case_id
bundle_fingerprint
requirement_map
authority_created  = false
execution_performed = false
external_release   = false
```

## Work Pattern effect

ContractProof selects `WP05` Obligation.

After Phase 4:

```text
extract_obligations   RESOLVED
normalize_obligations RESOLVED
identify_deadlines    RESOLVED
bind_evidence         RESOLVED
assess_status         RESOLVED
```

Therefore:

```text
WP05 Obligation = READY
```

This means the **planning/runtime contract** is earned.

It does not mean the product is executable.

ContractProof still has:

```text
WP01 Evidence = PARTIAL
WP05 Obligation = READY
WP11 Proof = BLOCKED
```

The Work Pattern Runtime remains non-executing and continues to emit `execution_gate = REFUSE`.

## Historical regression evolution

Phase 2 and Phase 3 originally asserted that obligation capabilities were still planned. Those were capability-frontier assertions, not eternal constitutional laws.

Phase 4 updates the old regression harnesses so they now test the durable invariant:

```text
catalog says planned   → compiler/runtime must report PLANNED
catalog says available → compiler/runtime must truthfully resolve an applicable provider
```

The eternal laws remain unchanged:

- no direct organ wiring;
- deterministic provider resolution;
- explicit product scope;
- missing executor is `REFUSE`;
- human authority remains explicit;
- existing provider does not become generic by existence;
- external release is not granted by compilation.

## Operator CLI

Inspect the engine boundary:

```bash
python3 scripts/dio_obligations.py inspect
```

Evaluate a source-bound obligation document:

```bash
python3 scripts/dio_obligations.py evaluate source.json \
  --evidence evidence.json \
  --now 2026-08-12T12:00:00+00:00
```

The evidence file may be either a JSON array or:

```json
{
  "evidence_records": []
}
```

## Acceptance sequence

Run from the repository root:

```bash
python3 scripts/validate_product_constitution.py
python3 scripts/build_profile_index.py
python3 scripts/validate_profiles.py
pytest -q tests/test_product_compiler_phase2.py
python3 scripts/validate_product_compiler.py
pytest -q tests/test_work_pattern_runtime_phase3.py
python3 scripts/validate_work_pattern_runtime.py
pytest -q tests/test_obligation_engine_phase4.py
python3 scripts/validate_obligation_engine.py
python3 scripts/dio_work_patterns.py inspect contractproof
python3 scripts/dio_obligations.py inspect
```

Expected Phase 4 token:

```text
DIO_OBLIGATION_ENGINE_READY
```

## Phase 4 exit criteria

Phase 4 is complete only when:

1. source binding is mandatory;
2. extraction is conservative and inspectable;
3. deontic candidates cannot self-adjudicate;
4. all seven canonical fulfilment states are schema-bound;
5. reserved legal/authority verdicts are forbidden;
6. deadlines derive only from explicit normalized dates;
7. evidence binding is explicit;
8. stale/untrusted evidence cannot satisfy requirements;
9. trusted current contradiction produces `CONTESTED` rather than a legal verdict;
10. the bundle is fingerprinted and mutation is detected;
11. Governed Case projection cannot mutate gates, actions or decisions;
12. the four obligation capabilities resolve through one shared provider;
13. `WP05` becomes `READY` for ContractProof;
14. `WP11` remains `BLOCKED` for ContractProof;
15. `product.executor.contractproof` remains `PLANNED`;
16. ContractProof execution remains `REFUSE`;
17. external release remains `REFUSE`;
18. no TenderProof, GrantProof or PermitProof runtime has been created.

## Next boundary

The next roadmap milestone is the **ContractProof Golden Proof**.

That phase should prove one realistic contract case end-to-end against the shared Obligation Core before DIO expands the obligation family.

The test is not “can we add more products?”

The test is:

> Can ContractProof consume the shared engine without changing the engine into ContractProof?

If yes, the factory is beginning to work.
