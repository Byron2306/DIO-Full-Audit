# DIO Canon Extension 15×3 ProductGrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote all fifteen DIO canon extensions through native normal, messy, and adversarial ProductGrade execution, then bind their 45 verified journeys to the immutable historical 53×3 corpus as a new 68-product / 204-journey portfolio receipt.

**Architecture:** Keep the historical 53×3 evidence immutable and treat it as an external evidence family identified by a pinned repository commit and Git blob SHA. Upgrade the existing canon-extension native runner from 11 baseline/unseen profiles to 15 normal/messy/adversarial profiles, require native 3/3 execution for all four Studio extensions as well as the eleven receipt-bound extensions, and aggregate the verified extension receipt with the historical anchor in a new portfolio verifier. Test fixtures may seed deterministic temporary canon/provenance state, but production acceptance must consume real generated artifacts and real proof seals and must fail closed when those inputs are absent.

**Tech Stack:** Python 3.12, pytest, JSON receipts, SHA-256 evidence binding, DIO Lingua semantic registration, BEAST artifact checks, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-06-canon-extension-15x3-productgrade-design.md`

## Global Constraints

- Historical base-canon evidence remains 53 products × 3 controlled variants = 159 journeys and must not be edited or backfilled.
- Canon-extension evidence must become 15 products × 3 controlled variants = 45 journeys.
- Portfolio aggregation may claim 68 products × 3 = 204 controlled journeys only by binding the immutable 53×3 evidence family to the verified 15×3 evidence family.
- Every extension must execute exactly `normal`, `messy`, and `adversarial` variants.
- Every variant must produce a separate buyer-facing artifact and a separate inspectable receipt.
- Lingua semantic custody and BEAST mechanical checks must pass for every variant.
- External effects and authority creation must remain `false` for all 45 journeys.
- A single failed variant refuses its product; a single refused product prevents extension and portfolio promotion.
- `commercial_validation: "UNPROVED"` remains a machine-level market-truth field and must not be conflated with ProductGrade capability status.
- The four Studio extensions must bind their existing Studio ProductGrade receipts as upstream provenance and still execute their own native 3/3 buyer cases.
- Unit and CI fixtures may create deterministic temporary evidence inputs. Production acceptance must not synthesize fake proof state to obtain a pass.
- Required extension token: `DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED`.
- Required portfolio token: `DIO_CANON_PORTFOLIO_68_X3_PRODUCT_GRADE_VERIFIED`.

---

## File Structure

### New files

- `evidence/historical/PROFESSIONAL_EVIDENCE_53_X3_ANCHOR.json` — immutable local descriptor for the historical public 53×3 evidence family, pinned to the exact DIO-Workflows source commit and Git blob.
- `products/canon_portfolio_product_grade.py` — validates the historical anchor and verified extension receipt, then writes the 68×3 portfolio receipt.
- `scripts/run_canon_portfolio_product_grade.py` — CLI for portfolio aggregation and `--require-all` failure semantics.
- `tests/test_canon_portfolio_68_product_grade.py` — historical-anchor and 68×3 aggregation tests.

### Modified files

- `products/canon_extension_native_profiles.py` — native profile registry for all 15 extensions with normal/messy/adversarial fixtures.
- `products/canon_extension_native_product_grade.py` — three-variant native executor, per-variant receipts, Studio provenance binding, 15-product batch receipt.
- `products/canon_extension_product_grade.py` — removes inherited-Studio exemption and requires native 3/3 ProductGrade for every extension.
- `scripts/run_canon_extension_native_product_grade.py` — 15×3 CLI semantics and new acceptance token.
- `scripts/run_canon_extension_product_grade.py` — orchestrates upstream Studio proof, native 15×3 proof, extension aggregation, and optional portfolio aggregation without manufacturing missing production state.
- `tests/test_canon_extension_native_product_grade.py` — 15-profile, 3-variant, fail-closed native execution tests.
- `tests/test_canon_extension_product_grade.py` — all-15 native promotion requirements.
- `tests/test_canon_extension_dual_bound_receipt.py` — updates native schema and provenance assertions.
- `tests/test_canon_extension_native_product_grade_cli.py` — CLI success/refusal behavior for 15×3.
- `.github/workflows/dio-canon-extension-productgrade.yml` — full target suite and acceptance-token verification when production state is explicitly available.

---

### Task 1: Freeze the historical 53×3 evidence identity

**Files:**
- Create: `evidence/historical/PROFESSIONAL_EVIDENCE_53_X3_ANCHOR.json`
- Create: `tests/test_canon_portfolio_68_product_grade.py`
- Create: `products/canon_portfolio_product_grade.py`

**Interfaces:**
- Consumes: JSON anchor at `evidence/historical/PROFESSIONAL_EVIDENCE_53_X3_ANCHOR.json`.
- Produces: `load_historical_53_anchor(path: Path) -> dict[str, Any]` and `validate_historical_53_anchor(anchor: dict[str, Any]) -> list[str]`.

- [ ] **Step 1: Write the failing anchor validation tests**

Add tests that require this exact immutable identity:

```python
EXPECTED_SOURCE = {
    "source_repository": "Byron2306/DIO-Workflows",
    "source_commit": "3119e290efd62cdeccd3f4f5938cc5be85014464",
    "source_path": "products/proof/receipts/PROFESSIONAL_EVIDENCE_53_X3_RECEIPT.json",
    "source_git_blob_sha": "7ffeb400a4ec0ffd51d0a10c3035d3303fd24c4e",
    "acceptance_token": "DIO_PROFESSIONAL_EVIDENCE_53_X3_VERIFIED",
    "schema": "dio.professional_evidence.multitier_53_receipt.v1",
    "canonical_incarnation_count": 53,
    "variant_count": 3,
    "journey_count": 159,
    "verified_journey_count": 159,
    "refused_journey_count": 0,
    "authority_created": False,
    "external_effects": False,
}


def test_historical_anchor_matches_frozen_53x3_identity() -> None:
    anchor = load_historical_53_anchor(ROOT / "evidence/historical/PROFESSIONAL_EVIDENCE_53_X3_ANCHOR.json")
    for key, value in EXPECTED_SOURCE.items():
        assert anchor[key] == value
    assert validate_historical_53_anchor(anchor) == []


def test_historical_anchor_refuses_count_or_blob_drift() -> None:
    anchor = dict(EXPECTED_SOURCE)
    anchor["source_git_blob_sha"] = "0" * 40
    anchor["journey_count"] = 158
    blockers = validate_historical_53_anchor(anchor)
    assert "historical_53_blob_identity_mismatch" in blockers
    assert "historical_53_journey_count_mismatch" in blockers
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_canon_portfolio_68_product_grade.py
```

Expected: collection/import failure because `products.canon_portfolio_product_grade` and the anchor file do not yet exist.

- [ ] **Step 3: Add the immutable anchor JSON**

Create:

```json
{
  "schema": "dio.historical_evidence_anchor.v1",
  "source_repository": "Byron2306/DIO-Workflows",
  "source_commit": "3119e290efd62cdeccd3f4f5938cc5be85014464",
  "source_path": "products/proof/receipts/PROFESSIONAL_EVIDENCE_53_X3_RECEIPT.json",
  "source_git_blob_sha": "7ffeb400a4ec0ffd51d0a10c3035d3303fd24c4e",
  "acceptance_token": "DIO_PROFESSIONAL_EVIDENCE_53_X3_VERIFIED",
  "receipt_schema": "dio.professional_evidence.multitier_53_receipt.v1",
  "canonical_incarnation_count": 53,
  "variant_count": 3,
  "variants": ["normal", "messy", "adversarial"],
  "journey_count": 159,
  "verified_journey_count": 159,
  "refused_journey_count": 0,
  "authority_created": false,
  "external_effects": false,
  "commercial_validation": "UNPROVED"
}
```

In the test and validator, use `receipt_schema` for the historical receipt's schema and reserve `schema` for the anchor's own schema.

- [ ] **Step 4: Implement the validator minimally**

In `products/canon_portfolio_product_grade.py`, define constants and fail-closed validation:

```python
HISTORICAL_53_ANCHOR_SCHEMA = "dio.historical_evidence_anchor.v1"
HISTORICAL_53_ACCEPTANCE_TOKEN = "DIO_PROFESSIONAL_EVIDENCE_53_X3_VERIFIED"
HISTORICAL_53_SOURCE_COMMIT = "3119e290efd62cdeccd3f4f5938cc5be85014464"
HISTORICAL_53_SOURCE_BLOB = "7ffeb400a4ec0ffd51d0a10c3035d3303fd24c4e"


def load_historical_53_anchor(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("historical 53 anchor must be a JSON object")
    return value


def validate_historical_53_anchor(anchor: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if anchor.get("schema") != HISTORICAL_53_ANCHOR_SCHEMA:
        blockers.append("historical_53_anchor_schema_invalid")
    if anchor.get("source_commit") != HISTORICAL_53_SOURCE_COMMIT:
        blockers.append("historical_53_source_commit_mismatch")
    if anchor.get("source_git_blob_sha") != HISTORICAL_53_SOURCE_BLOB:
        blockers.append("historical_53_blob_identity_mismatch")
    if anchor.get("acceptance_token") != HISTORICAL_53_ACCEPTANCE_TOKEN:
        blockers.append("historical_53_acceptance_token_invalid")
    if anchor.get("canonical_incarnation_count") != 53:
        blockers.append("historical_53_product_count_mismatch")
    if anchor.get("variant_count") != 3 or anchor.get("variants") != ["normal", "messy", "adversarial"]:
        blockers.append("historical_53_variant_contract_mismatch")
    if anchor.get("journey_count") != 159 or anchor.get("verified_journey_count") != 159:
        blockers.append("historical_53_journey_count_mismatch")
    if anchor.get("refused_journey_count") != 0:
        blockers.append("historical_53_refused_journeys_present")
    if anchor.get("authority_created") is not False or anchor.get("external_effects") is not False:
        blockers.append("historical_53_authority_boundary_drift")
    return sorted(set(blockers))
```

- [ ] **Step 5: Run the anchor tests and verify GREEN**

Run the same pytest command. Expected: anchor tests pass.

- [ ] **Step 6: Commit**

```bash
git add evidence/historical/PROFESSIONAL_EVIDENCE_53_X3_ANCHOR.json products/canon_portfolio_product_grade.py tests/test_canon_portfolio_68_product_grade.py
git commit -m "Freeze historical 53x3 evidence anchor"
```

---

### Task 2: Upgrade the native profile registry to all 15 products × 3 variants

**Files:**
- Modify: `products/canon_extension_native_profiles.py`
- Modify: `tests/test_canon_extension_native_product_grade.py`

**Interfaces:**
- Consumes: 15 slugs from `products.canon_extension_product_grade.CANON_EXTENSIONS`.
- Produces: `NATIVE_CANON_EXTENSION_PROFILES` with one profile per extension and `native_profile(slug: str) -> dict[str, Any]`.

- [ ] **Step 1: Replace the eleven-profile contract test with a fifteen-profile contract test**

Use the exact slug set:

```python
EXPECTED_SLUGS = {
    "article-publication",
    "article-publication-studio",
    "contract-desk",
    "corporate-readiness",
    "entrepreneurproof",
    "finance-readiness",
    "finance-readiness-studio",
    "fundingfinder",
    "investorproof",
    "launch-studio",
    "popia-readiness",
    "professional-correspondence",
    "professional-correspondence-studio",
    "report-pitch-studio",
    "site-studio",
}


def test_native_profile_registry_covers_exactly_all_fifteen_extensions() -> None:
    assert {row["slug"] for row in NATIVE_CANON_EXTENSION_PROFILES} == EXPECTED_SLUGS
    assert len(NATIVE_CANON_EXTENSION_PROFILES) == 15
    for row in NATIVE_CANON_EXTENSION_PROFILES:
        assert set(row["fixtures"]) == {"normal", "messy", "adversarial"}
        assert set(row["anchors"]) == {"normal", "messy", "adversarial"}
        assert row["forbidden_claims"]
        assert row["adversarial_pressure"]
        assert row["adversarial_expected_boundary"]
```

Add a dedicated test that the four Studio slugs are present natively.

- [ ] **Step 2: Add fixture distinctness tests**

For every profile, build semantic rows for all three fixtures and assert their serialized semantic content and expected anchors differ. Also assert the adversarial fixture contains `adversarial_pressure` input and the expected boundary text can be rendered without asserting a forbidden claim.

- [ ] **Step 3: Run the profile tests and verify RED**

Run:

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_canon_extension_native_product_grade.py -k "profile or fixture"
```

Expected: failures because only 11 profiles exist and they still use `baseline` / `unseen`.

- [ ] **Step 4: Convert the existing 11 profiles to the new profile shape**

Each profile must use:

```python
{
    "slug": "...",
    "name": "...",
    "family": "...",
    "mode": "...",
    "buyer": "...",
    "forbidden_claims": [...],
    "anchors": {
        "normal": "...",
        "messy": "...",
        "adversarial": "...",
    },
    "adversarial_pressure": "...",
    "adversarial_expected_boundary": "...",
    "fixtures": {
        "normal": {...},
        "messy": {...},
        "adversarial": {...},
    },
}
```

The messy fixture must include an explicit ambiguity or missing-evidence marker that semantic rendering preserves. The adversarial fixture must include an explicit request to overclaim, fabricate, create authority, or bypass release constraints.

- [ ] **Step 5: Add native profiles for all four Studio extensions**

Use distinct `mode` values so the renderer can identify them without aliasing their non-Studio sibling:

- `article_studio`
- `finance_studio`
- `correspondence_studio`
- `site_studio`

Each must have independent buyer context, normal/messy/adversarial anchors, forbidden claims, and adversarial boundary text.

- [ ] **Step 6: Update `build_semantic_rows` expectations in tests**

The renderer must surface messy facts as held/missing/ambiguous rather than silently inventing replacements. The adversarial pressure must be represented as a held/refused instruction plus the human boundary, not as an asserted result.

- [ ] **Step 7: Run the profile tests and verify GREEN**

Expected: exact 15 coverage and all fixture-shape tests pass.

- [ ] **Step 8: Commit**

```bash
git add products/canon_extension_native_profiles.py tests/test_canon_extension_native_product_grade.py
git commit -m "Expand canon extension native profiles to 15x3"
```

---

### Task 3: Refactor native execution into three isolated variant receipts

**Files:**
- Modify: `products/canon_extension_native_product_grade.py`
- Modify: `tests/test_canon_extension_native_product_grade.py`
- Modify: `tests/test_canon_extension_dual_bound_receipt.py`

**Interfaces:**
- Produces: `run_native_product_grade_variant(...) -> dict[str, Any]` and `run_native_product_grade_case(...) -> dict[str, Any]`.
- Variant receipt schema: `dio.product_grade.canon_extension_native_variant.v1`.
- Aggregate product receipt schema: `dio.product_grade.canon_extension_native.v3`.

- [ ] **Step 1: Write failing tests for one product creating three variant artifacts and receipts**

For `article-publication`, seed canon state in a temporary repo and run the product case with a passing BEAST stub. Assert:

```python
assert receipt["schema"] == "dio.product_grade.canon_extension_native.v3"
assert receipt["status"] == "PRODUCT_GRADE_VERIFIED"
assert receipt["variant_count"] == 3
assert receipt["verified_variant_count"] == 3
assert set(receipt["variants"]) == {"normal", "messy", "adversarial"}
assert len({row["customer_artifact_sha256"] for row in receipt["variants"].values()}) == 3
for variant, row in receipt["variants"].items():
    assert row["schema"] == "dio.product_grade.canon_extension_native_variant.v1"
    assert row["variant"] == variant
    assert row["passed"] is True
    assert row["lingua_semantic_custody"] is True
    assert row["beast_mechanical_pass"] is True
    assert row["authority_created"] is False
    assert row["external_effects"] is False
```

Assert each workspace contains `PRODUCT_GRADE_VARIANT_RECEIPT.json`.

- [ ] **Step 2: Write failing messy and adversarial behavior tests**

Messy test: inspect rendered text and receipt checks to ensure the expected missing/ambiguous marker remains visible and no invented replacement appears.

Adversarial test: ensure the pressure string does not become an asserted forbidden outcome and `adversarial_boundary_held` is true.

- [ ] **Step 3: Write a failing one-variant-failure test**

Inject a BEAST checker that fails only for the `messy` workspace. Assert the product aggregate is `PRODUCT_GRADE_REFUSE`, `verified_variant_count == 2`, and `critical_blockers` includes `variant_messy_refused`.

- [ ] **Step 4: Run the targeted native tests and verify RED**

Run:

```bash
PYTHONNOUSERSITE=1 python -m pytest -q \
  tests/test_canon_extension_native_product_grade.py \
  tests/test_canon_extension_dual_bound_receipt.py
```

Expected: failures because the engine still executes baseline + unseen and emits a single product receipt without variant receipts.

- [ ] **Step 5: Implement `run_native_product_grade_variant`**

Use one isolated directory per variant:

```text
state/product_grade/canon_extensions/<slug>/variants/normal/
state/product_grade/canon_extensions/<slug>/variants/messy/
state/product_grade/canon_extensions/<slug>/variants/adversarial/
```

The function must call the existing `_execute_fixture`, compute semantic/BEAST/forbidden/boundary checks, write `PRODUCT_GRADE_VARIANT_RECEIPT.json`, and return both the receipt and generated artifact metadata.

- [ ] **Step 6: Refactor `run_native_product_grade_case` to aggregate all three variants**

The product receipt must include:

```python
{
    "schema": "dio.product_grade.canon_extension_native.v3",
    "slug": slug,
    "status": "PRODUCT_GRADE_VERIFIED" or "PRODUCT_GRADE_REFUSE",
    "variant_count": 3,
    "verified_variant_count": verified_count,
    "refused_variant_count": 3 - verified_count,
    "variants": {"normal": ..., "messy": ..., "adversarial": ...},
    "canon_artifact": ...,
    "canon_artifact_sha256": ...,
    "canon_proof_receipt": ...,
    "canon_proof_receipt_sha256": ...,
    "authority_created": False,
    "external_effects": False,
    "commercial_validation": "UNPROVED",
}
```

No old `unseen_input_generalisation` field is used as the primary promotion gate; 3/3 named variants replace it. Keep backwards-compatible informational fields only if another test requires them, never as a substitute for variant evidence.

- [ ] **Step 7: Run targeted tests and verify GREEN**

Expected: three isolated artifacts, three per-variant receipts, fail-closed aggregate behavior.

- [ ] **Step 8: Commit**

```bash
git add products/canon_extension_native_product_grade.py tests/test_canon_extension_native_product_grade.py tests/test_canon_extension_dual_bound_receipt.py
git commit -m "Run canon extensions through three native ProductGrade variants"
```

---

### Task 4: Bind upstream Studio ProductGrade provenance without exempting Studio products from native execution

**Files:**
- Modify: `products/canon_extension_native_product_grade.py`
- Modify: `products/canon_extension_product_grade.py`
- Modify: `tests/test_canon_extension_native_product_grade.py`
- Modify: `tests/test_canon_extension_product_grade.py`

**Interfaces:**
- Consumes: aggregate Studio receipt from `products.product_grade_gauntlet.run_product_grade_gauntlet`.
- Adds optional argument: `studio_product_grade_receipt: dict[str, Any] | None` to native product/batch functions.
- Produces per-Studio binding fields `source_studio_id`, `source_studio_receipt_fingerprint`, and `source_studio_primary_artifact_sha256`.

- [ ] **Step 1: Write failing Studio provenance tests**

For all four Studio extension slugs, pass a valid upstream Studio receipt and assert native 3/3 can verify. Then omit or refuse the upstream row and assert ProductGrade refusal with `source_studio_product_grade_missing` or `source_studio_product_grade_not_verified`.

- [ ] **Step 2: Write a failing inherited-only exemption test**

Call `run_canon_extension_product_grade_gauntlet` with a verified upstream Studio receipt but no native receipt for `site-studio`. Assert `site-studio` remains `PRODUCT_GRADE_REFUSE` and contains `native_product_grade_not_run`.

- [ ] **Step 3: Run targeted tests and verify RED**

Expected: current `_evaluate_studio_extension` still grants ProductGrade from inherited Studio proof.

- [ ] **Step 4: Add explicit Studio slug-to-ID mapping**

Use:

```python
STUDIO_PROVENANCE = {
    "article-publication-studio": "article_publication_studio",
    "finance-readiness-studio": "finance_readiness_studio",
    "professional-correspondence-studio": "professional_correspondence_studio",
    "site-studio": "site_studio",
}
```

Before executing a Studio extension, validate the upstream row exists, has `status == PRODUCT_GRADE_VERIFIED`, binds a primary artifact hash, and has no inflated commercial fields.

- [ ] **Step 5: Remove the inherited-Studio ProductGrade exemption**

In `products/canon_extension_product_grade.py`, every one of the 15 extensions must discover or receive a native receipt and run native receipt checks. The four Studio products may additionally require their upstream Studio provenance fields, but they may never become ProductGrade verified from `_evaluate_studio_extension` alone.

- [ ] **Step 6: Run targeted tests and verify GREEN**

Expected: valid upstream + native 3/3 passes; inherited-only fails.

- [ ] **Step 7: Commit**

```bash
git add products/canon_extension_native_product_grade.py products/canon_extension_product_grade.py tests/test_canon_extension_native_product_grade.py tests/test_canon_extension_product_grade.py
git commit -m "Require native 3x3 proof for Studio canon extensions"
```

---

### Task 5: Promote the extension batch only at 45/45 journeys and 15/15 products

**Files:**
- Modify: `products/canon_extension_native_product_grade.py`
- Modify: `products/canon_extension_product_grade.py`
- Modify: `tests/test_canon_extension_native_product_grade.py`
- Modify: `tests/test_canon_extension_product_grade.py`

**Interfaces:**
- Produces extension acceptance token `DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED`.
- Native batch and promotion-layer aggregate both expose explicit journey/product counts.

- [ ] **Step 1: Write failing aggregate-count tests**

A fully passing seeded test must assert:

```python
assert receipt["extension_count"] == 15
assert receipt["variants_per_extension"] == 3
assert receipt["controlled_journey_count"] == 45
assert receipt["verified_journey_count"] == 45
assert receipt["refused_journey_count"] == 0
assert receipt["product_grade_verified_count"] == 15
assert receipt["product_grade_refuse_count"] == 0
assert receipt["all_product_grade_verified"] is True
assert receipt["acceptance_token"] == "DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED"
```

Add a refusal test where one variant fails and verify the token is not emitted.

- [ ] **Step 2: Run aggregate tests and verify RED**

Expected: old 11-product native token and old extension aggregate token do not satisfy the contract.

- [ ] **Step 3: Replace old batch token constants and count model**

Define exactly:

```python
EXTENSION_15_X3_VERIFIED_TOKEN = "DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED"
EXTENSION_15_X3_BASELINE_TOKEN = "DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_BASELINE_MEASURED"
```

Native batch and extension promotion aggregate must calculate 45 journey states from per-product variant receipts rather than hard-coding 45.

- [ ] **Step 4: Run aggregate tests and verify GREEN**

Expected: 45/45 is required for success.

- [ ] **Step 5: Commit**

```bash
git add products/canon_extension_native_product_grade.py products/canon_extension_product_grade.py tests/test_canon_extension_native_product_grade.py tests/test_canon_extension_product_grade.py
git commit -m "Gate canon extension promotion on 45 of 45 journeys"
```

---

### Task 6: Add the immutable 68×3 portfolio aggregator

**Files:**
- Modify: `products/canon_portfolio_product_grade.py`
- Modify: `tests/test_canon_portfolio_68_product_grade.py`

**Interfaces:**
- Consumes: validated historical anchor and verified extension 15×3 receipt.
- Produces: `run_canon_portfolio_product_grade(*, historical_anchor: dict[str, Any], extension_receipt: dict[str, Any], output_dir: Path) -> dict[str, Any]`.
- Writes: `CANON_PORTFOLIO_68_X3_PRODUCT_GRADE_RECEIPT.json`.

- [ ] **Step 1: Write failing success and refusal tests**

Success fixture must report:

```python
assert receipt["acceptance_token"] == "DIO_CANON_PORTFOLIO_68_X3_PRODUCT_GRADE_VERIFIED"
assert receipt["canon_product_count"] == 68
assert receipt["base_canon_product_count"] == 53
assert receipt["canon_extension_count"] == 15
assert receipt["variants_per_product"] == 3
assert receipt["base_canon_journey_count"] == 159
assert receipt["canon_extension_journey_count"] == 45
assert receipt["controlled_journey_count"] == 204
assert receipt["product_grade_verified_count"] == 68
assert receipt["all_product_grade_verified"] is True
assert receipt["historical_53_receipt_mutated"] is False
assert receipt["authority_created"] is False
assert receipt["external_effects"] is False
```

Refusal tests must cover wrong historical count, wrong historical blob, extension count 14, verified journey count 44, refused product, and wrong extension token.

- [ ] **Step 2: Run tests and verify RED**

Expected: aggregator function does not yet exist.

- [ ] **Step 3: Implement fail-closed aggregation**

Validate the historical anchor first. Validate extension receipt fields exactly:

```python
extension_receipt["acceptance_token"] == EXTENSION_15_X3_VERIFIED_TOKEN
extension_receipt["extension_count"] == 15
extension_receipt["variants_per_extension"] == 3
extension_receipt["controlled_journey_count"] == 45
extension_receipt["verified_journey_count"] == 45
extension_receipt["refused_journey_count"] == 0
extension_receipt["product_grade_verified_count"] == 15
extension_receipt["all_product_grade_verified"] is True
extension_receipt["authority_created"] is False
extension_receipt["external_effects"] is False
```

Compute deterministic fingerprints of both constituent evidence descriptors and include them in the new receipt.

- [ ] **Step 4: Write the portfolio receipt**

Use schema `dio.product_grade.canon_portfolio_68_x3.v1` and baseline token `DIO_CANON_PORTFOLIO_68_X3_PRODUCT_GRADE_BASELINE_MEASURED` when blocked.

- [ ] **Step 5: Run tests and verify GREEN**

Expected: exact 68 / 204 promotion only when both evidence families verify.

- [ ] **Step 6: Commit**

```bash
git add products/canon_portfolio_product_grade.py tests/test_canon_portfolio_68_product_grade.py
git commit -m "Add immutable 68x3 portfolio ProductGrade receipt"
```

---

### Task 7: Update CLIs for production acceptance without synthesizing proof state

**Files:**
- Modify: `scripts/run_canon_extension_native_product_grade.py`
- Modify: `scripts/run_canon_extension_product_grade.py`
- Create: `scripts/run_canon_portfolio_product_grade.py`
- Modify: `tests/test_canon_extension_native_product_grade_cli.py`
- Modify: `tests/test_canon_portfolio_68_product_grade.py`

**Interfaces:**
- Native CLI: runs all 15×3 against real repo evidence inputs.
- Extension CLI: runs upstream Studio ProductGrade, native 15×3, then extension promotion.
- Portfolio CLI: consumes the historical anchor and extension receipt, writes portfolio receipt, supports `--require-all`.

- [ ] **Step 1: Write failing CLI contract tests**

Test that `--require-all` returns non-zero when any real prerequisite is missing or any product refuses. Test the success path only with an explicitly seeded temporary repo in unit tests.

- [ ] **Step 2: Run CLI tests and verify RED**

Expected: old native CLI still describes 11 products and the portfolio CLI does not exist.

- [ ] **Step 3: Update the native CLI**

It must print the extension 15×3 acceptance token and return code 2 under `--require-all` unless the token is exact.

- [ ] **Step 4: Update the extension orchestration CLI**

Order:

```text
existing canon artifacts + seals must already exist
        ↓
run_product_grade_gauntlet() for four upstream Studios
        ↓
run_native_product_grade_batch() for all 15 × 3
        ↓
run_canon_extension_product_grade_gauntlet()
        ↓
write extension receipt / print extension token
```

Do not invoke any helper that creates fake canon artifacts merely to make acceptance pass.

- [ ] **Step 5: Add the portfolio CLI**

Arguments:

```text
--historical-anchor evidence/historical/PROFESSIONAL_EVIDENCE_53_X3_ANCHOR.json
--extension-receipt state/product_grade/canon_extensions/CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json
--output state/product_grade/canon_portfolio_68
--require-all
```

It loads both inputs, runs the aggregator, prints JSON plus the acceptance token, and returns 2 when required promotion fails.

- [ ] **Step 6: Run CLI tests and verify GREEN**

- [ ] **Step 7: Commit**

```bash
git add scripts/run_canon_extension_native_product_grade.py scripts/run_canon_extension_product_grade.py scripts/run_canon_portfolio_product_grade.py tests/test_canon_extension_native_product_grade_cli.py tests/test_canon_portfolio_68_product_grade.py
git commit -m "Wire 15x3 and 68x3 ProductGrade CLIs"
```

---

### Task 8: Make CI prove code behavior and separately gate real acceptance state

**Files:**
- Modify: `.github/workflows/dio-canon-extension-productgrade.yml`

**Interfaces:**
- Test job proves deterministic logic using temporary fixtures.
- Acceptance job runs only when repository/workflow context has the required real canon-extension state; it fails closed if explicitly requested and inputs are missing.

- [ ] **Step 1: Expand the test job**

Run:

```bash
PYTHONNOUSERSITE=1 python -m pytest -q \
  tests/test_canon_extension_product_grade.py \
  tests/test_canon_extension_native_product_grade.py \
  tests/test_canon_extension_dual_bound_receipt.py \
  tests/test_canon_extension_native_product_grade_cli.py \
  tests/test_canon_portfolio_68_product_grade.py
```

- [ ] **Step 2: Add static acceptance-token contract checks**

Use a short Python step to import the constants and assert they equal:

```text
DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED
DIO_CANON_PORTFOLIO_68_X3_PRODUCT_GRADE_VERIFIED
```

- [ ] **Step 3: Do not manufacture missing production state in CI**

If `state/product_portfolio/canon_extensions` is absent in a clean checkout, the regular test job still passes from temp fixtures, but no workflow step may claim the real 45-journey production acceptance token. A manually dispatched production-acceptance mode must fail with a clear missing-state message unless real state has been committed/materialized before invocation.

- [ ] **Step 4: Upload real receipts only when they exist**

Use `actions/upload-artifact@v4` with `if: always()` and `if-no-files-found: ignore` for:

```text
state/product_grade/canon_extensions/**
state/product_grade/canon_portfolio_68/**
```

This preserves actual acceptance evidence without fabricating it.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/dio-canon-extension-productgrade.yml
git commit -m "Expand canon extension ProductGrade CI"
```

---

### Task 9: Run the real 15×3 production gauntlet on the DIO repo state

**Files:**
- No code changes expected. This task produces state receipts under `state/product_grade/`.

**Interfaces:**
- Consumes: real generated canon-extension artifacts, historical generation receipts, canon proof seals, four upstream Studio ProductGrade inputs, and the frozen historical 53 anchor.
- Produces: 45 variant receipts, 15 aggregate product receipts, one extension receipt, and one portfolio receipt.

- [ ] **Step 1: Verify the real canon-extension state exists before running**

Run:

```bash
find state/product_portfolio/canon_extensions -maxdepth 3 -type f | sort
```

Expected: current artifacts and preserved generation receipts for all eleven receipt-bound products. For any missing required input, stop and run the existing canonical generation workflow that originally created that state; do not seed test HTML into production state.

- [ ] **Step 2: Seal receipt-bound canon artifacts**

Run:

```bash
PYTHONNOUSERSITE=1 python scripts/seal_canon_extension_proofs.py --require-all
```

Expected: seal acceptance token and exit 0. Any refusal blocks ProductGrade.

- [ ] **Step 3: Run the full extension CLI**

Run:

```bash
PYTHONNOUSERSITE=1 python scripts/run_canon_extension_product_grade.py --require-all
```

Expected final extension token:

```text
DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED
```

- [ ] **Step 4: Inspect extension counts, not just the token**

Use Python to load the receipt and assert 15 products, 45 controlled journeys, 45 verified, zero refused, 15 ProductGrade verified, authority/external false.

- [ ] **Step 5: Run the portfolio aggregator**

Run:

```bash
PYTHONNOUSERSITE=1 python scripts/run_canon_portfolio_product_grade.py --require-all
```

Expected token:

```text
DIO_CANON_PORTFOLIO_68_X3_PRODUCT_GRADE_VERIFIED
```

- [ ] **Step 6: Inspect the portfolio receipt**

Assert 53 + 15 = 68, 159 + 45 = 204, historical blob identity equals `7ffeb400a4ec0ffd51d0a10c3035d3303fd24c4e`, and `historical_53_receipt_mutated` is false.

- [ ] **Step 7: Run the full targeted suite again**

Run the exact five-file pytest command from Task 8. Expected: all green.

- [ ] **Step 8: Commit only durable code/anchor changes; treat generated state according to repository evidence policy**

If the repo convention keeps ProductGrade state out of Git, preserve the receipts as CI/workflow artifacts and record their fingerprints in the branch/PR description. Do not silently add megabytes of generated state contrary to `.gitignore` or existing policy.

---

### Task 10: Promote the public DIO Workflows site only after the proof tokens exist

**Files in `Byron2306/DIO-Workflows`:**
- Modify: `products/catalog.js`
- Modify: `products/app.js`
- Modify: `products/index.html`
- Modify: `index.html`
- Modify: `products/proof/public-production-proof.html` or add a new extension/portfolio receipt presentation without rewriting the historical 53 receipt
- Modify: `.github/workflows/public-portfolio-check.yml`
- Modify: `.github/workflows/storefront-check.yml`
- Modify: `tests/test_portfolio_68_and_films_contract.py`

**Interfaces:**
- Consumes: verified extension token and verified portfolio token from Full Audit.
- Produces: public capability labels that accurately separate ProductGrade proof from market validation.

- [ ] **Step 1: Write failing public-site contract tests**

For all 15 extensions assert:

```text
status == PRODUCT_GRADE_VERIFIED
variantCount == 3
verifiedVariantCount == 3
```

Renderer contract must contain `PRODUCT GRADE VERIFIED · 3/3` and must not use `UNPROVED` as the primary capability badge for extensions.

- [ ] **Step 2: Run public-site tests and verify RED**

Expected: current candidate labels fail.

- [ ] **Step 3: Update extension catalog truth**

Promote only the capability fields supported by the new receipts. Preserve a separate market-truth field such as `commercialValidation: "UNPROVED"` in machine data if desired, while rendering it as `Market validation · not yet established` rather than the product's main status.

- [ ] **Step 4: Update proof presentation**

Public portfolio language must say the 204 total consists of the preserved historical 159 base-canon journeys plus 45 newly verified extension journeys. Do not modify `PROFESSIONAL_EVIDENCE_53_X3_RECEIPT.json`.

- [ ] **Step 5: Run the complete public-site test suite and static checks**

Expected: all green before deployment.

- [ ] **Step 6: Commit and deploy `DIO-Workflows` main**

Commit message should identify the proof basis, for example:

```text
Promote 15 canon extensions after 45-journey ProductGrade verification
```

Then verify GitHub Pages deployment and live domain labels.

---

## Final Verification Checklist

Before declaring the programme complete, all of the following must be observed from fresh commands or workflow evidence:

- [ ] 15 native profiles exist.
- [ ] Every profile has exactly normal, messy, adversarial fixtures.
- [ ] 45 isolated variant receipts exist and pass.
- [ ] 15 aggregate extension product receipts report `PRODUCT_GRADE_VERIFIED` and 3/3.
- [ ] All four Studio extensions bind upstream Studio ProductGrade provenance and also have native 3/3 execution.
- [ ] Extension receipt reports 15 products, 45 journeys, 45 verified, 0 refused.
- [ ] Extension token is exactly `DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED`.
- [ ] Historical anchor remains pinned to DIO-Workflows commit `3119e290efd62cdeccd3f4f5938cc5be85014464` and blob `7ffeb400a4ec0ffd51d0a10c3035d3303fd24c4e`.
- [ ] Portfolio receipt reports 68 products and 204 controlled journeys.
- [ ] Portfolio token is exactly `DIO_CANON_PORTFOLIO_68_X3_PRODUCT_GRADE_VERIFIED`.
- [ ] Authority creation and external effects are false across all new controlled journeys.
- [ ] Machine commercial validation remains honest and separate from ProductGrade status.
- [ ] Full targeted pytest suite passes.
- [ ] GitHub Actions test workflow passes.
- [ ] Public site is not promoted until the real extension and portfolio tokens have been obtained.
- [ ] After promotion, public extensions show `PRODUCT GRADE VERIFIED · 3/3` while market validation remains separately qualified.
