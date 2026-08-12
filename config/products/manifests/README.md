# DIO Product Manifests

This directory is the canonical composition authority for DIO products/incarnations.

A manifest states **what** a product requires: work patterns, META primitives, profile references and capability requirements. It does not hard-code organs or create executors.

Phase 2 adds the deterministic Product Compiler:

```bash
python3 scripts/dio_product.py list
python3 scripts/dio_product.py validate contractproof
python3 scripts/dio_product.py inspect contractproof
python3 scripts/dio_product.py compile contractproof
```

Compiler-generated runtime plans are derived artifacts under `state/compiled_products/`. They are never edited back into source manifests.

The first canonical reference manifest is:

```text
contractproof.json
```

It is intentionally internal-only and non-executable. The compiler resolves already-earned shared capabilities and leaves future Obligation capabilities explicitly `PLANNED`.

If a required execution capability has no valid execution-capable provider, the governed state is `REFUSE`, not an unhandled error and never an inferred permission.

`config/dio_meta_products.json#vertical_compositions` remains compatibility evidence only. New product composition truth belongs here.

See `docs/DIO_PRODUCT_COMPILER_PHASE2.md`.
