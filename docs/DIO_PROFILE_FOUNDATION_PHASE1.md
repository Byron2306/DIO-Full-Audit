# DIO Profile Foundation — Phase 1

Date: 2026-08-12
Status: implementation seeded; acceptance gate added

## Objective

Phase 1 turns the six profile classes frozen in the Product Constitution into independently validating, source/version/hash-bound configuration objects.

Profiles remain declarative. They do not create executors, execution authority, product maturity, market validation or revenue proof.

## Canonical schema

Every concrete profile uses:

```text
schemas/dio_profile.schema.json
```

Canonical profile classes remain exactly:

- domain
- framework
- authority
- connector
- output
- commercial

## Binding contract

Every Phase 1 profile must bind to at least one explicit source with:

- source reference;
- source version;
- SHA-256 content hash;
- source kind;
- authority level.

A changed source therefore invalidates the profile binding until the profile is deliberately reviewed and rebound.

`externally_validated` is permitted only when at least one bound source has `authority_level = externally_authoritative`.

## First reference profile set

The first six profiles exist to prepare the Obligation-family build without pretending the generic contract model is already legal-domain validated:

```text
config/profiles/domains/project_delivery.json
config/profiles/frameworks/contract_generic.json
config/profiles/authorities/contract_owner.json
config/profiles/connectors/files_readonly.json
config/profiles/outputs/evidence_pack.json
config/profiles/commercial/internal_proof.json
```

Their shared internal source contract is:

```text
docs/DIO_PHASE1_REFERENCE_PROFILE_SOURCES.md
```

These profiles are source-bound to an internal design source and remain below external validation.

## Acceptance gate

Run:

```bash
python3 scripts/validate_product_constitution.py
python3 scripts/validate_profiles.py
```

Expected final token:

```text
DIO_PROFILE_FOUNDATION_READY
```

The profile gate verifies:

- all six profile classes have concrete instances;
- class and path agree;
- required class-specific semantics exist;
- source references exist inside the repository;
- stored SHA-256 hashes match current source bytes;
- profiles contain no executor, maturity or market-proof state;
- an externally validated profile cannot be backed only by internal-reference sources;
- internal-only commercial policy prohibits charging, external delivery and autonomous release.

## Phase boundary

Phase 1 does not implement the Product Compiler or Obligation Engine.

Once the constitutional gate and profile gate both pass, Phase 2 may begin with product `validate`, `compile` and `inspect` operations over manifests that reference these profiles.
