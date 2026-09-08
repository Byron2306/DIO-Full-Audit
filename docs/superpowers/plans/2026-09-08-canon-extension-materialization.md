# Canon Extension Materialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, truth-bound materialization stage for the 11 receipt-bound canon extensions so a clean checkout can complete the real 15x3 and 68x3 ProductGrade acceptance chain.

**Architecture:** Generate each receipt-bound canon extension's stable `site/index.html` from its existing native profile and bind it to the immutable historical 53x3 anchor with `CANON_EXTENSION_MATERIALIZATION_RECEIPT.json`. Harden the existing provenance sealer to require source-receipt artifact-hash binding, then insert materialization before sealing in CI and retain both canon and buyer HTML proof artifacts.

**Tech Stack:** Python 3.12+, pytest, pathlib, hashlib, json, existing DIO ProductGrade/native-profile modules, GitHub Actions YAML.

**Spec:** `docs/superpowers/specs/2026-09-08-canon-extension-materialization-design.md`

## Global Constraints

- Materialize exactly the 11 `proof_kind == "receipt_bound"` canon extensions.
- Do not rematerialize or alter the four `studio_product_grade` extensions.
- Never emit or fabricate `GAMMA_RECEIPT.json` for canon extension provenance.
- Preserve `authority_created: false` and `external_effects: false` everywhere in the new proof chain.
- Preserve `commercial_validation: UNPROVED`.
- Historical lineage root is `evidence/historical/PROFESSIONAL_EVIDENCE_53_X3_ANCHOR.json`; its bytes must remain unchanged.
- Materialization must be deterministic: repeated runs with unchanged inputs produce byte-identical HTML and receipts.
- Existing 15x3 and 68x3 ProductGrade behavior must remain intact.

---

### Task 1: Add failing materialization contract tests

**Files:**
- Create: `tests/test_canon_extension_materializer.py`
- Test: `tests/test_canon_extension_materializer.py`

**Interfaces:**
- Consumes: `CANON_EXTENSIONS`, `native_profile`, immutable historical anchor file.
- Produces expected API contract for `materialize_receipt_bound_extensions(*, root: Path) -> dict[str, Any]` and `MATERIALIZED_TOKEN`.

- [ ] **Step 1: Write failing tests**

Create tests that import:

```python
from products.canon_extension_materializer import (
    MATERIALIZATION_FILENAME,
    MATERIALIZED_TOKEN,
    materialize_receipt_bound_extensions,
)
```

Required assertions:

```python
receipt = materialize_receipt_bound_extensions(root=tmp_path)
assert receipt["acceptance_token"] == MATERIALIZED_TOKEN
assert receipt["target_count"] == 11
assert receipt["materialized_count"] == 11
assert receipt["refuse_count"] == 0
```

Seed the immutable anchor into `tmp_path/evidence/historical/PROFESSIONAL_EVIDENCE_53_X3_ANCHOR.json` from the real repository anchor bytes before calling the materializer.

For each receipt-bound spec, assert:

```python
site = tmp_path / spec["primary_artifact"]
source_receipt = site.parent / MATERIALIZATION_FILENAME
assert site.is_file()
assert source_receipt.is_file()
row = json.loads(source_receipt.read_text())
assert row["status"] == "PASS"
assert row["primary_artifact"] == spec["primary_artifact"]
assert row["primary_artifact_sha256"] == sha256(site.read_bytes()).hexdigest()
assert row["authority_created"] is False
assert row["external_effects"] is False
assert row["commercial_validation"] == "UNPROVED"
```

Add a determinism test that records SHA-256 hashes for every generated HTML and receipt, reruns materialization, and asserts the hashes are unchanged.

Add an anchor/profile binding test asserting every receipt has the live historical anchor hash and a `sha256:`-prefixed profile fingerprint.

- [ ] **Step 2: Run the test to verify RED**

Run:

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_canon_extension_materializer.py
```

Expected: collection/import failure because `products.canon_extension_materializer` does not exist.

- [ ] **Step 3: Commit RED test**

```bash
git add tests/test_canon_extension_materializer.py
git commit -m "test: define canon extension materialization contract"
```

---

### Task 2: Implement deterministic canon materializer

**Files:**
- Create: `products/canon_extension_materializer.py`
- Create: `scripts/materialize_canon_extensions.py`
- Test: `tests/test_canon_extension_materializer.py`

**Interfaces:**
- Consumes: `CANON_EXTENSIONS`, `native_profile(slug)`, anchor bytes at `evidence/historical/PROFESSIONAL_EVIDENCE_53_X3_ANCHOR.json`.
- Produces:
  - `MATERIALIZATION_SCHEMA = "dio.canon_extension.materialization_receipt.v1"`
  - `MATERIALIZATION_FILENAME = "CANON_EXTENSION_MATERIALIZATION_RECEIPT.json"`
  - `MATERIALIZED_TOKEN = "DIO_CANON_EXTENSION_11_MATERIALIZED"`
  - `materialize_receipt_bound_extension(*, spec: dict[str, Any], root: Path) -> dict[str, Any]`
  - `materialize_receipt_bound_extensions(*, root: Path) -> dict[str, Any]`

- [ ] **Step 1: Implement deterministic hashing helpers**

Use canonical JSON and SHA-256 helpers:

```python
def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()
```

- [ ] **Step 2: Implement buyer-readable deterministic HTML renderer**

Render only deterministic fields from the native profile and its normal fixture. Include product name, buyer, family/mode, normal subject/purpose, supplied evidence/requirements/questions/criteria where present, and a fixed boundary paragraph stating that human authority remains required and no external effect or commercial validation is created.

Do not include timestamps, random IDs, environment-specific paths, network results, or mutable runtime metadata.

- [ ] **Step 3: Implement one-extension materialization**

For `proof_kind != "receipt_bound"`, raise `ValueError`.

Require the historical anchor file to exist. Compute:

```python
historical_anchor_sha256 = sha256(anchor.read_bytes()).hexdigest()
profile_fingerprint = _fingerprint(native_profile(spec["slug"]))
```

Write the canon HTML to `root / spec["primary_artifact"]`, then emit beside it:

```python
{
    "schema": MATERIALIZATION_SCHEMA,
    "status": "PASS",
    "canon_id": spec["canon_id"],
    "name": spec["name"],
    "slug": spec["slug"],
    "primary_artifact": spec["primary_artifact"],
    "primary_artifact_sha256": <live sha>,
    "profile_fingerprint": <sha256:...>,
    "historical_anchor": "evidence/historical/PROFESSIONAL_EVIDENCE_53_X3_ANCHOR.json",
    "historical_anchor_sha256": <live anchor sha>,
    "authority_created": False,
    "external_effects": False,
    "commercial_validation": "UNPROVED",
    "claim_boundary": "...",
    "receipt_fingerprint": <deterministic sha256 fingerprint>
}
```

- [ ] **Step 4: Implement 11-extension batch materialization**

Filter `CANON_EXTENSIONS` to `proof_kind == "receipt_bound"`. Materialize each one independently, collect failures without minting PASS, and emit:

```python
{
    "schema": "dio.canon_extension.materialization_batch.v1",
    "acceptance_token": MATERIALIZED_TOKEN if len(rows) == 11 and not failures else "DIO_CANON_EXTENSION_MATERIALIZATION_REFUSE",
    "target_count": 11,
    "materialized_count": len(rows),
    "refuse_count": len(failures),
    "materializations": rows,
    "failures": failures,
    "authority_created": False,
    "external_effects": False,
    "commercial_validation": "UNPROVED"
}
```

- [ ] **Step 5: Add CLI**

`scripts/materialize_canon_extensions.py` prints the JSON batch receipt and acceptance token. `--require-all` returns non-zero unless the token equals `DIO_CANON_EXTENSION_11_MATERIALIZED`.

- [ ] **Step 6: Run materializer tests to verify GREEN**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_canon_extension_materializer.py
```

Expected: all tests pass.

- [ ] **Step 7: Commit implementation**

```bash
git add products/canon_extension_materializer.py scripts/materialize_canon_extensions.py tests/test_canon_extension_materializer.py
git commit -m "feat: materialize receipt-bound canon extensions"
```

---

### Task 3: Replace fictional Gamma receipt dependency and harden sealing

**Files:**
- Modify: `products/canon_extension_product_grade.py`
- Modify: `products/canon_extension_proof_seal.py`
- Modify: `tests/test_canon_extension_materializer.py`
- Test: existing canon extension tests

**Interfaces:**
- Consumes: `CANON_EXTENSION_MATERIALIZATION_RECEIPT.json` containing `primary_artifact_sha256`.
- Produces: existing `CANON_EXTENSION_PROOF_RECEIPT.json`, now refusing source receipts that do not bind the current artifact SHA.

- [ ] **Step 1: Write failing tamper/seal test**

After materialization, call `seal_receipt_bound_extension(spec=spec, root=tmp_path)` and assert PASS. Then mutate `site/index.html` and assert a second seal attempt raises `CanonExtensionProofSealError` because the source receipt's declared artifact SHA no longer matches the live bytes.

- [ ] **Step 2: Run the test to verify RED**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_canon_extension_materializer.py -k seal
```

Expected: the tampered artifact is currently accepted by the sealer.

- [ ] **Step 3: Change receipt-bound spec paths**

For all 11 receipt-bound rows in `CANON_EXTENSIONS`, replace:

```python
"proof_receipt": f"{_BASE}/<slug>/site/GAMMA_RECEIPT.json"
```

with:

```python
"proof_receipt": f"{_BASE}/<slug>/site/CANON_EXTENSION_MATERIALIZATION_RECEIPT.json"
```

Leave the four Studio rows unchanged.

- [ ] **Step 4: Harden source receipt binding**

In `seal_receipt_bound_extension`, after loading the source receipt and checking it does not report failure, require that one of the source receipt's string values equals either the live artifact SHA or `sha256:<live artifact SHA>`. Reuse a small recursive string collector or an explicit artifact-hash field check.

If no binding exists, raise:

```python
CanonExtensionProofSealError("generation receipt does not bind current artifact sha256: ...")
```

- [ ] **Step 5: Run targeted and existing canon tests**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q \
  tests/test_canon_extension_materializer.py \
  tests/test_canon_extension_product_grade.py \
  tests/test_canon_extension_native_product_grade.py \
  tests/test_canon_extension_dual_bound_receipt.py \
  tests/test_canon_extension_15x3_promotion.py \
  tests/test_canon_extension_native_product_grade_cli.py \
  tests/test_canon_portfolio_68_product_grade.py \
  tests/test_canon_portfolio_product_grade_cli.py
```

Expected: all pass.

- [ ] **Step 6: Commit seal/provenance correction**

```bash
git add products/canon_extension_product_grade.py products/canon_extension_proof_seal.py tests/test_canon_extension_materializer.py
git commit -m "fix: bind canon extension seals to truthful materialization receipts"
```

---

### Task 4: Wire clean-checkout acceptance workflow

**Files:**
- Modify: `.github/workflows/dio-canon-extension-productgrade.yml`
- Test: workflow execution on branch push

**Interfaces:**
- Consumes: `scripts/materialize_canon_extensions.py --require-all`.
- Produces: clean-checkout CI sequence proving materialization, sealing, 15x3, 68x3, and retained HTML proof.

- [ ] **Step 1: Add materializer files/tests to workflow path filters**

Add:

```yaml
- 'products/canon_extension_materializer.py'
- 'scripts/materialize_canon_extensions.py'
- 'tests/test_canon_extension_materializer.py'
```

- [ ] **Step 2: Include materializer test in test step**

Add `tests/test_canon_extension_materializer.py` to the pytest invocation.

- [ ] **Step 3: Materialize before sealing**

Immediately after historical-anchor hash capture, add:

```yaml
- name: Materialize 11 receipt-bound canon extensions
  run: PYTHONNOUSERSITE=1 python scripts/materialize_canon_extensions.py --require-all
```

- [ ] **Step 4: Assert materialization counts**

Add a shell step that asserts exactly 11 `site/index.html` files and exactly 11 `CANON_EXTENSION_MATERIALIZATION_RECEIPT.json` files under `state/product_portfolio/canon_extensions`.

- [ ] **Step 5: Assert native buyer artifact count**

After native 15x3 execution, assert exactly 45 `variants/*/customer_delivery/index.html` files.

- [ ] **Step 6: Upload inspectable proof artifacts**

Extend `actions/upload-artifact` paths to include:

```yaml
state/product_portfolio/canon_extensions/**/site/index.html
state/product_portfolio/canon_extensions/**/CANON_EXTENSION_MATERIALIZATION_RECEIPT.json
state/product_grade/canon_extensions/**/customer_delivery/index.html
```

Retain existing JSON evidence paths.

- [ ] **Step 7: Commit workflow**

```bash
git add .github/workflows/dio-canon-extension-productgrade.yml
git commit -m "ci: materialize canon extensions before ProductGrade acceptance"
```

---

### Task 5: Execute real local/CI proof chain and verify acceptance

**Files:**
- Generated only under `state/product_portfolio/canon_extensions/` and `state/product_grade/`.
- No additional source changes unless a failing test exposes a root-cause defect.

**Interfaces:**
- Consumes: completed Tasks 1-4.
- Produces: evidence of 11/11, 15/15, 45/45, 68/68, 204/204.

- [ ] **Step 1: Run materialization**

```bash
PYTHONNOUSERSITE=1 python scripts/materialize_canon_extensions.py --require-all
```

Expected token:

`DIO_CANON_EXTENSION_11_MATERIALIZED`

- [ ] **Step 2: Seal 11**

```bash
PYTHONNOUSERSITE=1 python scripts/seal_canon_extension_proofs.py --require-all
```

Expected token:

`DIO_CANON_EXTENSION_PROOF_SEALS_WRITTEN`

- [ ] **Step 3: Execute native 15x3**

```bash
rm -rf state/product_grade/canon_extensions
PYTHONNOUSERSITE=1 python scripts/run_canon_extension_native_product_grade.py --output state/product_grade/canon_extensions --require-all
```

Expected token:

`DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED`

- [ ] **Step 4: Aggregate 15 and seal 68x3**

```bash
PYTHONNOUSERSITE=1 python scripts/run_canon_extension_product_grade.py --output state/product_grade/canon_extension_aggregate --require-proof --require-all
PYTHONNOUSERSITE=1 python scripts/run_canon_portfolio_product_grade.py --extension-receipt state/product_grade/canon_extension_aggregate/CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json --output state/product_grade/canon_portfolio --require-all
```

Expected portfolio token:

`DIO_CANON_PORTFOLIO_68_X3_PRODUCT_GRADE_VERIFIED`

- [ ] **Step 5: Verify counts and hashes**

Assert:

```text
canon sites = 11
materialization receipts = 11
canon seals = 11
buyer HTML artifacts = 45
extensions ProductGrade = 15/15
extension journeys = 45/45
portfolio ProductGrade = 68/68
portfolio journeys = 204/204
historical_53_receipt_mutated = false
```

- [ ] **Step 6: Inspect branch CI**

Confirm the `DIO Canon Extension ProductGrade` workflow passes every step from a clean checkout and uploads the expected evidence artifact.

---

### Task 6: Final verification and red-pen review

**Files:**
- Review all changed files from Tasks 1-4.

**Interfaces:**
- Consumes: passing tests and CI evidence.
- Produces: completion claim only if evidence supports it.

- [ ] **Step 1: Run full targeted suite once more**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q \
  tests/test_canon_extension_materializer.py \
  tests/test_canon_extension_product_grade.py \
  tests/test_canon_extension_native_product_grade.py \
  tests/test_canon_extension_dual_bound_receipt.py \
  tests/test_canon_extension_15x3_promotion.py \
  tests/test_canon_extension_native_product_grade_cli.py \
  tests/test_canon_portfolio_68_product_grade.py \
  tests/test_canon_portfolio_product_grade_cli.py
```

- [ ] **Step 2: Review claim boundaries**

Search generated/source receipts for accidental commercial or authority inflation and confirm all new receipts preserve `UNPROVED`, `authority_created: false`, and `external_effects: false`.

- [ ] **Step 3: Review diff**

Confirm there are no unrelated changes, no `GAMMA_RECEIPT.json` fabrication, no mutation of the historical anchor, and no change to four Studio provenance semantics.

- [ ] **Step 4: Completion criterion**

Only declare the real proof chain closed after both targeted tests and clean-checkout CI report all required acceptance tokens and counts.
