# Slice 1 Cockpit Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the existing 68-product cloud cockpit so artifact navigation, hydration truth, Production Studio readiness/errors, Atlas and the preserved prospect registry are usable and truthful.

**Architecture:** Keep the current localhost service topology. Reuse the existing governed artifact gateway, add read-only runtime/Atlas projections in the BUSINESS server, and patch served HTML at runtime rather than rewriting the large generated dashboard snapshots. No investor/commercial branch merge occurs in this slice.

**Tech Stack:** Python 3.13, `http.server`, HTML/JavaScript, existing DIO dashboard/state builders, pytest in CI.

**Spec:** `docs/superpowers/specs/2026-09-09-slice1-cockpit-repair-design.md`

## Global Constraints

- Preserve verified 53 + 15 = 68 portfolio truth and the historical 53-row anchor.
- Preserve existing Atlas/prospect state; no replacement registry.
- No external publication, spend, outreach or delivery authority.
- Cockpit services remain localhost-only.
- Old Debian/Arda remains `LEGACY_HOST_AUDIT_PENDING`.
- Never expose secret values in readiness APIs.

---

### Task 1: Cockpit projection helpers

**Files:**
- Create: `cockpit_runtime.py`
- Create: `tests/test_cockpit_runtime.py`

**Interfaces:**
- Produces: `runtime_readiness() -> dict`, `atlas_projection() -> dict`, `artifact_url(raw: str) -> str`, `patch_advanced_dashboard(page: str) -> str`.

- [ ] Write tests that require internal paths to become `/api/business/artifact?path=...`, external HTTP(S) links to remain unchanged, the advanced dashboard refresh catch to expose `LIVE_STATE_UNAVAILABLE`, and readiness to return state labels without secret values.
- [ ] Run focused tests and verify RED.
- [ ] Implement the smallest helper module satisfying those contracts.
- [ ] Run focused tests and verify GREEN.
- [ ] Commit.

### Task 2: BUSINESS routes and served advanced dashboard

**Files:**
- Modify: `scripts/serve_business_workbench.py`
- Test: `tests/test_business_workbench_slice1.py`

**Interfaces:**
- Consumes: Task 1 helpers.
- Produces: `GET /api/business/atlas`, readiness embedded in `GET /api/business/production/state`, and a patched `/dashboard/index.html` when served through port 8765.

- [ ] Write handler-level tests for Atlas projection, production readiness and advanced-dashboard patching.
- [ ] Run tests and verify RED.
- [ ] Add routes and page interception without changing localhost binding or authority.
- [ ] Run tests and verify GREEN.
- [ ] Commit.

### Task 3: Production Studio visible readiness and failure output

**Files:**
- Create: `dashboard/production_slice1.js`
- Modify: `scripts/serve_business_workbench.py`
- Test: `tests/test_production_studio_slice1.py`

**Interfaces:**
- Consumes: `runtime_readiness` from production state.
- Produces: visible runtime-readiness panel and persistent action-error text for marketing production failures.

- [ ] Write static-contract tests requiring readiness UI injection and marketing-error rendering.
- [ ] Run tests and verify RED.
- [ ] Add a small injected script that renders readiness and wraps the marketing submit path with visible failure state while retaining existing endpoint semantics.
- [ ] Run tests and verify GREEN.
- [ ] Commit.

### Task 4: Atlas + preserved prospects surface

**Files:**
- Create: `dashboard/atlas_slice1.js`
- Modify: `scripts/serve_business_workbench.py`
- Test: `tests/test_atlas_slice1_surface.py`

**Interfaces:**
- Consumes: `/api/business/atlas`.
- Produces: a read-only Business-page Atlas/Prospect panel showing Atlas asset status, registry counts, source lineage, outreach gate and legacy-host audit status.

- [ ] Write static/API contract tests requiring the panel and read-only lineage fields.
- [ ] Run tests and verify RED.
- [ ] Inject the panel into BUSINESS and fetch/render the projection.
- [ ] Run tests and verify GREEN.
- [ ] Commit.

### Task 5: Slice 1 verification

**Files:**
- Modify only if verification reveals a defect.

- [ ] Run all new Slice 1 tests.
- [ ] Run existing Control Deck/launcher/portfolio focused tests.
- [ ] Confirm no test or API mutates historical 53-row truth.
- [ ] Confirm localhost bindings and authority gates are unchanged.
- [ ] Inspect branch diff for accidental secret values, stale `/home/byron` additions, `file://` link generation, or autonomous external actions.
- [ ] Record exact green test commands and remaining known limitations, including missing edge-tts/Node and `LEGACY_HOST_AUDIT_PENDING`.
