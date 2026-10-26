# Evidex Shared Finishing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a review-safe DIO finishing step that routes each successful Evidex pack through Format Core and Production Studio while preserving NicheFoundry as an approved optional brand-material route.

**Architecture:** Keep the embedded Evidex custody engine unchanged and add a focused DIO product-layer finisher. The finisher reads sealed pack metadata, builds typed semantic content, invokes Format Core in review mode, writes a normalized Production Studio receipt, and atomically rebuilds the existing ZIP. The outer Evidex runner invokes this step only after engine success and treats finishing failure as job failure.

**Tech Stack:** Python 3.12, Format Core semantic renderer, `python-docx`, HTML, JSON, `zipfile`, pytest/unittest.

**Spec:** `docs/superpowers/specs/2026-10-27-evidex-shared-finishing-design.md`

## Global Constraints

- Evidex remains the authority for evidence ingestion, claim state, source custody, and human review gates.
- Format Core uses `dio_professional`, `editable_review`, English, and `release_mode=False`.
- Shared finishing must not alter `SOURCE_REVIEW.json`, source copies, or existing customer artifacts.
- External delivery, publication, spend, and authority remain refused or false.
- NicheFoundry executes only when an approved brand-material request is present; this slice records the route as available and unexecuted.
- The archive replacement is atomic and contains only regular files under the pack directory.

## Review Focus

- A pack with `release_authorized=false` must remain visibly held in the formatted review surface and normalized receipt; Task 1 pins this.
- Missing or malformed `SOURCE_REVIEW.json` must fail before any review artifact is presented as complete; Task 1 pins this.
- A claim with `UNVERIFIED` state must appear as `UNVERIFIED` after formatting; Task 1 pins this.
- A formatting failure must produce a failed outer job receipt and preserve the generated pack directory; Task 2 pins this.
- Rebuilt ZIP contents must use safe relative names and include the normalized receipt exactly once; Task 2 pins this.

---

### Task 1: Format Core and Production Studio finisher

**Files:**
- Create: `products/evidex_studio_finish.py`
- Create: `tests/test_evidex_studio_finish.py`

**Interfaces:**
- Consumes: `adapters.format_core.renderer.build_paragraph_semantic_content`, `adapters.format_core.renderer.render_semantic_asset`, an Evidex pack directory, and the original intake mapping.
- Produces: `finish_evidex_pack(*, pack_dir: Path, intake: dict[str, Any], source_root: Path) -> dict[str, Any]`; writes `05_STUDIO_FINISH/FORMAT_CORE/*` and `05_STUDIO_FINISH/EVIDEX_STUDIO_FINISH_RECEIPT.json`.

- [x] **Step 1: Write failing tests for a held pack and invalid review metadata**

  Add `test_finish_preserves_human_gate_and_unverified_claims` and `test_finish_refuses_missing_or_malformed_source_review`. Assert the rendered HTML and receipt retain `UNVERIFIED`, `human_review_required=true`, and `release_authorized=false`; invalid metadata raises `EvidexStudioFinishError`.

- [x] **Step 2: Run the Task 1 tests and verify they fail**

  Run: `/workspace/.dio-venv/bin/python -m pytest -q tests/test_evidex_studio_finish.py`
  Expected: FAIL because `products.evidex_studio_finish` does not exist.

- [x] **Step 3: Implement the focused finisher**

  Define `EvidexStudioFinishError`, `build_evidex_semantic_content(*, pack_dir: Path, intake: dict[str, Any]) -> dict[str, Any]`, and `finish_evidex_pack(*, pack_dir: Path, intake: dict[str, Any], source_root: Path) -> dict[str, Any]`. Render DOCX and HTML review candidates, require Format Core QA to pass, hash outputs, and write the normalized receipt with every external authority false or refused and NicheFoundry marked available but unexecuted.

- [x] **Step 4: Run the Task 1 tests and verify they pass**

  Run: `/workspace/.dio-venv/bin/python -m pytest -q tests/test_evidex_studio_finish.py`
  Expected: PASS.

- [x] **Step 5: Commit Task 1**

  ```bash
  git add products/evidex_studio_finish.py tests/test_evidex_studio_finish.py
  git commit -m "feat: finish Evidex packs through Format Core"
  ```

### Task 2: Runner integration and atomic archive rebuild

**Files:**
- Modify: `products/evidex_studio_finish.py`
- Modify: `scripts/run_evidex_jobs.py`
- Modify: `tests/test_evidex_studio_finish.py`
- Modify: `tests/test_evidex_canonical_binding.py`

**Interfaces:**
- Consumes: Task 1's `finish_evidex_pack(...)` and the engine's final stdout line containing the generated ZIP path.
- Produces: `finish_evidex_archive(*, archive_path: Path, intake: dict[str, Any], source_root: Path) -> dict[str, Any]`; the outer run receipt gains `studio_finish`, and `returncode` becomes nonzero when finishing fails.

- [x] **Step 1: Write failing archive and runner tests**

  Add `test_archive_finish_reseals_relative_regular_files_once`, `test_runner_records_successful_studio_finish`, and `test_runner_fails_when_studio_finish_fails_without_removing_pack`. Assert the ZIP includes `05_STUDIO_FINISH/EVIDEX_STUDIO_FINISH_RECEIPT.json` once, contains no absolute or parent-traversal members, and failed finishing is recorded without deleting the pack directory.

- [x] **Step 2: Run the Task 2 tests and verify they fail**

  Run: `/workspace/.dio-venv/bin/python -m pytest -q tests/test_evidex_studio_finish.py tests/test_evidex_canonical_binding.py`
  Expected: FAIL because archive finalization and runner integration are absent.

- [x] **Step 3: Implement atomic archive finishing**

  Add `finish_evidex_archive(...)` using a sibling temporary ZIP and `Path.replace`. Reject a missing archive, missing sibling pack directory, symlinks, and files outside the pack directory. Update `run_evidex(...)` to parse the final stdout line, invoke the finisher after an engine return code of zero, and persist the normalized result or error in `EVIDEX_RUN_RECEIPT.json`.

- [x] **Step 4: Run the Task 2 tests and verify they pass**

  Run: `/workspace/.dio-venv/bin/python -m pytest -q tests/test_evidex_studio_finish.py tests/test_evidex_canonical_binding.py`
  Expected: PASS.

- [x] **Step 5: Commit Task 2**

  ```bash
  git add products/evidex_studio_finish.py scripts/run_evidex_jobs.py tests/test_evidex_studio_finish.py tests/test_evidex_canonical_binding.py
  git commit -m "feat: reseal Evidex archives with Studio finish"
  ```

### Task 3: Product documentation and release-slice verification

**Files:**
- Modify: `adapters/evidex/README.md`
- Modify: `docs/superpowers/plans/2026-10-27-evidex-shared-finishing.md`

**Interfaces:**
- Consumes: Tasks 1 and 2's runner behavior and receipt schema.
- Produces: operator documentation for the shared finishing path and recorded verification evidence in this plan.

- [x] **Step 1: Update the Evidex adapter documentation**

  Document the engine/Format Core/Production Studio/NicheFoundry responsibility boundary, output locations, human gate, and failure behavior.

- [x] **Step 2: Run the focused product suites**

  Run: `/workspace/.dio-venv/bin/python -m pytest -q tests/test_evidex_studio_finish.py tests/test_evidex_canonical_binding.py tests/test_evidex_quality_consumption.py tests/test_integrated_repair_regressions.py`
  Expected: PASS.

- [x] **Step 3: Run static integrity checks**

  Run: `git diff --check && /workspace/.dio-venv/bin/python -m compileall -q products/evidex_studio_finish.py scripts/run_evidex_jobs.py cross_folder_variants/Evidex/A_CODE/src/evidence_pack_engine`
  Expected: exit code 0.

- [x] **Step 4: Record the exact checks and known suite limitation**

  Check the completed plan boxes and append the commands and outcomes. Record that the unrelated full top-level suite currently stops during collection because `tests/test_multichannel_campaign_factory.py` imports missing `build_campaign_story`.

- [x] **Step 5: Commit Task 3**

  ```bash
  git add adapters/evidex/README.md docs/superpowers/plans/2026-10-27-evidex-shared-finishing.md
  git commit -m "docs: describe Evidex shared finishing boundary"
  ```

## Verification record

- RED: Task 1 produced five expected `ModuleNotFoundError` failures before `products.evidex_studio_finish` existed.
- GREEN: Task 1 produced `5 passed` in 0.21 seconds.
- RED: Task 2 produced four expected failures for the missing archive finisher and runner receipt integration.
- GREEN: Task 2 and canonical binding produced `18 passed` in 0.46 seconds.
- Regression RED→GREEN: the existing standalone entrypoint test exposed an eager `products` import; the lazy boundary fix produced `22 passed` across that contract and Tasks 1–2.
- Focused release slice after final-review fixes: `51 passed` in 7.17 seconds across Studio finishing, canonical binding, Evidex quality consumption, and integrated repair regressions.
- Static checks: `git diff --check` and `compileall` exited 0.
- Final review fixes: canonical `kpi_name`/`declared_target`/`declared_actual` fields now reach the customer review; malformed claim records fail before rendering; Format Core's receipt is included in the hashed artifact inventory; and the engine reports its exact pack root for unambiguous finishing.
- Known repository limitation: bare top-level test collection stops at `tests/test_multichannel_campaign_factory.py` because `scripts.build_multichannel_campaign_factory` no longer exports `build_campaign_story`. This predates and is outside the Evidex finishing slice.
