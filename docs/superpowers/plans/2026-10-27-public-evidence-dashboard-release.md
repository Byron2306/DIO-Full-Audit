# Public Evidence Dashboard and Website Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish verifiable professional evidence for all 68 offers, close public and operator UX gaps, and deploy one reproducible release to `dioworkflows.co.za`.

**Architecture:** Export a public-safe portfolio from the canonical offer/proof registries in DIO-Full-Audit, consume it deterministically in DIO-Workflows, and gate one Pages workflow on content, hash, accessibility, route, JavaScript, and responsive checks. Audit loopback dashboards separately and document the API ingress without exposing host secrets.

**Tech Stack:** Python 3.13, static HTML/CSS/JavaScript, pytest, Playwright, GitHub Pages/Actions, JSON receipts.

**Spec:** `docs/superpowers/specs/2026-10-27-production-convergence-design.md`

## Global Constraints

- DIO-Workflows `main` remains the Pages source and retains `CNAME=dioworkflows.co.za`.
- Public exports contain no operational paths, contacts, conversations, or secrets.
- Route-family proof is labelled separately from named-product customer proof.
- Operator dashboards remain loopback-only.
- Backend cutover stops if the redacted ingress manifest and host checks disagree; static release may proceed independently.
- Record the prior Pages commit before deployment.

## Review Focus

- A product without named proof must render an honest unproved state; Task 1 pins this.
- Long titles, missing media, and blocked embeds must remain usable; Task 3 pins this.
- 320–390 px layouts must not overflow or hide the primary CTA; Task 3 pins this.
- Redacted dashboard screenshots must not leak live customer data; Task 4 pins this.
- A Pages run that deploys before tests or from the wrong commit must fail contract checks; Task 5 pins this.

---

### Task 1: Canonical Public Evidence Export

**Files:**
- Create: `scripts/export_public_offer_evidence.py`
- Create: `config/public_evidence_export.schema.json`
- Create: `tests/test_public_offer_evidence_export.py`
- Generate: a versioned public export consumed by `/workspace/DIO-Workflows/products/launch-registry.json`

**Interfaces:**
- Produces: `export_public_offer_evidence(offer_contracts: Path, proof_registry: Path, output: Path) -> PublicEvidenceExportReceipt` for exactly 68 offers.

- [x] Write failing tests for count/unique IDs/routes, buyer job, bounded outcome, deliverable, acceptance criteria, route proof, named proof state, CTA, redaction, stable ordering, source commit, artifact ID, and SHA-256.
- [x] Implement deterministic export and reject unreachable proof references or downgrade them to an explicit unavailable state.
- [x] Run `pytest -q tests/test_public_offer_evidence_export.py tests/test_customer_journey_phase8.py`; expect PASS (14 tests).
- [x] Commit with `feat: export public evidence for 68 offers`.

### Task 2: Site Registry and Provenance Integration

**Files in `/workspace/DIO-Workflows`:**
- Modify: `products/launch-registry.json`
- Modify: `products/catalog.js`
- Modify: `products/app.js`
- Modify: `products/proven-routes.html`
- Modify: `tests/test_portfolio_68_and_films_contract.py`
- Create: `tests/test_public_evidence_provenance.py`

**Interfaces:**
- Consumes: the deterministic export and receipt from Task 1.
- Produces: public offer cards/pages with labelled engineering proof, customer artifact proof, and market validation.

- [ ] Write failing tests for all 68 routes, provenance fields, proof labels, missing/unreachable artifacts, CTA destinations, and absence of internal identifiers.
- [ ] Update registry/rendering and publish reachable proof snapshots or remove the dead reference.
- [ ] Run the focused portfolio/provenance tests; expect PASS.
- [ ] Commit in DIO-Workflows with `feat: publish professional offer evidence`.

### Task 3: Public Responsive and Accessibility Repairs

**Files in `/workspace/DIO-Workflows`:**
- Modify: `index.html`
- Modify: `assets/site.css`
- Modify: `assets/site.js`
- Modify: `products/index.html`
- Modify: `products/product.css`
- Modify: `products/catalog.js`
- Modify: `vesper-intake.html`
- Modify: `vesper-intake.js`
- Create: `tests/test_public_responsive_accessibility.py`
- Create: `scripts/check_legacy_product_urls.py`

**Files in DIO-Full-Audit:**
- Modify: `scripts/manage_product_workflow.py`
- Modify: `scripts/promote_lead_to_product_job.py`
- Modify: `scripts/manage_document_studio_commercial.py`
- Modify: `scripts/manage_vamp_commercial.py`
- Modify: `scripts/manage_sophia_commercial.py`

**Interfaces:**
- Produces: catalogue search, suite/proof filters, progressive disclosure, media fallback, and zero horizontal overflow at 390 px.

- [ ] Write failing DOM/Playwright tests for legacy `/sites/` URLs, Vesper overflow, obscured CTA, Products contrast, keyboard/focus, reduced motion, media fallback, filter behavior, and 320/390/768/1440 px layouts.
- [ ] Replace generated legacy URLs, repair Vesper/home mobile positioning, improve hero/header contrast, and add catalogue search/filters/progressive disclosure.
- [ ] Add poster/fallback links for blocked media and meaningful alternative text.
- [ ] Run all site pytest and Playwright checks; capture desktop and 390 px screenshots; expect PASS and no overflow.
- [ ] Commit in DIO-Workflows with `fix: close public journey and responsive gaps`.

### Task 4: Operator Dashboard Audit and Host Readiness

**Files in DIO-Full-Audit:**
- Create: `scripts/audit_operator_dashboards.py`
- Create: `scripts/verify_dio_host.py`
- Modify: dashboard cross-links and surfaces identified by the audit
- Create: `tests/test_operator_dashboard_readiness.py`
- Create: `docs/runbooks/dashboard-readiness.md`

**Interfaces:**
- Produces: redacted `dio.dashboard_audit.v1`, desktop/mobile screenshots, and `dio.host_readiness.v1` for Launcher, GoldenEye, Canonical Portfolio, Business, Production, Connections, Market, and Vesper API.

- [ ] Write failing tests for loopback binding, missing/stale links, state mount, pinned release, units, listeners, secret-presence metadata, public health, CORS, and foreign-origin refusal.
- [ ] Implement the auditor/verifier and repair confirmed navigation, status, and narrow-layout gaps without embedding implementation detail in operator flows.
- [ ] Run focused tests and capture redacted screenshots from actual local services; expect PASS or explicit `NEEDS_YOU` for unavailable host-only checks.
- [ ] Commit with `fix: close operator dashboard readiness gaps`.

### Task 5: Reproducible API Ingress Manifest

**Files:**
- Create: `deploy/api-ingress-manifest.example.json`
- Create: `scripts/verify_public_ingress.py`
- Create: `tests/test_public_ingress_manifest.py`
- Create: `docs/runbooks/public-api-ingress.md`

**Interfaces:**
- Produces: a redacted manifest covering DNS target class, tunnel/proxy service identity, upstream loopback port, health route, release commit, and rollback command.

- [ ] Write failing tests for missing fields, literal secrets, public upstreams, unexpected ports, commit mismatch, health mismatch, and redaction.
- [ ] Implement manifest verification and host/live comparison; return a backend-cutover hold on disagreement.
- [ ] Run `pytest -q tests/test_public_ingress_manifest.py`; expect PASS with fixtures.
- [ ] Commit with `ops: make public API ingress reproducible`.

### Task 6: Single Pages Workflow and Live Release

**Files in `/workspace/DIO-Workflows`:**
- Modify: `.github/workflows/pages.yml`
- Delete: `.github/workflows/static.yml`
- Create: `tests/test_pages_workflow_contract.py`
- Modify: `DEPLOYMENT.md`

**Interfaces:**
- Produces: one Pages workflow whose deploy job requires content, proof hash, route, JS, accessibility, responsive-overflow, and screenshot checks.

- [ ] Write a failing workflow-contract test for triggers, permissions, pinned actions, dependency graph, artifact source, custom domain, concurrency, and rollback metadata.
- [ ] Consolidate the workflows and document review-branch, merge, live verification, and prior-commit rollback.
- [ ] Run the entire DIO-Workflows suite locally; expect PASS.
- [ ] Push a review branch and inspect the exact diff and checks; merge to `main` only after required checks are green.
- [ ] Verify the deployed commit/checksum, core pages, all 68 routes, proof hashes, API/Presence health, session allow/refusal behavior, legacy URL absence, and desktop/390 px screenshots.
- [ ] If live verification fails, restore the recorded prior commit and rerun the single workflow; otherwise retain `dio.public_release_receipt.v1`.
