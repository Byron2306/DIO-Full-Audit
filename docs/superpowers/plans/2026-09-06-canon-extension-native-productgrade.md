# Canon Extension Native ProductGrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dual-bound native ProductGrade harness that can truthfully promote the eleven receipt-bound canon extensions only after real controlled buyer-artifact execution, Lingua custody, BEAST checks and unseen-input generalisation.

**Architecture:** A profile registry defines the eleven products and four proof families. A native runner registers family-generated semantic units through Lingua, renders a separate customer HTML artifact, runs BEAST over that package, repeats the path with an unseen fixture, and emits a v2 dual-bound receipt. The existing canon-extension gauntlet then validates both canon and customer live-byte bindings.

**Tech Stack:** Python 3.12, pytest, DIO Lingua lifecycle, BEAST QualityCascade, stdlib HTML/hash/JSON/path utilities.

**Spec:** `docs/superpowers/specs/2026-09-06-canon-extension-native-productgrade-design.md`

## Global Constraints

- The existing 15/15 canon-extension proof seals are preserved byte-for-byte.
- Canon surface identity and customer artifact ProductGrade are separate bindings.
- No v2 receipt may verify unless its live customer artifact hash is checked.
- Lingua custody must come from `register_product_source`, not a manually asserted boolean.
- BEAST must run through `run_beast_artifact_checks` in production.
- Unseen-input generalisation must re-run the same family path with a materially different fixture.
- `external_effects` and `authority_created` remain `false`.
- `customers_will_pay`, `verified_payment`, and `commercial_validation` remain `UNPROVED`.

---

### Task 1: Define the eleven native ProductGrade profiles

**Files:**
- Create: `products/canon_extension_native_profiles.py`
- Test: `tests/test_canon_extension_native_product_grade.py`

**Interfaces:**
- Produces: `NATIVE_CANON_EXTENSION_PROFILES: tuple[dict[str, Any], ...]`
- Produces: `native_profile(slug: str) -> dict[str, Any]`
- Each profile exposes `slug`, `family`, `buyer`, `baseline`, `unseen`, `baseline_anchor`, `mutation_anchor`, and `forbidden_claims`.

- [ ] **Step 1: Write the failing profile-registry test**

```python
def test_native_profile_registry_covers_exactly_the_eleven_receipt_bound_extensions():
    expected = {
        "article-publication", "contract-desk", "corporate-readiness",
        "entrepreneurproof", "finance-readiness", "fundingfinder",
        "investorproof", "launch-studio", "popia-readiness",
        "professional-correspondence", "report-pitch-studio",
    }
    assert {row["slug"] for row in NATIVE_CANON_EXTENSION_PROFILES} == expected
    assert all(row["baseline_anchor"] != row["mutation_anchor"] for row in NATIVE_CANON_EXTENSION_PROFILES)
```

- [ ] **Step 2: Run the test and verify RED**

Run: `PYTHONNOUSERSITE=1 python -m pytest -q tests/test_canon_extension_native_product_grade.py`

Expected: import failure because `products.canon_extension_native_profiles` does not exist.

- [ ] **Step 3: Implement the profile registry**

Create explicit controlled fixtures for all eleven products. Fixtures must be structured data, not pre-written final HTML. The four accepted family values are `publication_professional`, `readiness_assurance`, `opportunity_venture`, and `launch_orchestration`.

- [ ] **Step 4: Re-run and verify GREEN**

Run the same pytest command. Expected: profile test passes.

- [ ] **Step 5: Commit**

Commit message: `Define native ProductGrade profiles for canon extensions`.

---

### Task 2: Build family semantic units and deterministic buyer HTML

**Files:**
- Create: `products/canon_extension_native_product_grade.py`
- Modify: `tests/test_canon_extension_native_product_grade.py`

**Interfaces:**
- Produces: `build_semantic_rows(profile: dict[str, Any], fixture: dict[str, Any]) -> list[dict[str, str]]`
- Produces: `render_buyer_html(*, title: str, semantic_object: dict[str, Any], output_path: Path) -> None`
- Semantic rows must be generated from fixture fields and carry stable paragraph IDs.

- [ ] **Step 1: Add failing tests for each family**

Tests assert that baseline fixtures produce semantic rows containing their baseline anchor and that unseen fixtures contain mutation anchors without the baseline-only anchor.

- [ ] **Step 2: Verify RED**

Run the focused test file. Expected: missing functions.

- [ ] **Step 3: Implement minimal family builders and HTML renderer**

The renderer must consume the Lingua semantic object's `source.units`, HTML-escape all text, produce valid UTF-8 HTML with title/sections, and include no DIO receipt/proof language in visible customer copy.

- [ ] **Step 4: Verify GREEN**

Run focused tests.

- [ ] **Step 5: Commit**

Commit message: `Render native canon extension buyer artifacts from semantic units`.

---

### Task 3: Execute one dual-bound native ProductGrade case

**Files:**
- Modify: `products/canon_extension_native_product_grade.py`
- Modify: `tests/test_canon_extension_native_product_grade.py`

**Interfaces:**
- Produces: `run_native_product_grade_case(*, slug: str, root: Path, output_dir: Path, beast_checker: Callable[..., dict[str, Any]] = run_beast_artifact_checks) -> dict[str, Any]`
- Persists `PRODUCT_GRADE_RECEIPT.json`, baseline customer HTML, isolated Lingua object/receipt, and unseen evidence.

- [ ] **Step 1: Add a failing happy-path test with a deterministic BEAST test checker**

The test creates a temporary repo root containing a canon surface and canon proof receipt, calls `run_native_product_grade_case`, and asserts:

```python
assert receipt["schema"] == "dio.product_grade.canon_extension_native.v2"
assert receipt["status"] == "PRODUCT_GRADE_VERIFIED"
assert receipt["canon_artifact_sha256"] != receipt["customer_artifact_sha256"]
assert receipt["lingua_semantic_custody"] is True
assert receipt["beast_mechanical_pass"] is True
assert receipt["unseen_input_generalisation"] is True
assert receipt["external_effects"] is False
assert receipt["authority_created"] is False
```

The injected checker exists only to isolate the unit test from the harvested BEAST subprocess. Production default remains the real BEAST adapter.

- [ ] **Step 2: Verify RED**

Run focused tests. Expected: missing runner.

- [ ] **Step 3: Implement baseline execution**

Implementation sequence:

1. resolve and contain-check canon/proof paths;
2. hash canon and proof live bytes;
3. build baseline semantic rows;
4. call `register_product_source` into `output_dir / "lingua_state"`;
5. persist registration receipt;
6. render baseline `customer_delivery/index.html`;
7. invoke `beast_checker(dio_root=root, workspace=customer_delivery_dir)`;
8. execute family anchor/forbidden-claim checks;
9. run unseen fixture through a separate isolated Lingua/output path;
10. compute unseen anchor/hash checks;
11. write the v2 receipt.

- [ ] **Step 4: Verify GREEN**

Run focused tests.

- [ ] **Step 5: Commit**

Commit message: `Execute dual-bound native ProductGrade cases`.

---

### Task 4: Add fail-closed tamper and semantic-boundary tests

**Files:**
- Modify: `tests/test_canon_extension_native_product_grade.py`
- Modify: `products/canon_extension_native_product_grade.py`

**Interfaces:** Existing Task 3 API.

- [ ] **Step 1: Add failing tests**

Add separate tests proving REFUSE when:

- BEAST reports `mechanical_pass: false`;
- unseen output retains the baseline-only anchor;
- a family forbidden claim appears;
- canon proof receipt is missing;
- a customer artifact path would escape the output/root boundary.

- [ ] **Step 2: Verify RED**

Run focused tests and confirm the new cases expose missing fail-closed checks.

- [ ] **Step 3: Implement minimal refusal logic**

Every failed gate must be recorded in `critical_blockers`; status is verified only with an empty blocker set.

- [ ] **Step 4: Verify GREEN**

Run focused tests.

- [ ] **Step 5: Commit**

Commit message: `Fail closed on native ProductGrade evidence drift`.

---

### Task 5: Teach the canon gauntlet to validate v2 dual binding

**Files:**
- Modify: `products/canon_extension_product_grade.py`
- Modify: `tests/test_canon_extension_product_grade.py`

**Interfaces:**
- Change `_native_receipt_checks` to accept root/spec context for v2 receipts.
- For v2, validate both canon live bytes and customer live bytes plus canon proof live hash.
- Preserve legacy single-artifact receipt behavior.

- [ ] **Step 1: Add failing v2 validation tests**

Create a v2 receipt with a real temporary customer artifact. Assert acceptance, then mutate the customer artifact and assert `native_product_grade_customer_artifact_mismatch`.

- [ ] **Step 2: Verify RED**

Run: `PYTHONNOUSERSITE=1 python -m pytest -q tests/test_canon_extension_product_grade.py tests/test_canon_extension_native_product_grade.py`

- [ ] **Step 3: Implement v2 gauntlet validation**

For v2 receipts require:

```text
canon_artifact_sha256 == live canon SHA
canon_proof_receipt_sha256 == live CANON_EXTENSION_PROOF_RECEIPT.json SHA
customer_artifact exists inside root
customer_artifact_sha256 == live customer artifact SHA
primary_artifact_sha256 == customer_artifact_sha256
beast_mechanical_pass == true
lingua_semantic_custody == true
unseen_input_generalisation == true
external_effects == false
authority_created == false
```

- [ ] **Step 4: Verify GREEN**

Run both test files.

- [ ] **Step 5: Commit**

Commit message: `Validate dual-bound native ProductGrade receipts`.

---

### Task 6: Add the eleven-product native batch runner

**Files:**
- Create: `scripts/run_canon_extension_native_product_grade.py`
- Modify: `tests/test_canon_extension_native_product_grade.py`

**Interfaces:**
- Produces: `run_native_product_grade_batch(*, root: Path, output_root: Path, beast_checker=...) -> dict[str, Any]`
- CLI default output: `state/product_grade/canon_extensions`
- CLI flag: `--require-all`
- Acceptance token: `DIO_CANON_EXTENSION_NATIVE_PRODUCT_GRADE_VERIFIED` only when 11/11 verify.

- [ ] **Step 1: Add failing batch test**

Use a temporary repo with all eleven canon surfaces/proof receipts and a deterministic passing checker. Assert `target_count == 11`, `verified_count == 11`, and no refusals.

- [ ] **Step 2: Verify RED**

Run focused tests.

- [ ] **Step 3: Implement batch and CLI**

The batch writes one case directory per slug and a `NATIVE_CANON_EXTENSION_PRODUCT_GRADE_BATCH_RECEIPT.json` summary.

- [ ] **Step 4: Verify GREEN**

Run focused tests.

- [ ] **Step 5: Commit**

Commit message: `Add native ProductGrade batch for eleven canon extensions`.

---

### Task 7: Put the native tests behind CI

**Files:**
- Modify: `.github/workflows/dio-canon-extension-productgrade.yml`

**Interfaces:** CI must run both ProductGrade test files.

- [ ] **Step 1: Update workflow paths and pytest command**

Run:

```text
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_canon_extension_product_grade.py tests/test_canon_extension_native_product_grade.py
```

- [ ] **Step 2: Push the test-first state before production implementation when possible and observe expected RED**

Capture the failing workflow run as TDD evidence.

- [ ] **Step 3: After Tasks 1-6 are implemented, observe GREEN**

Require the workflow job to complete successfully.

- [ ] **Step 4: Commit**

Commit message: `Gate native canon extension ProductGrade in CI`.

---

### Task 8: Real local 11/11 and portfolio 15/15 verification

**Files:** No new production code unless the real run exposes a defect.

**Interfaces:**
- `python -m scripts.run_canon_extension_native_product_grade --require-all`
- `python -m scripts.run_canon_extension_product_grade --output /tmp/dio-canon-extension-grade --require-all`

- [ ] **Step 1: User cherry-picks the runtime commits onto the current DIO working branch**

Preserve the existing local state and canon seals.

- [ ] **Step 2: Run the native eleven-product batch**

Expected summary:

```text
target_count: 11
verified_count: 11
refuse_count: 0
DIO_CANON_EXTENSION_NATIVE_PRODUCT_GRADE_VERIFIED
```

- [ ] **Step 3: Run the existing 15-extension gauntlet with `--require-all`**

Expected:

```text
extension_count: 15
product_grade_verified_count: 15
product_grade_refuse_count: 0
all_product_grade_verified: true
DIO_CANON_EXTENSION_PRODUCT_GRADE_VERIFIED
commercial_validation: UNPROVED
```

- [ ] **Step 4: Preserve the final receipts and hashes**

Archive the eleven native receipts, batch receipt, and final 15-extension receipt without rewriting the historical Gamma or canon proof receipts.
