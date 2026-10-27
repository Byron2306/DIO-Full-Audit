# DIO Slice 2 Commercial Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the governed Vesper commercial spine onto the verified Slice 1 cloud branch without importing obsolete branch history.

**Architecture:** Preserve the existing Presence Core as the conversational front door and add one canonical customer-case lineage consumed by Needs You, pricing recommendations, invoice/payment projections, Outlook reconciliation, operator summaries, and later Control Deck mobile views. Deterministic DIO state owns commercial truth and authority; Vesper/Qwen may explain but never manufacture actions, payment, delivery, or scope authority.

**Tech Stack:** Python 3.11+, pytest, JSON state/receipts, Presence Core, existing Control Deck/Market Command runtimes.

**Spec:** `docs/superpowers/specs/2026-09-09-vesper-commercial-spine-mobile-operator-design.md` from the commercial-spine proof branch; this Slice 2 branch transplants only the commercial components onto `agent/dio-control-deck-68-productgrade`.

## Global Constraints

- Start from verified Slice 1 head; do not merge the historical Vesper branch wholesale.
- Customer-case stages are monotonic and evidence-bound.
- Pricing output is recommendation truth, never invoice or payment authority.
- Public conversation state never exposes private invoice/payment data.
- Outlook reconciliation consumes normalized messages and creates no raw send authority.
- Browser-return success is never payment proof.
- Needs You is the shared human decision queue and does not itself create authority.
- Slice 3 investor class and Slice 4 global pricing remain future integrations; Slice 2 only provides their commercial spine interfaces.
- Production Studio rendering carry-forward remains issue #52 and does not block Slice 2.

---

### Task 1: Canonical customer-case state

**Files:**
- Create: `presence_core/customer_cases.py`
- Create: `tests/test_vesper_customer_cases.py`

**Interfaces:**
- `create_or_attach_case(state_root: Path, *, conversation_id: str, channel: str, external_user_id: str, product_id: str | None = None, contact_email: str | None = None) -> dict[str, Any]`
- `load_case(state_root: Path, case_id: str) -> dict[str, Any] | None`
- `list_cases(state_root: Path, limit: int = 100) -> list[dict[str, Any]]`
- `update_case(state_root: Path, case: dict[str, Any], *, stage: str | None = None, patch: dict[str, Any] | None = None, evidence_ref: str | None = None) -> dict[str, Any]`
- `find_case_for_conversation(state_root: Path, conversation_id: str) -> dict[str, Any] | None`

- [ ] Write tests proving same-conversation reuse, canonical commercial defaults, monotonic stage history, and most-recent-first listing.
- [ ] Run `PYTHONNOUSERSITE=1 python -m pytest -q tests/test_vesper_customer_cases.py` and verify RED because `presence_core.customer_cases` is absent.
- [ ] Implement JSON-backed customer-case storage under `<state_root>/customer_cases/` with stable IDs and evidence-bound stage history.
- [ ] Re-run the focused test and verify GREEN.
- [ ] Commit the task independently.

### Task 2: Commercial pricing and 68-product registry projection

**Files:**
- Create: `presence_core/commercial_pricing.py`
- Create: `products/commercial_pricing_registry.py`
- Create: `tests/test_vesper_commercial_pricing.py`
- Create: `tests/test_vesper_commercial_pricing_registry.py`

**Interfaces:**
- `recommend_quote(...) -> dict[str, Any]` returns `known_band`, `scope_sensitive`, or `needs_operator`.
- Registry rows cover exactly the canonical 68 products and distinguish governed reference bands from `UNPROVED` commercial validation.

- [ ] Write RED tests for governed offer bands, out-of-envelope escalation, and exactly 68 registry rows.
- [ ] Run both pricing test files and confirm RED.
- [ ] Transplant/adapt deterministic pricing logic from PR #43 without importing obsolete Vesper history.
- [ ] Run pricing tests and existing portfolio truth tests; verify GREEN.
- [ ] Commit independently.

### Task 3: Commercial Needs You and case projection

**Files:**
- Create: `presence_core/commercial_cases.py`
- Modify: `presence_core/state.py`
- Create: `tests/test_vesper_commercial_needs_you.py`

**Interfaces:**
- `ensure_commercial_needs_you(...) -> dict[str, Any]`
- `apply_quote_recommendation(...) -> dict[str, Any]`
- Supported reasons: `scope_approval_required`, `quote_approval_required`, `invoice_send_approval`, `attachment_review`, `release_approval`.

- [ ] Write RED tests proving deduplicated Needs You items and no invoice/work authority from a recommendation.
- [ ] Run focused tests and confirm RED.
- [ ] Implement the minimal projection and stage-safe updates.
- [ ] Run focused tests plus `tests/test_presence_engine.py`; verify GREEN.
- [ ] Commit independently.

### Task 4: Evidex invoice/payment bridge and Outlook reconciliation

**Files:**
- Create: `presence_core/commercial_evidex.py`
- Create: `presence_core/outlook_cases.py`
- Create: `tests/test_vesper_evidex_invoice_bridge.py`
- Create: `tests/test_vesper_outlook_case_reconciliation.py`

**Interfaces:**
- `project_evidex_commercial_state(job_root: Path) -> dict[str, Any]`
- `apply_commercial_projection(...) -> dict[str, Any]`
- `reconcile_outlook_message(state_root: Path, message: dict[str, Any]) -> dict[str, Any]`

- [ ] Write RED tests proving `PAID.txt` alone is not verified payment and a web-started customer replying by email remains one case.
- [ ] Run both test files and confirm RED.
- [ ] Implement conservative invoice/payment projection and normalized Outlook case matching.
- [ ] Re-run focused tests and verify GREEN.
- [ ] Commit independently.

### Task 5: Operator case views and Vesper truth separation

**Files:**
- Create: `presence_core/operator_views.py`
- Modify: `presence_core/engine.py`
- Modify: `presence_core/llm.py`
- Create: `tests/test_vesper_operator_case_views.py`
- Create: `tests/test_vesper_operator_truth.py`
- Create: `tests/test_vesper_commercial_transcript_gauntlet.py`

**Interfaces:**
- Operator summary exposes Needs You, cases, quote/invoice/payment state, and next governed action.
- Public and operator drafting roles remain distinct.
- Unsupported action-state language is rejected when governing facts do not prove the action.

- [ ] Write RED operator/public role and transcript tests, including quarantined-upload and unsupported processing claims.
- [ ] Run focused tests and confirm RED.
- [ ] Adapt role-aware drafting and action-state guard to the current Slice 1 Presence Core implementation.
- [ ] Run focused tests plus existing Presence tests; verify GREEN.
- [ ] Commit independently.

### Task 6: Read APIs, Control Deck commercial projection, and Slice 2 acceptance

**Files:**
- Modify: `scripts/serve_presence_bridge.py`
- Modify: `scripts/serve_business_workbench.py`
- Create or modify: `dashboard/commercial_slice2.js`
- Create: `tests/test_slice2_commercial_spine_contracts.py`
- Create: `.github/workflows/dio-slice2-commercial-spine.yml`

**Interfaces:**
- Read-only APIs expose operator summary, case list, case detail, Needs You, and governed commercial pricing projection.
- Control Deck presents `Customer | Product | Value | Stage | Needs You` and drill-down links without a second CRM.

- [ ] Write RED contract tests for API routes, mobile commercial projection, 68-product registry linkage, and no browser-side authority secrets.
- [ ] Run Slice 2 workflow and confirm RED.
- [ ] Implement minimal read APIs and Control Deck projection over canonical case state.
- [ ] Run Slice 2 tests plus Slice 1 cockpit contracts and Vesper commercial regression suite; verify GREEN.
- [ ] Deploy to the Droplet only after CI GREEN, then verify live case/Needs You/operator-summary hydration without creating external effects.
- [ ] Stamp `DIO_SLICE_2_COMMERCIAL_SPINE_LIVE_VERIFIED` only after live smoke passes.
