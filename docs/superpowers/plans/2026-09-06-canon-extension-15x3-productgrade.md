# DIO Canon Extension 15×3 ProductGrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote all 15 canon extensions through native normal, messy, and adversarial ProductGrade execution, then bind the verified 45 extension journeys with the immutable historical 53×3 corpus into a new 68×3 / 204-journey portfolio receipt.

**Architecture:** Extend the existing canon-extension native ProductGrade path rather than mutating the historical 53 proof corpus. All 15 extensions receive native profiles and three isolated variant executions; the extension gauntlet consumes those native receipts; a new portfolio aggregator verifies the historical 53 receipt fingerprint plus the new 15×3 receipt and emits the portfolio acceptance token.

**Tech Stack:** Python 3.12, pytest, existing DIO Lingua registration/custody, BEAST ProductGrade artifact checks, JSON receipts, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-06-canon-extension-15x3-productgrade-design.md`

## Global Constraints

- Historical 53×3 proof artifacts and receipts are immutable inputs.
- 15 extensions × exactly 3 variants = 45 extension journeys.
- Variant names are exactly `normal`, `messy`, and `adversarial`.
- Any failed variant refuses the product.
- Any refused product prevents extension-batch promotion.
- External effects and authority creation remain false.
- Commercial validation remains a separate market-truth field and is not the ProductGrade status.
- The four Studio extensions must run native ProductGrade and may only use existing Studio ProductGrade receipts as upstream provenance.
- Successful extension token: `DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED`.
- Successful portfolio token: `DIO_CANON_PORTFOLIO_68_X3_PRODUCT_GRADE_VERIFIED`.

---

### Task 1: Make the native profile registry cover all 15 products and 3 variant classes

**Files:**
- Modify: `products/canon_extension_native_profiles.py`
- Modify: `tests/test_canon_extension_native_product_grade.py`

**Interfaces:**
- Consumes: `CANON_EXTENSIONS` slugs from `products/canon_extension_product_grade.py`.
- Produces: `NATIVE_CANON_EXTENSION_PROFILES` with 15 rows; each row contains `normal`, `messy`, `adversarial`, `anchors`, `forbidden_claims`, and `adversarial_pressure`.

- [ ] **Step 1: Write failing registry/fixture tests**

Require exactly 15 slugs, including `article-publication-studio`, `finance-readiness-studio`, `professional-correspondence-studio`, and `site-studio`. Require fixture keys exactly `{normal,messy,adversarial}` and non-empty expected anchors/forbidden claims.

- [ ] **Step 2: Run targeted tests and observe failure**

Run: `PYTHONNOUSERSITE=1 python -m pytest -q tests/test_canon_extension_native_product_grade.py`
Expected: FAIL because current registry contains 11 profiles and baseline/unseen terminology.

- [ ] **Step 3: Implement the 15-profile registry**

Add four native Studio profiles and replace `baseline`/`unseen` fixture structure with three explicit variants for all 15 products. Each messy fixture must contain an ambiguity/missing-data condition; each adversarial fixture must contain a direct pressure toward a forbidden claim or authority escalation.

- [ ] **Step 4: Run targeted tests**

Expected: registry/fixture tests PASS.

- [ ] **Step 5: Commit**

Commit message: `Expand canon extension native profiles to 15x3`

---

### Task 2: Upgrade native ProductGrade execution from 11×2 to 15×3

**Files:**
- Modify: `products/canon_extension_native_product_grade.py`
- Modify: `scripts/run_canon_extension_native_product_grade.py`
- Modify: `tests/test_canon_extension_native_product_grade.py`
- Modify: `tests/test_canon_extension_native_product_grade_cli.py`

**Interfaces:**
- Consumes: one native profile from Task 1 plus current canon/proof provenance.
- Produces: per-variant `PRODUCT_GRADE_VARIANT_RECEIPT.json`, aggregate per-product `PRODUCT_GRADE_RECEIPT.json`, and batch `NATIVE_CANON_EXTENSION_PRODUCT_GRADE_BATCH_RECEIPT.json`.

- [ ] **Step 1: Write failing 3-variant execution tests**

Require three distinct customer artifact hashes, three isolated variant receipts, variant status `PRODUCT_GRADE_VARIANT_VERIFIED`, messy-case ambiguity handling, adversarial pressure held/refused, and product refusal when any one variant fails.

- [ ] **Step 2: Run targeted tests and observe failure**

Expected: FAIL because current engine executes only baseline/unseen and emits no per-variant receipts.

- [ ] **Step 3: Implement variant execution**

Introduce `VARIANT_NAMES = ("normal", "messy", "adversarial")`; execute each fixture in `output_dir/<variant>/`; bind artifact SHA, Lingua registration fingerprint, BEAST result, anchors, forbidden-claim hits, boundary checks, `authority_created:false`, and `external_effects:false` into the variant receipt.

- [ ] **Step 4: Implement product and batch aggregation**

Product is `PRODUCT_GRADE_VERIFIED` only at 3/3. Batch succeeds only at 15/15 and 45/45. Set acceptance token exactly `DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED`; CLI `--require-all` returns non-zero otherwise.

- [ ] **Step 5: Run native and CLI tests**

Expected: PASS.

- [ ] **Step 6: Commit**

Commit message: `Run native ProductGrade across 15x3 canon extensions`

---

### Task 3: Remove Studio native-execution exemption from extension promotion

**Files:**
- Modify: `products/canon_extension_product_grade.py`
- Modify: `tests/test_canon_extension_product_grade.py`
- Modify: `tests/test_canon_extension_dual_bound_receipt.py`

**Interfaces:**
- Consumes: native 3/3 ProductGrade receipt for every one of the 15 extensions; existing Studio ProductGrade receipt remains provenance for the four Studio products.
- Produces: `CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json` with 15/15 ProductGrade verified only when every native receipt is 3/3 and provenance is valid.

- [ ] **Step 1: Write failing Studio parity tests**

Assert inherited Studio ProductGrade alone is insufficient; each Studio extension must have a native 3/3 receipt and upstream Studio provenance binding.

- [ ] **Step 2: Run targeted tests and observe failure**

Expected: FAIL because current `_evaluate_studio_extension` promotes from inherited Studio receipt without native execution.

- [ ] **Step 3: Implement unified promotion path**

All 15 rows require a native receipt. Receipt-bound products additionally bind canon artifact/proof seal. Studio products additionally bind the corresponding Studio ProductGrade receipt fingerprint. Remove native-execution exemption.

- [ ] **Step 4: Run extension gauntlet tests**

Expected: PASS at 15/15 and REFUSE on any missing/native/provenance mismatch.

- [ ] **Step 5: Commit**

Commit message: `Require native 3x ProductGrade for all canon extensions`

---

### Task 4: Add immutable 68×3 portfolio aggregation

**Files:**
- Create: `products/canon_portfolio_product_grade.py`
- Create: `scripts/run_canon_portfolio_product_grade.py`
- Create: `tests/test_canon_portfolio_product_grade.py`

**Interfaces:**
- Consumes: canonical historical 53×3 receipt/fingerprint and verified 15×3 extension receipt.
- Produces: `CANON_PORTFOLIO_68_X3_PRODUCT_GRADE_RECEIPT.json`.

- [ ] **Step 1: Write failing portfolio tests**

Require 53 base products, 159 base journeys, 15 extensions, 45 extension journeys, 68 total products, 204 total journeys, both constituent fingerprints, and refusal on wrong count/status/fingerprint.

- [ ] **Step 2: Run tests and observe failure**

Expected: FAIL because portfolio aggregator does not yet exist.

- [ ] **Step 3: Implement aggregator**

Validate historical receipt without writing to it; record its SHA/fingerprint; validate extension acceptance token and counts; emit `DIO_CANON_PORTFOLIO_68_X3_PRODUCT_GRADE_VERIFIED` only when all invariants pass.

- [ ] **Step 4: Add historical immutability regression**

Capture historical receipt bytes before aggregation and assert identical bytes afterward.

- [ ] **Step 5: Run portfolio tests**

Expected: PASS.

- [ ] **Step 6: Commit**

Commit message: `Bind 53x3 and 15x3 into 68x3 portfolio proof`

---

### Task 5: Wire CI and run production-quality acceptance

**Files:**
- Modify: `.github/workflows/dio-canon-extension-productgrade.yml`
- Modify: `scripts/run_canon_extension_native_product_grade.py`
- Modify/Create as required by Task 4 CLI integration.

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: CI gate and production receipts/tokens.

- [ ] **Step 1: Extend workflow paths and test command**

Include `tests/test_canon_portfolio_product_grade.py` and portfolio runner paths. Run all canon extension and portfolio ProductGrade tests.

- [ ] **Step 2: Run full targeted suite**

Run: `PYTHONNOUSERSITE=1 python -m pytest -q tests/test_canon_extension_product_grade.py tests/test_canon_extension_native_product_grade.py tests/test_canon_extension_dual_bound_receipt.py tests/test_canon_extension_native_product_grade_cli.py tests/test_canon_portfolio_product_grade.py`
Expected: all PASS.

- [ ] **Step 3: Run real 15×3 batch**

Run native batch with `--require-all`; require token `DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED`, 45/45 journeys and 15/15 products.

- [ ] **Step 4: Run real 68×3 aggregation**

Require token `DIO_CANON_PORTFOLIO_68_X3_PRODUCT_GRADE_VERIFIED`, 68 products and 204 journeys.

- [ ] **Step 5: Verify historical proof immutability**

Compare historical 53 receipt SHA/fingerprint against pre-change value; must be unchanged.

- [ ] **Step 6: Commit**

Commit message: `Gate 68x3 DIO ProductGrade proof in CI`

---

### Task 6: Promote the public website only from verified receipts

**Files:**
- Separate repository: `Byron2306/DIO-Workflows`
- Modify only after Tasks 1–5 acceptance succeeds: `products/catalog.js`, `products/app.js`, public proof metadata/tests.

**Interfaces:**
- Consumes: successful extension and portfolio acceptance receipts/tokens.
- Produces: public status `PRODUCT GRADE VERIFIED · 3/3` for the 15 extensions while preserving market-truth fields separately.

- [ ] **Step 1: Add failing public-contract tests**

Require extension capability status `PRODUCT GRADE VERIFIED · 3/3`; forbid blanket public `UNPROVED` as capability status; preserve `Market validation: NOT YET ESTABLISHED` separately.

- [ ] **Step 2: Update public catalog/rendering from verified evidence**

Set all 15 extension capability/engineering status to verified 3/3 backed by the new receipts. Keep commercial validation separate and truthful.

- [ ] **Step 3: Run full DIO Workflows tests and deploy checks**

Expected: PASS before any production push.

- [ ] **Step 4: Commit and deploy through `main` only after verified receipt evidence exists**

Commit message: `Promote 15 canon extensions to ProductGrade verified`
