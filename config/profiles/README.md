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

Canonical concrete-profile index:

```text
config/profiles/index.json
```

Profiles are declarative configuration. They may not create authority, executors, product maturity, market validation or revenue proof.

Every concrete Phase 1 profile is source/version/hash-bound. A changed source invalidates the binding until deliberate review and rebinding occur. The index separately binds each profile ID/version to the SHA-256 of the concrete profile bytes used later by product manifests.

The first reference set supports the future Obligation-family build while remaining explicitly internal-proof grade:

```text
domains/project_delivery.json
frameworks/contract_generic.json
authorities/contract_owner.json
connectors/files_readonly.json
outputs/evidence_pack.json
commercial/internal_proof.json
```

After changing a profile, rebuild its deterministic index before strict validation:

```bash
python3 scripts/build_profile_index.py
```

Then run:

```bash
python3 scripts/validate_product_constitution.py
python3 scripts/validate_profiles.py
```

Expected Phase 1 token:

```text
DIO_PROFILE_FOUNDATION_READY
```

See `docs/DIO_PROFILE_FOUNDATION_PHASE1.md` for the binding contract and exit criteria.
