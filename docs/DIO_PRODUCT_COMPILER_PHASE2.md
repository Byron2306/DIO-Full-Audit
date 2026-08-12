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
deterministic composition identity
      +
compiler-bound compilation identity
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

Only manifests under:

```text
config/products/manifests/
```

may be compiled. Product IDs and incarnation IDs must be unique, and the manifest filename must equal the incarnation ID.

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

The receipt preserves both product-composition identity and compiler-bound compilation identity, plus execution and external-release gate states.

## Two fingerprints, two truths

Phase 2 deliberately separates **composition identity** from **compilation identity**.

### Composition fingerprint

`composition_fingerprint` identifies the canonical product composition and is derived from:

- exact Product Manifest bytes;
- exact bound profile content hashes;
- Work Pattern registry;
- META capability registry;
- capability catalog;
- profile index;
- Product Manifest schema.

The compiler implementation itself is not part of this identity. This lets DIO distinguish “the same product composition” from “the exact compiler build that produced this plan.”

### Compilation fingerprint

`compilation_fingerprint` binds the resulting governed plan to:

- the composition fingerprint;
- compiler version;
- SHA-256 of `products/compiler.py`;
- Compiled Product schema SHA-256;
- deterministic SHA-256 of the compiled plan before the compilation fingerprint is inserted.

Thus:

```text
same composition + different compiler implementation
→ same composition identity may remain
→ compilation identity MUST change
```

Timestamps are excluded from both deterministic fingerprints.

## Capability resolution

Canonical capability truth lives in:

```text
config/portfolio/capability_catalog.json
```

Product manifests request capability IDs. They never name concrete organs or runtime providers.

The compiler resolves a capability only from the canonical catalog. Provider selection is deterministic by priority and provider ID.

Every earned provider declares a `product_scope`. A provider is usable only when its scope includes the product ID or the explicit wildcard `*`.

This prevents a dangerous shortcut:

```text
relevant code exists != generic capability != provider applies to this product
```

Capability states are:

- `RESOLVED`: an earned available provider explicitly applies to the product and satisfies the requirement;
- `PLANNED`: the capability is known but has not been earned;
- `UNAVAILABLE`: a known capability cannot currently satisfy this product/requirement;
- `UNKNOWN`: no canonical capability definition exists.

A `PLANNED` capability is never treated as available merely because architecture says it should exist. An existing provider is never treated as generic merely because its file exists.

## Execution law

The compiler enforces:

```text
missing required execution capability -> REFUSE
```

Compilation itself never promotes `maturity.operational_flags.executable`.

If a manifest claims `executable = true` while a required execution capability is unresolved, compilation refuses the manifest rather than silently downgrading truth.

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

## Commercial contradiction law

An `internal_only` commercial profile cannot coexist with:

```text
campaign_enabled = true
```

That combination is refused rather than translated into ambiguous runtime behaviour.

External release is never granted by compilation alone.

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

Currently earned generic capabilities resolve for:

- Governed Case materialisation;
- evidence provenance;
- evidence linking.

`CapitalRoom` exists as an earned proof-room provider, but its current implementation is scoped to the existing registered products and does **not** include `dio_contractproof`. Therefore:

```text
proof.room.compile = UNAVAILABLE
```

for ContractProof in Phase 2.

The following remain intentionally `PLANNED`:

- `obligation.extract`;
- `obligation.normalize`;
- `obligation.deadlines`;
- `obligation.evaluate`;
- `product.executor.contractproof`.

Expected ContractProof gates:

```text
composition      = ALLOW
planning         = NEEDS_IMPLEMENTATION
execution        = REFUSE
human_review     = NEEDS_YOU
external_release = REFUSE
```

That is a successful Phase 2 compilation.

## Refusal and regression harnesses

Primary acceptance:

```bash
python3 scripts/validate_product_compiler.py
```

Regression contract:

```bash
pytest -q tests/test_product_compiler_phase2.py
```

The harnesses prove positive compilation and negative constitutional behaviour.

They must refuse or withhold capability for:

1. a Product Manifest that attempts direct `organs` wiring;
2. a product whose Work Patterns require a META primitive omitted by the manifest;
3. a manifest whose bound profile content hash is stale or tampered;
4. execution without an earned execution-capable provider;
5. an existing provider whose declared product scope does not include the product;
6. an internal-only commercial profile paired with campaign enablement;
7. compilation from outside the canonical manifest registry.

They also prove deterministic reproduction of both fingerprints under unchanged inputs and unchanged compiler source.

Expected final token:

```text
DIO_PRODUCT_COMPILER_READY
```

## Phase 2 exit criteria

Phase 2 is complete only when:

1. Phase 0 constitution passes;
2. Phase 1 profiles pass;
3. `contractproof` validates as a canonical manifest;
4. `contractproof` compiles into the seven canonical artifacts;
5. composition fingerprint reproduction passes;
6. compiler-bound compilation fingerprint reproduction passes;
7. direct organ wiring is refused;
8. incomplete META composition is refused;
9. stale profile binding is refused;
10. provider applicability scope is enforced;
11. missing ContractProof executor remains `REFUSE`;
12. internal-only external release remains `REFUSE`;
13. regression tests pass;
14. the final token is `DIO_PRODUCT_COMPILER_READY`.

## Phase boundary

Phase 2 does **not** implement Obligation Core.

The compiler is now allowed to tell DIO exactly what is missing. Phase 3 formalises reusable Work Pattern runtime contracts, and the subsequent Obligation phase earns the capabilities currently visible as `PLANNED` or `UNAVAILABLE`.

No bespoke `contractproof.py`, `tenderproof.py`, `grantproof.py` or `permitproof.py` is introduced by this phase.
