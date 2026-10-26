# Product Layers

The suite is stratified into product layers so each offer can be sold, routed, governed, and marketed separately while sharing the same DIO commercial spine.

## Shared shape

```text
Inbox / form / file intake
-> product route
-> canonical job
-> governed case
-> evidence + requirements + claims
-> approval / authority gates
-> product-specific processing
-> human review
-> governed output / delivery
-> commercial and learning feedback
```

Existing proven or controlled-pilot layers remain configured in:

```text
config/product_layers.json
```

The new governed product portfolio is configured in:

```text
config/dio_product_portfolio.json
```

The two files deliberately mean different things:

- `product_layers.json` describes existing product/service layers with current fulfilment proof;
- `dio_product_portfolio.json` registers new product slots that DIO can classify, govern and plan before their product-specific executors are proven.

## Existing layer roles

- **Evidex**: first productized evidence-pack cash offer.
- **HOMS**: education marking, assessment, exam and learning-production vertical.
- **Outlook Triage**: intake router and standalone inbox-control offer.
- **VAMP**: performance and institutional evidence mapping.
- **Sophia**: academic/research review with persistent evidence and human authorship boundaries.
- **DIO Document Studio**: technical editing, translation, semantic QA and governed formatting.
- **NicheFoundry**: shared campaign/media production infrastructure rather than a default standalone product.

## Wave 1 portfolio layers

- **DIO Assurance**: AI inventory, controls, claim lineage, evidence and assurance-readiness.
- **DIO Agent Authority**: governed action proposals, dissent, capability authority and execution receipts.
- **DIO VendorProof**: third-party/vendor questionnaire and evidence review.
- **DIO Accreditation**: institutional standards-to-evidence and corrective-action readiness.
- **DIO TenderProof**: tender/RFP requirements, mandatory gates, evidence and locked submission preparation.
- **DIO GrantProof**: persistent grant obligation, indicator and reporting-period evidence lineage.
- **DIO Research Integrity**: stable claim/source/revision and human decision lineage.
- **DIO RegOps**: operational prerequisites, evidence, deadlines and readiness gates.
- **DIO CapitalRoom**: internal-only investor fit, claim evidence and diligence management.

## Current truth boundary

A Wave 1 portfolio product is **not** automatically production-ready.

Registration currently proves that DIO can define the product's:

- buyer and bounded problem;
- intake route;
- evidence requirements;
- human authorities;
- expected outputs;
- risk boundary;
- activation gates;
- canonical `JOB.json`;
- canonical `CASE.json`.

The generic runtime deliberately records:

```text
classification = registered
planning = enabled
processing = not_started
execution = not_implemented
external_release = held
```

A product becomes executable only after a product-specific parser/runner, validation receipt, human review contract and release path are implemented and proven.

See:

```text
docs/DIO_PRODUCT_PLATFORM_WAVE1.md
schemas/dio_product_request.schema.json
schemas/dio_governed_case.schema.json
products/registry.py
scripts/reconcile_product_portfolio.py
```

## Campaign purpose

Existing Phase 3 campaign tooling remains review-first. The new portfolio campaign builder is:

```bash
python3 scripts/build_portfolio_campaigns.py
```

It generates campaign/storyboard candidates for the eight customer-facing Wave 1 products. **DIO CapitalRoom is excluded by code** because it is an internal fundraising and diligence layer.

No generated campaign is publication authority. Copy, product claims, evidence, privacy, fulfilment readiness and release still require operator review.
