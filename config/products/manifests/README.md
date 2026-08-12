# DIO Product Manifests

This directory is the canonical composition authority for DIO products/incarnations.

A manifest states **what** a product requires: work patterns, META primitives, profile references and capability requirements. It never hard-codes organs or contains executor implementation.

The deterministic Product Compiler is operated with:

```bash
python3 scripts/dio_product.py list
python3 scripts/dio_product.py validate contractproof
python3 scripts/dio_product.py inspect contractproof
python3 scripts/dio_product.py compile contractproof
```

Compiler-generated plans are derived artifacts under `state/compiled_products/`. They are never edited back into source manifests.

The first canonical reference manifest is:

```text
contractproof.json
```

Its lifecycle demonstrates that capability truth may advance without changing the product-composition law:

- Phase 2: `COMPOSED`, missing executor -> execution `REFUSE`;
- Phase 3: work-pattern contracts made the missing frontier explicit;
- Phase 4: shared Obligation Core earned WP05 without becoming a ContractProof executor;
- Phase 5: the internal golden proof earns the remaining WP01/WP11 providers plus a product-scoped bounded ContractProof executor.

ContractProof remains **internal-only** in Phase 5. Its maturity is `internal_proof`: routable, governable and executable for controlled internal processing, but not campaign-enabled, externally validated, continuous-assurance ready or revenue proven.

Compiler v1.1 preserves the authority boundary:

```text
missing required execution provider -> REFUSE
earned bounded execution provider   -> NEEDS_YOU
compiler autonomous execution        -> never ALLOW
```

The Phase 5 executor may process a human-initiated internal case and write local proof artifacts. It cannot decide contractual fulfilment, create a waiver or legal opinion, perform external effects, or release the pack externally.

`proof.room.compile` remains provider-scoped. CapitalRoom's existing provider still excludes ContractProof; ContractProof uses its own bounded proof-pack adapter rather than pretending CapitalRoom is generic.

`config/dio_meta_products.json#vertical_compositions` remains compatibility evidence only. New product composition truth belongs here.

See:

- `docs/DIO_PRODUCT_COMPILER_PHASE2.md`
- `docs/DIO_WORK_PATTERN_RUNTIME_PHASE3.md`
- `docs/DIO_OBLIGATION_ENGINE_PHASE4.md`
- `docs/DIO_CONTRACTPROOF_PHASE5.md`
