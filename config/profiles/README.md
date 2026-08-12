# DIO Profile Library

Phase 1 turns the six profile classes frozen by the Product Constitution into concrete, independently validating configuration objects:

- `domains/`
- `frameworks/`
- `authorities/`
- `connectors/`
- `outputs/`
- `commercial/`

Canonical schema:

```text
schemas/dio_profile.schema.json
```

Profiles are declarative configuration. They may not create authority, executors, product maturity, market validation or revenue proof.

Every concrete Phase 1 profile is source/version/hash-bound. A changed source invalidates the binding until deliberate review and rebinding occur.

The first reference set supports the future Obligation-family build while remaining explicitly internal-proof grade:

```text
domains/project_delivery.json
frameworks/contract_generic.json
authorities/contract_owner.json
connectors/files_readonly.json
outputs/evidence_pack.json
commercial/internal_proof.json
```

Run:

```bash
python3 scripts/validate_product_constitution.py
python3 scripts/validate_profiles.py
```

Expected Phase 1 token:

```text
DIO_PROFILE_FOUNDATION_READY
```

See `docs/DIO_PROFILE_FOUNDATION_PHASE1.md` for the binding contract and exit criteria.
