# Customer Journey Phase 8 — 68-Product Binding & Final Commercial Gauntlet

**Goal:** Bind all 68 verified commercial products to the shared Customer Journey Spine without bespoke commerce plumbing, unknown fulfilment routes, portfolio drift, or authority leakage.

## Architecture

Phase 8 introduces a product-binding compiler over existing frozen truth:

1. 53 historical products + 15 canon extensions from the commercial pricing registry.
2. Phase 0's eight journey archetypes.
3. Phase 7's proved fulfilment families.
4. Two final native routes required by the complete portfolio:
   - Market / opportunity intelligence via Market Command read/intelligence plane.
   - Vesper case service via the Phase 6 Journey Runtime.
5. Existing Phase 1–6 lifecycle contracts remain the only customer-lifecycle implementation.

Products declare only a route and profiles. The compiler resolves the route into an execution provider and emits a hash-bound `dio.fulfilment_execution_profile.v1`. Product rows do not own lifecycle transitions.

## Truth boundary

Phase 8 proves **Customer Journey Spine binding for 68/68 commercial products**. It does not invent missing canonical Product Compiler manifests or promote source maturity. Where a canonical product manifest exists it is hash-linked; where it does not, the binding says so explicitly.

## Required gates

- [ ] Exactly 68 unique commercial products compile.
- [ ] Historical truth remains 53 + 15.
- [ ] Every product has exactly one archetype A–H.
- [ ] Every product has exactly one known fulfilment route.
- [ ] Required/optional inputs come from the Phase 2 contract.
- [ ] Scope rules and pricing are identical to the commercial registry.
- [ ] Quote authority remains explicit and unchanged.
- [ ] Settlement classes remain typed; controlled tests never become revenue.
- [ ] Human/professional/legal gates are explicit.
- [ ] Deliverable and release profiles are explicit.
- [ ] Delivery channels are explicit.
- [ ] No product-specific lifecycle implementation exists in the binding registry.
- [ ] No compiled execution profile creates authority.
- [ ] Representative controlled/live evidence exists across all eight archetypes.
- [ ] Archetype F uses the real Market Command intelligence plane.
- [ ] Archetype H uses the real Vesper Journey Runtime.
- [ ] Phase 2, Phase 4, Phase 6 and Phase 7 compatibility remains green.

## Exit token

`DIO_CUSTOMER_JOURNEY_PHASE8_68_PRODUCT_BINDING_VERIFIED`

Emit only if:

```text
PORTFOLIO_BINDING=68/68
UNKNOWN_ARCHETYPES=0
UNKNOWN_FULFILMENT_ROUTES=0
BESPOKE_COMMERCE_PIPELINES=0
AUTHORITY_LEAKS=0
ARCHETYPE_GAUNTLET=8/8
DIO_CUSTOMER_JOURNEY_PHASE8_68_PRODUCT_BINDING_VERIFIED
```
