# DIO Canon Extension 15×3 ProductGrade Gauntlet Design

Date: 2026-09-06
Branch: `agent/dio-canon-extension-productgrade-gauntlet`

## Purpose

Promote all fifteen DIO canon extensions through a native ProductGrade gauntlet equivalent in proof shape to the historical 53-product corpus, without rewriting or mutating the historical 53×3 evidence.

The result must preserve two distinct truths:

- the historical base-canon corpus remains 53 products × 3 controlled variants = 159 journeys;
- the canon-extension corpus becomes 15 products × 3 controlled variants = 45 journeys.

A new portfolio-level receipt may then bind the two immutable evidence families as 68 products × 3 controlled variants = 204 controlled journeys.

## Non-goals

This programme does not prove customer demand, willingness to pay, verified payment, legal approval, publication authority, investment interest, funding approval, market success, or autonomous external authority.

It must not backfill the fifteen extensions into the historical 53×3 receipt or alter historical receipt semantics.

## Canon extension set

The native gauntlet covers all fifteen extensions:

1. Article Publication
2. Article Publication Studio
3. Contract Desk
4. Corporate Readiness
5. EntrepreneurProof
6. Finance Readiness
7. Finance Readiness Studio
8. FundingFinder
9. InvestorProof
10. Launch Studio
11. POPIA Readiness
12. Professional Correspondence
13. Professional Correspondence Studio
14. Report & Pitch Studio
15. Site Studio

The four Studio extensions currently evaluated through inherited `studio_product_grade` evidence must receive their own native buyer-artifact execution. Their existing Studio ProductGrade receipts remain upstream provenance and must be bound into the new native receipts rather than substituted for native execution.

## Required execution shape

Each of the fifteen extensions must execute three independent controlled variants:

- `normal`: ordinary buyer packet with complete, valid context;
- `messy`: incomplete, ambiguous, noisy, conflicting, or partially missing context that the product must surface rather than silently repair;
- `adversarial`: prompt, claim, authority, provenance, or boundary pressure intended to make the product fabricate, overclaim, create authority, or bypass release constraints.

Each variant must produce its own inspectable buyer-facing artifact and its own execution receipt.

No product is ProductGrade verified unless all three variants pass.

## Variant requirements

Every variant must verify, at minimum:

1. native product execution occurred through the product's declared machinery;
2. a buyer-facing artifact was generated for that variant;
3. the artifact is separate from the frozen canon artifact;
4. the artifact SHA-256 is recorded and bound to the variant receipt;
5. Lingua semantic custody is preserved from source rows to persisted semantic object and registration receipt;
6. BEAST mechanical artifact checks pass;
7. expected semantic anchors for the active fixture are present;
8. prohibited claims are absent;
9. the human/authority boundary is present where the product requires it;
10. external effects remain false;
11. authority creation remains false;
12. variant-specific mutation is demonstrated so the three outputs cannot be aliases of one fixture;
13. unexpected execution errors fail closed and remain inspectable in the receipt.

The adversarial variant must additionally demonstrate that at least one explicit forbidden or authority-escalating instruction is refused, held, or converted into a review-required boundary rather than appearing as an asserted outcome.

## Canon and provenance binding

### Receipt-bound extensions

For receipt-bound extensions, every ProductGrade result must bind:

- canon identity and slug;
- current canon artifact path and SHA-256;
- current canon proof seal path and SHA-256;
- preserved generation receipt identity;
- generated customer artifact path and SHA-256 for each variant;
- Lingua registration receipt fingerprint;
- BEAST result;
- variant identity;
- variant receipt fingerprint.

The live canon artifact and its proof seal are evidence inputs. They are not themselves the buyer-artifact output of the new ProductGrade run.

### Studio extensions

For Article Publication Studio, Finance Readiness Studio, Professional Correspondence Studio, and Site Studio, the new native ProductGrade receipt must bind the corresponding existing Studio ProductGrade receipt as upstream provenance, then independently execute normal, messy, and adversarial buyer cases through a native profile for that Studio extension.

A Studio source receipt that is absent, refused, or hash-inconsistent causes fail-closed ProductGrade refusal for that extension.

## Native profile registry

`products/canon_extension_native_profiles.py` becomes the source of native execution profiles for all fifteen extensions.

Every profile must define:

- `slug`
- `name`
- `family`
- `mode`
- `buyer`
- forbidden claims
- three fixtures: `normal`, `messy`, `adversarial`
- expected semantic anchor(s) per fixture
- adversarial pressure and the expected held/refused boundary

Legacy `baseline` / `unseen` terminology is retired for this programme because it does not express parity with the historical normal/messy/adversarial gauntlet.

## Native execution engine

`products/canon_extension_native_product_grade.py` becomes a 15-product, 3-variant engine.

The engine must:

1. iterate all fifteen native profiles;
2. execute exactly three variants per product;
3. write each variant into an isolated workspace;
4. produce a `PRODUCT_GRADE_VARIANT_RECEIPT.json` per variant;
5. produce one aggregate `PRODUCT_GRADE_RECEIPT.json` per product;
6. declare `PRODUCT_GRADE_VERIFIED` only if all three variants pass;
7. produce one batch receipt covering all fifteen products.

Required batch acceptance token:

`DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED`

Required batch truth on success:

- `extension_count: 15`
- `variants_per_extension: 3`
- `controlled_journey_count: 45`
- `verified_journey_count: 45`
- `refused_journey_count: 0`
- `product_grade_verified_count: 15`
- `product_grade_refuse_count: 0`
- `all_product_grade_verified: true`
- `external_effects: false`
- `authority_created: false`
- `commercial_validation: UNPROVED`

`commercial_validation: UNPROVED` remains a market-truth field. It must no longer be used as the primary public capability status once ProductGrade is verified.

## Extension gauntlet aggregation

`products/canon_extension_product_grade.py` remains the canon-extension promotion layer, but it must no longer treat the four Studio extensions as exempt from native ProductGrade execution.

All fifteen rows must require a native ProductGrade receipt with three passing variants.

Required extension-gauntlet acceptance token:

`DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED`

The aggregate extension receipt must report per product:

- proof status;
- ProductGrade status;
- 3/3 variant status;
- variant receipt fingerprints;
- canon/provenance bindings;
- customer-artifact hashes;
- blockers;
- market-truth fields.

## Portfolio 68×3 receipt

Add a new immutable portfolio aggregation receipt rather than modifying the historical 53×3 receipt.

The portfolio aggregator must ingest:

1. the preserved historical 53×3 receipt or its canonical fingerprint;
2. the new verified 15×3 extension receipt.

It must verify their identities and expected counts before promotion.

Required portfolio acceptance token:

`DIO_CANON_PORTFOLIO_68_X3_PRODUCT_GRADE_VERIFIED`

Required portfolio truth on success:

- `canon_product_count: 68`
- `base_canon_product_count: 53`
- `canon_extension_count: 15`
- `variants_per_product: 3`
- `base_canon_journey_count: 159`
- `canon_extension_journey_count: 45`
- `controlled_journey_count: 204`
- `product_grade_verified_count: 68`
- `all_product_grade_verified: true`
- `historical_53_receipt_mutated: false`
- `external_effects: false`
- `authority_created: false`

The receipt must preserve fingerprints of both constituent evidence families so the 204 claim can be reconstructed without pretending all 204 journeys were generated in one historical run.

## Public website promotion semantics

Only after the 15×3 extension receipt verifies all fifteen products should the DIO Workflows site promote these extension products from candidate language.

Primary public capability status for each of the fifteen:

`PRODUCT GRADE VERIFIED · 3/3`

Secondary truth fields may state:

- `Canon level: VERIFIED`
- `Controlled execution: 3/3 VERIFIED`
- `Market exposure: OBSERVED` only where externally evidenced by campaign/traffic telemetry;
- `Market validation: NOT YET ESTABLISHED` unless customer evidence supports a stronger state;
- `Verified payment: NOT YET ESTABLISHED` unless payment evidence exists.

The word `UNPROVED` must not be used as a blanket public status for a product whose capability has passed ProductGrade. It may remain in machine receipts for specific commercial claims.

The site must continue to distinguish engineering/capability proof from market proof.

## Tests

The change is test-driven.

Minimum required failing tests before implementation:

1. native profile registry covers exactly 15 extensions;
2. every profile defines exactly normal, messy, and adversarial fixtures;
3. all four Studio extensions have native profiles;
4. one ProductGrade case generates and binds three distinct buyer artifacts;
5. messy fixture exposes ambiguity/missing-data handling instead of invention;
6. adversarial fixture proves prohibited-claim or authority pressure is held/refused;
7. any failed variant causes product-level refusal;
8. any missing canon/provenance binding causes refusal;
9. batch requires 45/45 journeys and 15/15 products;
10. extension aggregator refuses inherited Studio-only proof without native 3/3 receipt;
11. portfolio aggregator refuses wrong 53 or 15 constituent counts;
12. portfolio aggregator verifies 68 products and 204 journeys only when both evidence families verify;
13. historical 53 receipt bytes/fingerprint remain unchanged;
14. CLI returns non-zero when `--require-all` is requested and any product is refused;
15. CI workflow runs the full extension and portfolio proof suites.

Existing tests that assert exactly eleven native profiles must be rewritten to assert exactly fifteen.

## CI

`.github/workflows/dio-canon-extension-productgrade.yml` must run:

- native-profile tests;
- native 15×3 ProductGrade tests;
- dual-bound receipt tests;
- extension aggregate tests;
- portfolio 68×3 aggregate tests;
- CLI acceptance tests.

A production-quality acceptance run must print both final tokens when successful:

`DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED`

`DIO_CANON_PORTFOLIO_68_X3_PRODUCT_GRADE_VERIFIED`

## Failure semantics

The system remains fail closed.

A single failed variant prevents that product from being ProductGrade verified.

A single refused product prevents the 15×3 extension acceptance token.

A missing or inconsistent historical 53 receipt prevents the 68×3 portfolio acceptance token.

No failure may be converted into a warning merely to satisfy the portfolio count.

## Historical evidence preservation

The canonical 53×3 proof artifacts and receipts are immutable inputs.

Implementation must include a regression assertion that their expected fingerprint or byte hash does not change during the new programme.

The new portfolio receipt references the historical evidence. It does not edit it.

## Exit criteria

This programme is complete only when all of the following are simultaneously true:

1. fifteen native profiles exist;
2. forty-five isolated controlled journeys execute;
3. all 45 variant receipts pass;
4. all 15 aggregate product receipts report `PRODUCT_GRADE_VERIFIED` and 3/3;
5. all canon/provenance/customer-artifact bindings are valid;
6. BEAST and Lingua checks pass for all 45 journeys;
7. authority and external effects remain held for all 45 journeys;
8. extension acceptance token is `DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED`;
9. portfolio acceptance token is `DIO_CANON_PORTFOLIO_68_X3_PRODUCT_GRADE_VERIFIED`;
10. the portfolio receipt reports 68 products and 204 controlled journeys;
11. the historical 53×3 evidence remains unchanged;
12. full targeted test suite and CI pass;
13. only then may the public site promote the fifteen extensions to `PRODUCT GRADE VERIFIED · 3/3`.
