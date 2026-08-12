# DIO Product Compiler — Phase 2

Date: 2026-08-12  
Status: implementation seeded; acceptance and refusal harness added

## Deus et machina

Phase 2 is the boundary where declarative product intent becomes a deterministic governed product plan.

The compiler does **not** create new sovereignty. It does not grant execution authority, invent product maturity, infer market validation, or silently substitute an organ for a missing capability.

Its job is narrower and stronger:

```text
Product Manifest
      +
Profile bindings
      +
Work-pattern grammar
      +
META composition
      +
Earned capability catalog
      ↓
DIO Product Compiler
      ↓
Compiled governed product plan
      +
explicit unresolved capabilities
      +
explicit authority gates
      +
deterministic composition fingerprint
      +
proof receipt
```

## Canonical commands

```bash
python3 scripts/dio_product.py list
python3 scripts/dio_product.py validate contractproof
python3 scripts/dio_product.py inspect contractproof
python3 scripts/dio_product.py compile contractproof
```

`validate` and `inspect` do not write compiled artifacts.

`compile` writes under:

```text
state/compiled_products/<product_id>/
```

## Compilation artifacts

A successful compilation emits:

```text
COMPILED_PRODUCT.json
CASE_TEMPLATE.json
CAPABILITY_PLAN.json
GATE_PLAN.json
OUTPUT_PLAN.json
TEST_PLAN.json
COMPILATION_RECEIPT.json
```

The receipt contains the deterministic `composition_fingerprint` and the execution / external-release gate states at compilation time.

## Deterministic composition fingerprint

The composition fingerprint is derived from hashes of the canonical compilation inputs:

- the exact Product Manifest bytes;
- exact bound profile content hashes;
- Work Pattern registry;
- META capability registry;
- capability catalog;
- profile index;
- Product Manifest schema.

The timestamp is **not** part of the composition fingerprint. Two compilations from identical canonical inputs must therefore produce the same fingerprint.

Changing any governed input changes the fingerprint.

## Capability resolution

Canonical capability truth lives in:

```text
config/portfolio/capability_catalog.json
```

Product manifests request capability IDs. They never name concrete organs or runtime providers.

The compiler resolves a capability only from the canonical catalog. Provider selection is deterministic by priority and provider ID.

Capability states are:

- `RESOLVED`: an earned available provider satisfies the requirement;
- `PLANNED`: the capability is known but has not been earned;
- `UNAVAILABLE`: a known capability cannot currently satisfy the requirement;
- `UNKNOWN`: no canonical capability definition exists.

A `PLANNED` capability is not treated as available merely because an architecture document says it should exist.

## Execution law

The compiler enforces:

```text
missing required execution capability -> REFUSE
```

Compilation itself never promotes `maturity.operational_flags.executable`.

If a manifest claims `executable = true` while a required execution capability is unresolved, compilation refuses the manifest rather than downgrading the truth silently.

## META dependency law

Each Work Pattern declares its `primary_meta` requirements.

The compiler computes the union of required META capabilities for the selected Work Patterns and refuses a Product Manifest whose META composition is incomplete.

Thus a product cannot request `WP05 Obligation work` while quietly omitting META Authority.

## Profile binding law

Every profile reference in a Product Manifest must match the canonical profile index on:

- profile ID;
- profile class;
- profile version;
- exact profile content SHA-256.

A stale or tampered profile reference refuses compilation.

## ContractProof reference compilation

Phase 2 introduces:

```text
config/products/manifests/contractproof.json
```

It is intentionally an **internal**, `composed`, non-executable incarnation.

It composes:

```text
WP01 Evidence
WP05 Obligation
WP11 Proof

META Evidence
META Assurance
META Authority
META Room
```

with the six Phase 1 reference profiles.

Currently earned capabilities resolve for:

- Governed Case materialisation;
- evidence provenance;
- evidence linking;
- proof-room compilation.

The following remain intentionally `PLANNED` until later phases:

- `obligation.extract`;
- `obligation.normalize`;
- `obligation.deadlines`;
- `obligation.evaluate`;
- `product.executor.contractproof`.

Therefore the expected Phase 2 ContractProof gates are:

```text
composition      = ALLOW
planning         = NEEDS_IMPLEMENTATION
execution        = REFUSE
human_review     = NEEDS_YOU
external_release = REFUSE
```

That is a successful Phase 2 compilation.

## Refusal harness

Run:

```bash
python3 scripts/validate_product_compiler.py
```

The acceptance harness proves positive compilation and negative constitutional behaviour.

It must refuse:

1. a Product Manifest that attempts direct `organs` wiring;
2. a product whose selected Work Patterns require a META primitive omitted by the manifest;
3. a manifest whose bound profile content hash is stale or tampered;
4. execution without an earned execution-capable provider.

It also proves that identical governed inputs reproduce the same composition fingerprint.

Expected final token:

```text
DIO_PRODUCT_COMPILER_READY
```

## Phase 2 exit criteria

Phase 2 is complete only when:

1. Phase 0 constitution still passes;
2. Phase 1 profiles still pass;
3. `contractproof` validates;
4. `contractproof` compiles into the seven canonical artifacts;
5. deterministic fingerprint reproduction passes;
6. direct organ wiring is refused;
7. incomplete META composition is refused;
8. stale profile binding is refused;
9. missing ContractProof executor remains `REFUSE`;
10. internal-only external release remains `REFUSE`;
11. the final token is `DIO_PRODUCT_COMPILER_READY`.

## Phase boundary

Phase 2 does **not** implement Obligation Core.

The compiler is now allowed to tell DIO exactly what is missing. Phase 3 formalises reusable Work Pattern runtime contracts, and the subsequent Obligation phase earns the capabilities currently visible as `PLANNED`.

No bespoke `contractproof.py`, `tenderproof.py`, `grantproof.py` or `permitproof.py` is introduced by this phase.
