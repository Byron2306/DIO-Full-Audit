# DIO META Runtime Consolidation — Phase 8

## Status

Phase 8 converts the four canonical META primitives from composition labels into one deterministic, inspectable runtime plane. It does not create a fifth META product, a new vertical product, a new executor or an authority layer.

```text
product manifest
  -> Product Compiler
  -> canonical META runtime plan
  -> META Evidence observation
  -> META Assurance observation
  -> META Authority observation
  -> META Room observation
  -> tamper-evident runtime receipt
```

The sole entrypoint is `products/meta_runtime.py`. Runtime contracts, dependencies, handlers and component custody remain in `config/portfolio/meta_capabilities.json`, which is already the Product Compiler's canonical META source.

## Consolidation law

The older `config/dio_meta_products.json` registry remains available for the pre-compiler nine-product portfolio and its existing acceptance proof. It is now a compatibility projection, not a competing runtime authority. Phase 8 refuses if its primitive IDs, roles or component references diverge from the canonical registry.

Vertical composition belongs in product manifests. The runtime consumes the compiler's selected META capabilities and never rewrites a product's manifest, profiles, maturity, gates, case, evidence, proof or execution receipt.

## Runtime contracts

### META Evidence

Observes Governed Case, Obligation Bundle and evidence-sufficiency identity. It reports record counts and gaps without adjudicating fulfilment.

### META Assurance

Checks artifact hashes and the product execution receipt's constitutional boundaries. It may recommend an execution block, but it cannot create one or perform an action.

### META Authority

Projects the already-compiled execution, human-review and release gates. It creates no authorization, human authority receipt, capability lease, Valinor decision or ARDA identity.

### META Room

Binds the proof fingerprint, rendered artifact hashes and prior META step receipts into the consolidated receipt. The result remains a disclosure candidate, never external-release authority.

## Phase 7 integration

ContractProof, TenderProof, GrantProof and PermitProof each resolve all four primitives in the fixed order:

```text
meta_evidence -> meta_assurance -> meta_authority -> meta_room
```

Each reference product is executed once through its existing bounded runner. The same META plan and product result are then observed twice. Phase 8 fails unless both runtime receipts are byte-semantically identical and the underlying product result remains unchanged.

## Boundaries

Phase 8 proves controlled internal runtime consolidation only. It does not prove continuous production assurance, customer validation, legal correctness, regulatory approval, market demand, revenue, scale or autonomous action.

Every step and portfolio receipt preserves:

```text
authority_created            = false
executor_created             = false
external_effects             = false
external_release_authorized  = false
human_gate                   = NEEDS_YOU
external_release_gate        = REFUSE
```

## Acceptance

```bash
pytest -q tests/test_meta_products.py tests/test_meta_runtime_phase8.py
python scripts/run_meta_runtime_phase8.py --output /tmp/dio-phase8-meta-runtime
```

Acceptance token:

```text
DIO_META_RUNTIME_CONSOLIDATED_READY
```

The next phase may build the Control Deck Portfolio OS over this single runtime receipt plane rather than teaching the UI to interrogate four separate META implementations.
