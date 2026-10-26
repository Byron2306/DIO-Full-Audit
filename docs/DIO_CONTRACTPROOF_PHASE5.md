# DIO ContractProof Golden Proof — Phase 5

## Status

Phase 5 is the first end-to-end proof of a DIO commercial composition built from shared organism capabilities rather than a bespoke parallel core.

The governing test is:

> Can ContractProof consume shared Evidence, Obligation and Governed Case machinery, add only the bounded product-specific seams it genuinely needs, and produce a portable proof pack without inventing contractual authority?

Phase 5 answers that question with one controlled internal golden case.

## Product composition

ContractProof selects:

- `WP01` Evidence;
- `WP05` Obligation;
- `WP11` Proof;
- META Evidence;
- META Assurance;
- META Authority;
- META Room.

The product remains bound to the six Phase 1 reference profiles, including:

- `framework.contract_generic`;
- `authority.contract_owner`;
- `connector.files_readonly`;
- `output.evidence_pack`;
- `commercial.internal_proof`.

## What Phase 5 earns

The capability catalog advances to `1.3.0`.

### Shared evidence frontier

Phase 5 exposes conservative review-readiness functions already grounded in canonical Evidence Intelligence:

- `evidence.sufficiency`;
- `evidence.gaps`.

Both resolve through:

```text
evidence_sufficiency_v1
ref = evidence/sufficiency.py
product_scope = ["*"]
execution_capable = false
```

The state `READY_FOR_HUMAN_REVIEW` is not a contractual fulfilment, compliance, legal, approval or release verdict.

### Shared Obligation Core

Phase 4 remains unchanged as the shared obligation engine:

- `obligation.extract`;
- `obligation.normalize`;
- `obligation.deadlines`;
- `obligation.evaluate`.

All four continue to resolve through `obligation_core_v1`, wildcard scoped and non-executing.

ContractProof does not fork Obligation Core.

### Product-scoped Proof adapter

ContractProof earns a bounded provider:

```text
contractproof_proof_pack_v1
ref = products/contractproof/proof.py
product_scope = ["dio_contractproof"]
execution_capable = false
```

It satisfies:

- `proof.room.compile`;
- `proof.integrity.verify`;
- `proof.disclosure.prepare`.

This does **not** broaden CapitalRoom.

The pre-existing `capitalroom_proof_room` provider continues to exclude `dio_contractproof`. Provider existence is still not genericity.

### Bounded internal executor

ContractProof earns:

```text
product.executor.contractproof
provider = contractproof_internal_runner_v1
ref = products/contractproof/runner.py
product_scope = ["dio_contractproof"]
execution_capable = true
```

The executor may:

- run a human-initiated internal case;
- materialise Governed Case state;
- bind supplied evidence to explicit obligation locators;
- invoke shared Obligation Core;
- assess evidence review-readiness;
- compile local proof artifacts;
- verify artifact integrity;
- emit an internal execution receipt.

It may not:

- decide contractual fulfilment on behalf of the owner;
- issue a legal opinion;
- create a waiver;
- create authority;
- perform external side effects;
- send or publish the proof pack;
- grant external release.

## Compiler v1.1 execution law

Golden Proof exposed a latent authority bug in the original Phase 2 compiler.

The original implementation had an unreachable-at-the-time branch equivalent to:

```text
executable=true + executor resolved -> execution ALLOW
```

While no executor existed this did not grant anything. Phase 5 made the branch reachable, so the compiler law was corrected before the executor was accepted.

Compiler `1.1.0` now enforces:

```text
missing required execution capability -> REFUSE
earned bounded execution capability   -> NEEDS_YOU
autonomous compiler execution         -> never ALLOW
```

This is a semantic hardening, not a relaxation.

The Work Pattern Runtime remains non-executing and continues to emit:

```text
execution_gate = REFUSE
```

It may observe the compiler's `NEEDS_YOU`, but it cannot turn that into execution authority.

## Exact Evidence Pack output profile

Phase 5 follows the live `output.evidence_pack` profile rather than inventing a convenient product-specific output contract.

Required artifact types are exactly:

1. `JSON`
2. `DOCX`
3. `PDF`
4. `HTML`
5. `proof_room_manifest`

The golden executor therefore emits:

```text
EVIDENCE_PACK.json
EVIDENCE_PACK.docx
EVIDENCE_PACK.pdf
EVIDENCE_PACK.html
PROOF_MANIFEST.json
```

DOCX and PDF are rendered deterministically with the Python standard library so Golden Proof does not depend on a hidden office-installation side effect.

The semantic pack must preserve all seven profile-required sections:

1. `requirement_or_obligation_ledger`
2. `evidence_map`
3. `missing_evidence_register`
4. `contested_state_register`
5. `deadline_register`
6. `human_review_register`
7. `provenance_manifest`

The profile's disclosure and QA rules remain binding. Missing and contested evidence may not be silently omitted.

## Proof identity and tamper detection

`PROOF_MANIFEST.json` binds:

- case identity;
- Obligation Bundle fingerprint;
- required section set;
- artifact type;
- filename;
- SHA-256 of every rendered child artifact.

`proof_fingerprint` is recomputed during verification from the manifest identity itself.

Therefore the verifier detects:

- missing artifacts;
- changed JSON/DOCX/PDF/HTML bytes;
- omitted required artifact types;
- changed proof-manifest identity.

Integrity verification does not authorize disclosure.

A verified pack becomes only:

```text
INTERNAL_REVIEW_CANDIDATE
human_gate = NEEDS_YOU
external_release_gate = REFUSE
```

## Golden reference case

Canonical fixtures live under:

```text
config/products/golden/contractproof/
  reference_contract.json
  reference_evidence.json
```

The reference case is deliberately imperfect.

At the fixed golden evaluation time:

```text
2026-08-12T12:00:00+00:00
```

it must produce exactly:

```text
SATISFIED     = 1
MISSING       = 1
PARTIAL       = 1
EXPIRED       = 1
NOT_YET_DUE   = 1
NEEDS_REVIEW  = 1
```

Evidence review-readiness must remain:

```text
GAPS_PRESENT
```

This is intentional.

Golden Proof proves that ContractProof can preserve inconvenient truth. It does not require a fake all-green contract.

## Maturity

Phase 5 promotes ContractProof from:

```text
COMPOSED
```

to:

```text
INTERNAL PROOF
```

The manifest flags are:

```text
routable                    = true
governable                  = true
executable                  = true
campaign_enabled            = false
externally_validated        = false
continuous_assurance_ready  = false
revenue_proven              = false
```

`executable=true` means a bounded valid executor exists. It does not mean autonomous execution is permitted.

The compiler gate remains `NEEDS_YOU`.

The commercial profile remains `internal_only`, so external release remains `REFUSE`.

## Operator CLI

Inspect current composition:

```bash
python3 scripts/dio_contractproof.py inspect
```

Run the canonical golden case:

```bash
python3 scripts/dio_contractproof.py golden
```

Default output:

```text
state/golden_proofs/dio_contractproof/reference/
```

Verify the generated proof pack:

```bash
python3 scripts/dio_contractproof.py verify
```

Golden execution requires an explicit operator identity. The operator triggers bounded internal processing; the operator identity is not converted into a contractual fulfilment or disclosure decision.

## Acceptance sequence

Run from repository root:

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

pytest -q tests/test_contractproof_phase5.py
python3 scripts/validate_contractproof_phase5.py

python3 scripts/dio_contractproof.py inspect
python3 scripts/dio_contractproof.py golden
python3 scripts/dio_contractproof.py verify
```

Phase 5 acceptance token:

```text
DIO_CONTRACTPROOF_GOLDEN_READY
```

## Exit criteria

Phase 5 is complete only when:

1. all ContractProof required capabilities resolve;
2. WP01, WP05 and WP11 are all `READY`;
3. Work Pattern Runtime remains non-executing;
4. compiler execution is `NEEDS_YOU`, never `ALLOW`;
5. external release remains `REFUSE`;
6. CapitalRoom scope remains unchanged and truthful;
7. shared Obligation Core remains generic and non-executing;
8. the bounded executor is ContractProof-scoped;
9. an explicit human operator is required to run it;
10. the golden case preserves all six expected obligation states;
11. evidence sufficiency remains `GAPS_PRESENT` for the imperfect golden case;
12. all five output-profile artifact types are emitted;
13. all seven semantic sections are present;
14. child artifact tampering is detected;
15. proof-manifest identity tampering is detected;
16. no fulfilment authority, legal opinion or waiver is created;
17. no external side effect occurs;
18. maturity is `internal_proof`, not pilot/customer/revenue maturity.

## Phase boundary

Phase 5 does not create:

- TenderProof;
- GrantProof;
- PermitProof;
- external ContractProof delivery;
- campaign permission;
- customer validation;
- legal opinion authority;
- autonomous execution.

The next roadmap milestone is **Phase 6: Obligation Family Expansion**.

The factory test becomes:

> Can TenderProof, GrantProof and PermitProof be composed primarily from profiles, manifests, output templates and small adapters without modifying Obligation Core?

If yes, DIO has moved from one golden product to a genuine product factory.
