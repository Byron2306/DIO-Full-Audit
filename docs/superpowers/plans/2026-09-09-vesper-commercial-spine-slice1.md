# Vesper Commercial Spine Slice 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the canonical customer-case backbone, role-correct operator/public conversation contracts, deterministic scope/pricing recommendation, Evidex invoice projection, Outlook reconciliation hooks, and shared Needs You/operator read APIs required before Control Deck mobile and public web launch.

**Architecture:** Presence remains the conversational front door, but commercially meaningful interactions attach to one durable customer case under persistent runtime state. Deterministic code owns scope, stage, pricing evidence, invoice/payment projections, and authority-required transitions; Qwen only explains those facts. Outlook, operator Telegram, Control Deck, and later web Vesper all consume the same case lineage.

**Tech Stack:** Python 3.11+, FastAPI, pytest, JSON state/receipts, existing Presence Core, LINGUA, Microsoft Graph/Outlook adapters, Evidex commercial artifacts.

**Spec:** `docs/superpowers/specs/2026-09-09-vesper-commercial-spine-mobile-operator-design.md`

## Global Constraints

- DIO determines truth and authority; Qwen only drafts presentation.
- Operator Telegram is private/operator-facing, not customer-facing.
- Public attachments remain quarantined until an authorised workflow receipt proves parsing/processing.
- Product marketing copy cannot expand a bounded pilot into production authority.
- Browser returns are never payment proof; verified provider evidence owns payment state.
- Outlook Smart Bot may draft but does not gain unrestricted send authority.
- Runtime state must be relocatable to persistent `/srv/dio/state` before production customer intake.
- No browser/client receives long-lived DIO signing secrets.
- Existing live Vesper branch must remain deployable while this feature branch is developed.

---

### Task 1: Canonical customer-case state model

**Files:**
- Create: `presence_core/customer_cases.py`
- Test: `tests/test_vesper_customer_cases.py`

**Interfaces:**
- Produces: `create_or_attach_case(state_root: Path, *, conversation_id: str, channel: str, external_user_id: str, product_id: str | None = None, contact_email: str | None = None) -> dict[str, Any]`
- Produces: `load_case(state_root: Path, case_id: str) -> dict[str, Any] | None`
- Produces: `list_cases(state_root: Path, limit: int = 100) -> list[dict[str, Any]]`
- Produces: `update_case(state_root: Path, case: dict[str, Any], *, stage: str | None = None, patch: dict[str, Any] | None = None, evidence_ref: str | None = None) -> dict[str, Any]`
- Produces: `find_case_for_conversation(state_root: Path, conversation_id: str) -> dict[str, Any] | None`

- [ ] **Step 1: Write failing tests for creation, attachment, persistence, and monotonic stage history**

```python
from pathlib import Path

from presence_core.customer_cases import (
    create_or_attach_case,
    find_case_for_conversation,
    load_case,
    update_case,
)


def test_customer_case_is_reused_for_same_conversation(tmp_path: Path):
    root = tmp_path / "presence"
    first = create_or_attach_case(
        root,
        conversation_id="CONV-1",
        channel="webchat",
        external_user_id="anon-1",
        product_id="dio_research_integrity",
    )
    second = create_or_attach_case(
        root,
        conversation_id="CONV-1",
        channel="email",
        external_user_id="person@example.com",
        contact_email="person@example.com",
    )
    assert second["case_id"] == first["case_id"]
    assert set(second["channel_origins"]) == {"webchat", "email"}
    assert second["contact_email"] == "person@example.com"
    assert find_case_for_conversation(root, "CONV-1")["case_id"] == first["case_id"]


def test_case_stage_history_is_evidence_bound_and_monotonic(tmp_path: Path):
    root = tmp_path / "presence"
    case = create_or_attach_case(root, conversation_id="CONV-2", channel="webchat", external_user_id="anon-2")
    case = update_case(root, case, stage="QUALIFIED", evidence_ref="EV-1")
    case = update_case(root, case, stage="SCOPE_ASSESSED", evidence_ref="EV-2")
    assert [row["stage"] for row in case["stage_history"]][-2:] == ["QUALIFIED", "SCOPE_ASSESSED"]
    assert load_case(root, case["case_id"])["stage"] == "SCOPE_ASSESSED"
```

- [ ] **Step 2: Run tests and verify RED because `presence_core.customer_cases` does not exist**

Run: `pytest -q tests/test_vesper_customer_cases.py`
Expected: FAIL during import with missing module/function.

- [ ] **Step 3: Implement minimal JSON-backed customer-case storage with stable IDs and stage ordering**

Implement state under `<state_root>/customer_cases/` with an index mapping conversation IDs to case IDs. Reject backwards transitions and record `stage_history` entries with timestamp/evidence reference. Initialise required fields from the spec including empty `scope`, `commercial`, `outlook`, `job_links`, and `needs_you_ids`.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `pytest -q tests/test_vesper_customer_cases.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add presence_core/customer_cases.py tests/test_vesper_customer_cases.py
git commit -m "feat: add canonical Vesper customer cases"
```

---

### Task 2: Operator/public conversation contract and action-state guard

**Files:**
- Modify: `presence_core/llm.py`
- Modify: `presence_core/engine.py`
- Test: `tests/test_vesper_operator_truth.py`
- Test: `tests/test_vesper_conversation_cortex.py`

**Interfaces:**
- `draft_with_cortex(..., governed_context=...)` receives role/audience context without granting authority.
- Add a deterministic `draft_claims_authorized(text: str, facts: str) -> bool` or equivalent guard that rejects unsupported action-state claims.

- [ ] **Step 1: Write failing regression tests reproducing the live operator/customer confusion and unsupported processing claim**

```python
def test_operator_prompt_is_not_customer_facing(monkeypatch):
    captured = {}
    # monkeypatch provider call to capture messages
    # invoke draft for governed_context={"role":"operator"}
    # assert system/user instruction contains owner/operator language and not "customer-facing reply"


def test_draft_guard_rejects_processing_claim_without_processing_fact():
    assert draft_claims_authorized(
        "I have received your file and will now process it.",
        "attachment=ATT-1; state=quarantined; attachment_processed=false",
    ) is False
```

Also add a transcript-level test asserting an operator asking about Sophia receives owner-facing wording and that a quarantined upload cannot become “processing”.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `pytest -q tests/test_vesper_operator_truth.py tests/test_vesper_conversation_cortex.py`
Expected: FAIL on current customer-facing prompt and unsupported action-state acceptance.

- [ ] **Step 3: Implement role-aware drafting and expanded claim guard**

System/user drafting instruction must branch by governed role:
- operator: concise owner-facing operational reply, no customer sales close;
- public: customer-facing reply.

Expand unsupported state claims to cover process/analyse/analyze/parse/open/start/queue/generate/invoice/charge/deliver/release/publish/submit/fulfil unless authoritative facts explicitly prove the relevant state/action.

Pass `role`, `audience`, and runtime provenance through governed descriptive context from `engine.py` without granting execution authority.

- [ ] **Step 4: Run tests and verify GREEN plus existing focused Vesper suite**

Run:
```bash
pytest -q tests/test_vesper_operator_truth.py tests/test_vesper_conversation_cortex.py tests/test_presence_engine.py tests/test_vesper_conversation_state.py tests/test_vesper_lingua_conversation.py tests/test_vesper_conversation_knowledge.py tests/test_vesper_conversation_crystals.py
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add presence_core/llm.py presence_core/engine.py tests/test_vesper_operator_truth.py tests/test_vesper_conversation_cortex.py
git commit -m "fix: separate Vesper operator truth from public sales copy"
```

---

### Task 3: Deterministic scope and pricing recommendation

**Files:**
- Create: `presence_core/commercial_pricing.py`
- Modify: `adapters/lingua/conversation_knowledge.py`
- Test: `tests/test_vesper_commercial_pricing.py`

**Interfaces:**
- Produces: `reference_offers(root: Path, product_id: str) -> list[dict[str, Any]]`
- Produces: `recommend_quote(root: Path, *, product_id: str, scope: dict[str, Any], historical_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]`
- Recommendation states: `known_band`, `scope_sensitive`, `needs_operator`.
- The public conversation knowledge projection may expose governed offer names/ranges but never payment state or private invoice history.

- [ ] **Step 1: Write failing tests for governed band extraction and out-of-envelope escalation**

```python
def test_evidex_tiny_pack_uses_governed_public_band(tmp_path):
    result = recommend_quote(tmp_path, product_id="evidex", scope={"file_count": 3, "complexity": "low"})
    assert result["mode"] in {"known_band", "scope_sensitive"}
    assert result["currency"] == "ZAR"
    assert result["min_amount"] == 350
    assert result["max_amount"] == 750
    assert result["authority_created"] is False


def test_research_integrity_full_article_requires_operator_when_public_offer_is_one_section(tmp_path):
    result = recommend_quote(tmp_path, product_id="dio_research_integrity", scope={"page_count": 20, "requested_depth": "full_document"})
    assert result["mode"] == "needs_operator"
    assert result["reason"] == "scope_exceeds_governed_offer"
```

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests/test_vesper_commercial_pricing.py`
Expected: FAIL because pricing module does not exist.

- [ ] **Step 3: Implement deterministic parser/recommender**

Parse ZAR ranges from governed `commercial_campaigns.json` offer prices. Use explicit scope rules only where evidence exists. Do not invent a numeric quote for products with no governed band or for scope that exceeds the advertised/proven envelope; return `needs_operator` with evidence references instead. Historical rows, when supplied, may be used only as structured numeric comparables.

- [ ] **Step 4: Run pricing and knowledge tests**

Run: `pytest -q tests/test_vesper_commercial_pricing.py tests/test_vesper_conversation_knowledge.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add presence_core/commercial_pricing.py adapters/lingua/conversation_knowledge.py tests/test_vesper_commercial_pricing.py tests/test_vesper_conversation_knowledge.py
git commit -m "feat: add governed commercial price recommendations"
```

---

### Task 4: Project Evidex invoice/payment truth into customer cases

**Files:**
- Create: `presence_core/commercial_evidex.py`
- Modify: `presence_core/customer_cases.py`
- Test: `tests/test_vesper_evidex_invoice_bridge.py`

**Interfaces:**
- Produces: `project_evidex_commercial_state(job_root: Path) -> dict[str, Any]`
- Produces: `apply_commercial_projection(state_root: Path, case_id: str, projection: dict[str, Any]) -> dict[str, Any]`

- [ ] **Step 1: Write failing tests for invoice draft/sent/payment projections**

```python
def test_evidex_invoice_artifacts_project_without_claiming_payment(tmp_path):
    job = tmp_path / "job"
    job.mkdir()
    (job / "INVOICE_ID.txt").write_text("INV-42")
    (job / "INVOICE.txt").write_text("Amount: R950")
    projection = project_evidex_commercial_state(job)
    assert projection["invoice_id"] == "INV-42"
    assert projection["invoice_state"] == "drafted"
    assert projection["payment_state"] == "unverified"


def test_paid_marker_requires_payment_receipt_for_verified_state(tmp_path):
    job = tmp_path / "job"
    job.mkdir()
    (job / "PAID.txt").write_text("paid")
    projection = project_evidex_commercial_state(job)
    assert projection["payment_state"] != "verified"
    (job / "PAYMENT_RECEIPT.txt").write_text("provider_event=verified")
    assert project_evidex_commercial_state(job)["payment_state"] == "verified"
```

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests/test_vesper_evidex_invoice_bridge.py`
Expected: FAIL because commercial bridge does not exist.

- [ ] **Step 3: Implement projection with conservative payment truth**

Map `INVOICE_ID.txt`, `INVOICE.txt`, `INVOICE_SENT.txt`, `PAID.txt`, and `PAYMENT_RECEIPT.txt` into deterministic commercial state. `PAID.txt` alone may indicate a legacy/controlled marker but must not become verified provider payment without qualifying receipt evidence.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `pytest -q tests/test_vesper_evidex_invoice_bridge.py tests/test_vesper_customer_cases.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add presence_core/commercial_evidex.py presence_core/customer_cases.py tests/test_vesper_evidex_invoice_bridge.py
git commit -m "feat: project Evidex invoice truth into customer cases"
```

---

### Task 5: Outlook case reconciliation and commercial Needs You

**Files:**
- Create: `presence_core/outlook_cases.py`
- Modify: `presence_core/state.py`
- Modify: `presence_core/engine.py`
- Test: `tests/test_vesper_outlook_case_reconciliation.py`
- Test: `tests/test_vesper_commercial_needs_you.py`

**Interfaces:**
- Produces: `reconcile_outlook_message(state_root: Path, message: dict[str, Any]) -> dict[str, Any]`
- Case matching priority: explicit case marker > conversation/thread binding > verified contact email > new candidate case.
- Needs You commercial reasons include `scope_approval_required`, `quote_approval_required`, `invoice_send_approval`, `attachment_review`, and `release_approval`.

- [ ] **Step 1: Write failing tests showing a web-started lead and email reply remain one case**

```python
def test_email_reply_attaches_to_existing_web_case(tmp_path):
    # create case with contact_email
    # reconcile Outlook message from same verified address
    # assert same case_id and channel_origins include webchat/email
```

Add a test that an out-of-envelope Research Integrity quote creates one Needs You item rather than falsely advancing invoice/work state.

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests/test_vesper_outlook_case_reconciliation.py tests/test_vesper_commercial_needs_you.py`
Expected: FAIL because reconciliation/commercial Needs You behavior is absent.

- [ ] **Step 3: Implement minimal reconciliation and Needs You projection**

Do not call Microsoft Graph from this module. It consumes normalized Outlook message records from the existing adapter. Persist message/thread IDs in the case Outlook section and create deterministic Needs You records for authority-required commercial decisions.

- [ ] **Step 4: Run focused tests plus presence engine tests**

Run: `pytest -q tests/test_vesper_outlook_case_reconciliation.py tests/test_vesper_commercial_needs_you.py tests/test_presence_engine.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add presence_core/outlook_cases.py presence_core/state.py presence_core/engine.py tests/test_vesper_outlook_case_reconciliation.py tests/test_vesper_commercial_needs_you.py
git commit -m "feat: reconcile Outlook intake with Vesper customer cases"
```

---

### Task 6: Shared operator read APIs and transcript acceptance gauntlet

**Files:**
- Modify: `scripts/serve_presence_bridge.py`
- Modify: `presence_core/state.py`
- Test: `tests/test_vesper_commercial_api.py`
- Test: `tests/test_vesper_research_integrity_transcript.py`
- Modify: `.github/workflows/vesper-conversational-presence-v2.yml`

**Interfaces:**
- Add localhost/operator-authorized read endpoints for:
  - `GET /api/presence/operator/cases`
  - `GET /api/presence/operator/cases/{case_id}`
  - `GET /api/presence/operator/commercial-summary`
- Responses are read-only and include `authority_created: false`.

- [ ] **Step 1: Write failing API and transcript tests**

The transcript test replays:

```text
What exactly is DIO?
Tell me about Sophia.
Especially the integrity offering. What do I send and how does payment work?
It is a 20-page academic article.
Can I send the whole thing?
[file upload]
How long will that take and will you send an invoice?
```

Assertions:
- operator answers are owner-facing;
- one-section offer is not silently promoted;
- attachment remains quarantined;
- no invented turnaround/account portal/billing team;
- quote/invoice state is grounded;
- Needs You receives scope/quote decision when required.

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests/test_vesper_commercial_api.py tests/test_vesper_research_integrity_transcript.py`
Expected: FAIL because APIs and complete transcript behavior do not yet exist.

- [ ] **Step 3: Implement minimal operator read endpoints and summary projection**

Reuse the existing operator token/auth boundary in the Presence bridge. Do not expose these endpoints publicly or alter the localhost bind rule. Extend CI focused suite with all new commercial tests.

- [ ] **Step 4: Run complete Slice 1 gauntlet**

Run:
```bash
pytest -q \
  tests/test_presence_engine.py \
  tests/test_vesper_conversation_state.py \
  tests/test_vesper_lingua_conversation.py \
  tests/test_vesper_conversation_knowledge.py \
  tests/test_vesper_conversation_crystals.py \
  tests/test_vesper_conversation_cortex.py \
  tests/test_vesper_customer_cases.py \
  tests/test_vesper_operator_truth.py \
  tests/test_vesper_commercial_pricing.py \
  tests/test_vesper_evidex_invoice_bridge.py \
  tests/test_vesper_outlook_case_reconciliation.py \
  tests/test_vesper_commercial_needs_you.py \
  tests/test_vesper_commercial_api.py \
  tests/test_vesper_research_integrity_transcript.py
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/serve_presence_bridge.py presence_core/state.py tests/test_vesper_commercial_api.py tests/test_vesper_research_integrity_transcript.py .github/workflows/vesper-conversational-presence-v2.yml
git commit -m "feat: expose governed commercial case truth to operator surfaces"
```

---

## Slice 1 completion checkpoint

Before merging/deploying:

1. Verify no public endpoint exposes private customer cases.
2. Verify no new code gives Smart Outlook direct send authority.
3. Verify no numeric quote is produced outside governed bands/comparables.
4. Verify full Research Integrity transcript passes.
5. Verify current Telegram text round-trip remains functional.
6. Verify runtime state root can be redirected to `/srv/dio/state` without code changes.
7. Request code review and resolve all Critical/Important findings.
8. Only then prepare the mobile Control Deck Slice 2 plan.