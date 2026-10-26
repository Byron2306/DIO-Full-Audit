# DIO Work Pattern Runtime — Phase 3

## Status

Phase 3 introduces the first canonical runtime contract layer for DIO work patterns.

It does **not** create a new product runtime, a generic executor, execution authority, or a replacement for specialist organs.

The governing principle is:

> Work patterns define stable operational contracts. Capabilities satisfy those contracts. Products request the contracts through their composition. Organs remain implementation providers behind capability resolution.

This preserves the Phase 0–2 doctrine:

- one DIO organism;
- products request capabilities, never organs;
- provider existence is not genericity;
- planned capability is not earned capability;
- Valinor remains kernel authority;
- ARDA remains execution identity / attestation authority;
- human authority remains explicit and inspectable;
- missing required execution capability remains `REFUSE`.

## Phase 3 objective

Turn the canonical twelve work patterns from portfolio grammar into stable, machine-validating runtime contracts while refusing to invent capability DIO has not earned.

Phase 3 focuses operational detail on five patterns:

1. `WP01` Evidence
2. `WP05` Obligation
3. `WP08` Intake
4. `WP10` Document
5. `WP11` Proof

The other seven canonical patterns are registered as declared contracts so the runtime vocabulary is complete without pretending their operational interfaces have been earned in this phase.

## New canonical artifacts

### Runtime registry

`config/portfolio/work_pattern_runtime.json`

Defines:

- exactly twelve canonical work-pattern contracts;
- the five Phase 3 focus patterns;
- input contracts;
- output contracts;
- inherited human boundaries;
- operation-to-capability requirements;
- no provider references;
- no organ references;
- no execution-required operations.

### Runtime schema

`schemas/dio_work_pattern_runtime.schema.json`

Rejects direct provider wiring and constrains Phase 3 operation contracts to non-executing capability requirements.

### Runtime planner

`products/work_pattern_runtime.py`

Resolves work-pattern operations through the same canonical capability catalog used by the Product Compiler.

The runtime planner never imports or selects an organ directly. It delegates capability resolution to the compiler's deterministic provider-resolution law, including product-scope checks.

Per-operation resolution states remain:

- `RESOLVED`
- `PLANNED`
- `UNAVAILABLE`
- `UNKNOWN`

Per-pattern runtime states are derived, never asserted:

- `READY` — every operation is resolved;
- `PARTIAL` — some operations are resolved and the remainder are planned;
- `PLANNED` — every operation is planned;
- `BLOCKED` — at least one operation is unavailable or unknown;
- `DECLARED` — canonical contract exists but Phase 3 has not bound operations yet.

A `READY` work pattern still does not grant execution authority. Phase 3 is a planning runtime and its execution gate is always `REFUSE`.

## Capability frontier added in Phase 3

The capability catalog version advances to `1.1.0`.

New capabilities are deliberately registered as **planned** with no providers:

### Evidence

- `evidence.sufficiency`
- `evidence.gaps`

### Intake

- `intake.normalize`
- `intake.classify`
- `intake.missing_information`

### Document

- `document.project`
- `document.qa`
- `document.release.prepare`

### Proof

- `proof.integrity.verify`
- `proof.disclosure.prepare`

No code module is promoted to a generic provider merely because it exists somewhere in the repository.

## ContractProof as the Phase 3 reference composition

ContractProof selects:

- `WP01` Evidence
- `WP05` Obligation
- `WP11` Proof

The expected Phase 3 runtime plan is intentionally incomplete.

### WP01 Evidence — `PARTIAL`

Earned and reusable:

- governed case materialisation;
- evidence provenance;
- evidence linking.

Still planned:

- sufficiency assessment;
- gap emission.

### WP05 Obligation — `PARTIAL`

Earned and reusable:

- generic evidence linking.

Still planned for Phase 4 Obligation Core:

- obligation extraction;
- obligation normalisation;
- deadline identification;
- fulfilment evaluation.

Phase 3 therefore does **not** implement Obligation Core.

### WP11 Proof — `BLOCKED`

`proof.room.compile` has an earned provider in CapitalRoom, but that provider does not declare applicability to `dio_contractproof`.

Therefore the runtime reports the operation as `UNAVAILABLE` rather than treating existing code as generic capability.

Also still planned:

- proof integrity verification;
- disclosure preparation.

This distinction is deliberate:

> Existing provider ≠ applicable provider ≠ generic provider.

## Authority boundary

Every planned work pattern preserves the canonical human boundary as a `NEEDS_YOU` gate.

The Phase 3 runtime emits:

- `authority_created = false`
- `executor_created = false`
- `execution_gate = REFUSE`

For a canonical manifest it also carries the Product Compiler execution gate so the runtime cannot silently relax the compiler's decision.

## CLI

List contracts:

```bash
python3 scripts/dio_work_patterns.py list
```

Inspect ContractProof without executing anything:

```bash
python3 scripts/dio_work_patterns.py inspect contractproof
```

Validate the ContractProof runtime plan:

```bash
python3 scripts/dio_work_patterns.py validate contractproof
```

Expected validation token:

```text
DIO_WORK_PATTERN_PLAN_VALID
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
python3 scripts/dio_work_patterns.py inspect contractproof
```

Phase 3 acceptance token:

```text
DIO_WORK_PATTERN_RUNTIME_READY
```

## Fingerprint note

Phase 3 expands `config/portfolio/capability_catalog.json`. The Product Compiler intentionally includes the capability-catalog hash in product composition identity.

Therefore a ContractProof compilation minted after Phase 3 will have a different composition/compilation fingerprint from a Phase 2 receipt minted before this catalog expansion, even though `products/compiler.py` itself is unchanged.

That is expected and desirable. The old receipt remains historical evidence of the exact Phase 2 composition; a new compile represents the current Phase 3 capability frontier.

## Phase 3 exit boundary

Phase 3 is complete when:

1. all twelve canonical work patterns have validated contracts;
2. the five focus patterns have explicit input/output/operation contracts;
3. operations request capabilities rather than organs/providers;
4. all operation capability IDs exist in the canonical catalog;
5. provider applicability remains product-scoped;
6. new capability frontier entries remain planned until earned;
7. ContractProof Evidence reports `PARTIAL`;
8. ContractProof Obligation reports `PARTIAL` and exposes the Phase 4 frontier;
9. ContractProof Proof reports `BLOCKED` because the existing proof provider is inapplicable;
10. every selected pattern retains its human boundary;
11. Phase 3 creates neither authority nor executors;
12. Product Compiler execution for ContractProof remains `REFUSE`;
13. no Obligation Engine has been implemented.

## What Phase 3 deliberately does not do

Phase 3 does not:

- implement Obligation Core;
- create `product.executor.contractproof`;
- make ContractProof executable;
- broaden CapitalRoom's proof provider scope;
- promote Document Studio or Vesper modules to generic providers without explicit earned applicability;
- modify Valinor or ARDA authority;
- create TenderProof, GrantProof, or PermitProof vertical runtimes.

Those boundaries are features, not missing ambition.

Phase 3 gives DIO a reusable operational grammar with teeth while keeping the teeth behind the right gates.
