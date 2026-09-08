# DIO 68-Product Portfolio Truth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every current portfolio consumer derive and display 68 products from the unchanged 53-row historical crosswalk plus the frozen verified 15-extension receipt.

**Architecture:** `portfolio_runtime.py` remains the sole derivation boundary. The historical crosswalk and independently verified extension receipt remain separate evidence inputs; consumers receive one versioned projection with explicit component counts and fail closed to 53 when extension evidence is absent or invalid.

**Tech Stack:** Python 3, pytest, JSON, CSV, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-09-08-dio-68-portfolio-local-launcher-design.md`

## Global Constraints

- Keep `config/atlas/dio_meta_incarnation_crosswalk.csv` byte-for-byte unchanged and exactly 53 data rows.
- Accept exactly 15 unique extensions only when all existing ProductGrade, proof, commercial, authority, and external-effect predicates pass.
- Derive exactly 68 current canonical incarnations; never encode 68 by editing the historical CSV.
- Missing or invalid extension evidence must visibly fall back to 53 with `extension_summary_state` explaining why.
- Do not claim commercial validation, willingness to pay, revenue, legal authority, or external-release authority.
- All commits target `agent/dio-control-deck-68-productgrade`; resolve its dirty merge state separately after tests pass.

---

### Task 1: Freeze the real 15-extension evidence input

**Files:**
- Create: `state/product_grade/canon_extensions/CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json`
- Test: `tests/test_canon_extension_summary_persistence.py`
- Source: `scripts/run_canon_extension_product_grade.py`

**Interfaces:**
- Consumes: `run_canon_extension_product_grade_gauntlet(root: Path, studio_product_grade_receipt: dict) -> dict`
- Produces: a committed receipt accepted by `summary_is_publishable(receipt: dict[str, Any]) -> bool`

- [ ] **Step 1: Add a failing repository-receipt test**

Add:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_RECEIPT = ROOT / "state/product_grade/canon_extensions/CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json"

def test_committed_canon_extension_summary_is_publishable():
    assert CANONICAL_RECEIPT.is_file()
    receipt = json.loads(CANONICAL_RECEIPT.read_text(encoding="utf-8"))
    assert summary_is_publishable(receipt) is True
    assert receipt["extension_count"] == 15
    assert len(receipt["extensions"]) == 15
```

- [ ] **Step 2: Run the test and verify the real missing-input failure**

Run:

```bash
PYTHONNOUSERSITE=1 python -m pytest -q   tests/test_canon_extension_summary_persistence.py::test_committed_canon_extension_summary_is_publishable
```

Expected: FAIL because `CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json` is absent.

- [ ] **Step 3: Generate the receipt from the existing gauntlet**

Run the established generator with its proof requirements:

```bash
PYTHONNOUSERSITE=1 python scripts/run_canon_extension_product_grade.py   --require-all   --require-proof   > /tmp/dio-canon-extension-productgrade.log
```

Expected log markers:

```text
DIO_CANON_EXTENSION_PROOF_VERIFIED
DIO_CANON_EXTENSION_PRODUCT_GRADE_VERIFIED
DIO_CANON_EXTENSION_CONTROL_DECK_SUMMARY_WRITTEN:
```

Do not hand-author or repair a failing receipt. If the command does not emit all three markers, stop and investigate the gauntlet failure.

- [ ] **Step 4: Verify the generated evidence boundary**

Run:

```bash
PYTHONNOUSERSITE=1 python - <<'PY'
import json
from pathlib import Path
from products.canon_extension_summary import summary_is_publishable

path = Path("state/product_grade/canon_extensions/CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json")
receipt = json.loads(path.read_text(encoding="utf-8"))
assert summary_is_publishable(receipt)
assert receipt["extension_count"] == 15
assert receipt["product_grade_verified_count"] == 15
assert receipt["canon_extension_proof_verified_count"] == 15
assert receipt["commercial_validation"] == "UNPROVED"
assert receipt["authority_created"] is False
assert receipt["external_effects"] is False
assert len({row["canon_id"] for row in receipt["extensions"].values()}) == 15
assert len({row.get("slug", key) for key, row in receipt["extensions"].items()}) == 15
print("DIO_CANON_EXTENSION_FROZEN_SUMMARY_VALID")
PY
```

Expected: `DIO_CANON_EXTENSION_FROZEN_SUMMARY_VALID`.

- [ ] **Step 5: Run the persistence tests**

Run:

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_canon_extension_summary_persistence.py
```

Expected: PASS.

- [ ] **Step 6: Commit the frozen receipt and test**

```bash
git add   state/product_grade/canon_extensions/CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json   tests/test_canon_extension_summary_persistence.py
git commit -m "fix: freeze verified canon extension portfolio input"
```

### Task 2: Verify the real 53-plus-15 derivation

**Files:**
- Modify: `tests/test_portfolio_runtime_canon_extensions.py`
- Read: `portfolio_runtime.py`
- Read without modifying: `config/atlas/dio_meta_incarnation_crosswalk.csv`

**Interfaces:**
- Consumes: `portfolio_runtime.import_portfolio(force: bool = False) -> dict[str, Any]`
- Produces: repository-level acceptance coverage for the exact 53/15/68 invariant

- [ ] **Step 1: Add a failing real-source integration test**

Add:

```python
def test_repository_sources_derive_verified_68_product_truth():
    portfolio = portfolio_runtime.import_portfolio(force=True)

    assert portfolio["schema"] == "dio.meta_portfolio.atlas_import.v3"
    assert portfolio["base_canonical_incarnation_count"] == 53
    assert portfolio["canon_extension_count"] == 15
    assert portfolio["canonical_incarnation_count"] == 68
    assert len(portfolio["incarnations"]) == 68
    assert portfolio["extension_summary_state"] == "VERIFIED"
    assert portfolio["candidate_incarnations_imported"] == 0
    assert len([
        row for row in portfolio["incarnations"]
        if row.get("portfolio_identity") == "canon_extension"
    ]) == 15
```

- [ ] **Step 2: Run the test**

Run:

```bash
PYTHONNOUSERSITE=1 python -m pytest -q   tests/test_portfolio_runtime_canon_extensions.py::test_repository_sources_derive_verified_68_product_truth
```

Expected: PASS only after Task 1’s real receipt exists. If it fails, inspect `extension_summary_state` before changing code.

- [ ] **Step 3: Add an immutable-anchor assertion**

Add imports `hashlib` and this test:

```python
def test_historical_crosswalk_remains_the_53_row_anchor():
    crosswalk = portfolio_runtime.CROSSWALK
    before_sha = hashlib.sha256(crosswalk.read_bytes()).hexdigest()
    with crosswalk.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    portfolio_runtime.import_portfolio(force=True)
    after_sha = hashlib.sha256(crosswalk.read_bytes()).hexdigest()

    assert len(rows) == 53
    assert after_sha == before_sha
```

- [ ] **Step 4: Run all portfolio-runtime tests**

Run:

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_portfolio_runtime_canon_extensions.py
```

Expected: PASS, including verified 68, unverified 53 fallback, cache invalidation, and immutable anchor.

- [ ] **Step 5: Commit repository-level derivation coverage**

```bash
git add tests/test_portfolio_runtime_canon_extensions.py
git commit -m "test: verify repository derives 68-product truth"
```

### Task 3: Correct stale Production Studio expectations

**Files:**
- Modify: `tests/test_operator_production_studio.py`
- Read: `operator_production.py`
- Read: `scripts/serve_business_workbench.py`

**Interfaces:**
- Consumes: current repository portfolio returned by `portfolio_runtime.import_portfolio(force=True)`
- Produces: tests that distinguish current verified truth from explicit fallback behavior

- [ ] **Step 1: Change the current-state test to assert component truth**

Replace the hard-coded 53 assertions in `test_canonical_portfolio_self_hydrates_without_promoting_atlas_candidates` with:

```python
assert receipt["base_canonical_incarnation_count"] == 53
assert receipt["canon_extension_count"] == 15
assert receipt["canonical_incarnation_count"] == 68
assert len(receipt["incarnations"]) == 68
assert receipt["extension_summary_state"] == "VERIFIED"
assert receipt["candidate_incarnations_imported"] == 0
assert sum(row["portfolio_identity"] == "canonical_incarnation" for row in receipt["incarnations"]) == 53
assert sum(row["portfolio_identity"] == "canon_extension" for row in receipt["incarnations"]) == 15
```

- [ ] **Step 2: Change Production Studio’s live portfolio count expectation**

Replace:

```python
assert state["portfolio"]["count"] == 53
```

with:

```python
assert state["portfolio"]["count"] == 68
assert state["portfolio"]["candidate_incarnations_imported"] == 0
```

- [ ] **Step 3: Run the focused tests**

Run:

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_operator_production_studio.py
```

Expected: PASS. Do not change fallback tests in `tests/test_portfolio_runtime_canon_extensions.py`.

- [ ] **Step 4: Commit corrected consumer expectations**

```bash
git add tests/test_operator_production_studio.py
git commit -m "test: align production studio with verified 68 portfolio"
```

### Task 4: Expose component truth to all live consumers

**Files:**
- Modify: `scripts/serve_business_workbench.py`
- Modify: `scripts/serve_market_command_ms10.py`
- Modify: `scripts/build_operator_dashboard.py`
- Modify: `tests/test_operator_production_studio.py`
- Modify: `tests/test_market_command.py`

**Interfaces:**
- Consumes: portfolio v3 fields from `import_portfolio()` and `load_portfolio()`
- Produces: health/state payload fields `base_canonical_incarnations`, `canon_extensions`, `canonical_incarnations`, and `extension_summary_state`

- [ ] **Step 1: Add failing Business Workbench source assertions**

In `test_business_deployment_uses_production_workbench_and_market_auto_imports`, assert:

```python
for marker in (
    '"base_canonical_incarnations": portfolio.get("base_canonical_incarnation_count", 0)',
    '"canon_extensions": portfolio.get("canon_extension_count", 0)',
    '"extension_summary_state": portfolio.get("extension_summary_state", "MISSING")',
):
    assert marker in business
```

- [ ] **Step 2: Add component fields to `/api/business/health`**

In `scripts/serve_business_workbench.py`, extend the existing health dictionary:

```python
"base_canonical_incarnations": portfolio.get("base_canonical_incarnation_count", 0),
"canon_extensions": portfolio.get("canon_extension_count", 0),
"canonical_incarnations": portfolio.get("canonical_incarnation_count", 0),
"extension_summary_state": portfolio.get("extension_summary_state", "MISSING"),
"portfolio_truth_verified": (
    portfolio.get("base_canonical_incarnation_count") == 53
    and portfolio.get("canon_extension_count") == 15
    and portfolio.get("canonical_incarnation_count") == 68
    and portfolio.get("extension_summary_state") == "VERIFIED"
),
```

- [ ] **Step 3: Preserve extension identity in Market Command choices**

Change `scripts/serve_market_command_ms10.py` from the hard-coded identity to:

```python
"portfolio_identity": row.get("portfolio_identity") or "canonical_incarnation",
```

and add to its returned payload:

```python
"base_canonical_incarnation_count": registry.get("base_canonical_incarnation_count", 0),
"canon_extension_count": registry.get("canon_extension_count", 0),
"canonical_incarnation_count": registry.get("canonical_incarnation_count", len(products)),
"extension_summary_state": registry.get("extension_summary_state", "MISSING"),
```

- [ ] **Step 4: Add focused Market Command assertions**

Add to the existing source/portfolio test in `tests/test_market_command.py`, or create:

```python
def test_market_command_preserves_derived_portfolio_truth():
    source = (ROOT / "scripts/serve_market_command_ms10.py").read_text(encoding="utf-8")
    assert '"portfolio_identity": row.get("portfolio_identity")' in source
    assert '"base_canonical_incarnation_count": registry.get(' in source
    assert '"canon_extension_count": registry.get(' in source
    assert '"extension_summary_state": registry.get(' in source
```

- [ ] **Step 5: Ensure dashboard portfolio summary forwards v3 fields**

In `collect_product_portfolio()`, preserve these registry keys in its `summary`:

```python
"base_canonical_incarnation_count": registry.get("base_canonical_incarnation_count", 0),
"canon_extension_count": registry.get("canon_extension_count", 0),
"canonical_incarnation_count": registry.get("canonical_incarnation_count", len(registry.get("incarnations", []))),
"extension_summary_state": registry.get("extension_summary_state", "MISSING"),
```

- [ ] **Step 6: Run consumer tests**

Run:

```bash
PYTHONNOUSERSITE=1 python -m pytest -q   tests/test_operator_production_studio.py   tests/test_market_command.py
```

Expected: PASS.

- [ ] **Step 7: Commit consumer truth propagation**

```bash
git add   scripts/serve_business_workbench.py   scripts/serve_market_command_ms10.py   scripts/build_operator_dashboard.py   tests/test_operator_production_studio.py   tests/test_market_command.py
git commit -m "feat: expose 68-product component truth"
```

### Task 5: Make CI validate deployable portfolio truth

**Files:**
- Modify: `.github/workflows/dio-canon-extension-productgrade.yml`

**Interfaces:**
- Consumes: the committed frozen receipt and repository-source integration tests
- Produces: a CI gate that cannot pass when the deployable branch would display 53

- [ ] **Step 1: Add the real consumer tests to the workflow**

Extend the pytest command with:

```yaml
tests/test_operator_production_studio.py
tests/test_market_command.py
```

The existing workflow must retain:

```yaml
tests/test_portfolio_runtime_canon_extensions.py
tests/test_canon_extension_summary_persistence.py
```

- [ ] **Step 2: Run the exact workflow test set locally**

Run the pytest list from the workflow verbatim with `PYTHONNOUSERSITE=1 python -m pytest -q`.

Expected: PASS and no source file mutation.

- [ ] **Step 3: Confirm the historical anchor is unmodified**

Run:

```bash
git diff --exit-code -- config/atlas/dio_meta_incarnation_crosswalk.csv
```

Expected: exit 0 with no output.

- [ ] **Step 4: Commit the CI truth gate**

```bash
git add .github/workflows/dio-canon-extension-productgrade.yml
git commit -m "ci: gate deployable 68-product portfolio truth"
```

### Task 6: Resolve branch integration and validate the live checkout

**Files:**
- Resolve only files reported by Git as conflicted
- Do not modify: `config/atlas/dio_meta_incarnation_crosswalk.csv`

**Interfaces:**
- Consumes: tested PR #36 branch and its base branch history
- Produces: mergeable PR state and a Debian checkout whose APIs agree on 68

- [ ] **Step 1: Fetch and inspect divergence**

```bash
git fetch origin
git status --short
git log --oneline --decorate --graph --max-count=30   origin/agent/dio-canon-extension-productgrade-gauntlet   origin/agent/dio-control-deck-68-productgrade
```

Expected: the current PR ancestry and no unexplained local edits.

- [ ] **Step 2: Merge the PR base into its head without force**

```bash
git switch agent/dio-control-deck-68-productgrade
git merge --no-ff origin/agent/dio-canon-extension-productgrade-gauntlet
```

Resolve conflicts by preserving the v3 dual-source derivation and both new test sets. Never resolve by adding extension rows to the crosswalk.

- [ ] **Step 3: Run the focused acceptance suite**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q   tests/test_canon_extension_summary_persistence.py   tests/test_portfolio_runtime_canon_extensions.py   tests/test_operator_production_studio.py   tests/test_market_command.py
```

Expected: PASS.

- [ ] **Step 4: Restart the two current portfolio-consuming services**

```bash
systemctl --user restart dio-control-deck.service dio-market-command.service
systemctl --user --no-pager --full status dio-control-deck.service dio-market-command.service
```

Expected: both active.

- [ ] **Step 5: Verify Business Workbench live truth**

```bash
curl -fsS http://127.0.0.1:8765/api/business/health | python -m json.tool
curl -fsS http://127.0.0.1:8765/api/business/portfolio | python -m json.tool
```

Expected health fields: base 53, extensions 15, total 68, `VERIFIED`, and `portfolio_truth_verified: true`.

- [ ] **Step 6: Verify Market Command live truth**

```bash
curl -fsS http://127.0.0.1:8770/api/market/products | python -m json.tool
```

Expected: count 68 with 15 rows retaining `portfolio_identity: canon_extension`.

- [ ] **Step 7: Push normally and confirm PR checks**

```bash
git push origin agent/dio-control-deck-68-productgrade
```

Expected: non-force push succeeds; PR #36 becomes mergeable after required checks complete.
