# Outlook-to-Vesper Ingress Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Microsoft Outlook a replay-safe, attachment-governed ingress surface for canonical Vesper cases and harden outbound Graph mail so exact approved content can be reconciled without duplicate sends.

**Architecture:** Keep Phase 9 Microsoft Graph outbound delta polling as the sole inbound content source. Add immutable version capture, security clearance, and a thin Outlook-to-Presence adapter over the existing local ingress ledger; separately seal outbound intents by content digest and reconcile ambiguous Graph draft/send effects.

**Tech Stack:** Python 3.13, pytest, Microsoft Graph REST/MSAL, JSON receipts, SQLite ingress ledger, local attachment quarantine.

**Spec:** `docs/superpowers/specs/2026-10-25-outlook-vesper-ingress-convergence-design.md`

## Global Constraints

- Preserve existing user changes and do not merge the V13-V16 archives wholesale.
- Inbound content truth is local Graph delta polling; Cloudflare Graph webhooks remain disabled and may later be wake-up hints only.
- Mail transport creates no product, payment, fulfilment, attachment-processing, send, or release authority.
- Sender address and Graph conversation ID are unverified identity hints, not sufficient authority to merge cases.
- No attachment is parsed or promoted before security checks and explicit hash-bound operator clearance.
- Outlook is not the ContractProof pilot delivery channel; authenticated Vesper web remains the first delivery transport.
- Outbound approval is bound to exact recipients, subject, body, attachment bytes, case, manifest, and release authority.
- Ambiguous provider outcomes are reconciled before retry; blind draft recreation and blind resend are prohibited.

## Review Focus

- Graph returns sparse updates, deletions, or a stale delta cursor: hydrate safely, preserve prior versions, and rebaseline without replaying the mailbox; Task 1 tests pin this.
- A PDF/DOCX declaration disagrees with bytes, an archive expands excessively, or scanner is unavailable: retain quarantine and hold; Task 2 tests pin this.
- Sender/conversation hints match multiple cases: create `NEEDS_YOU`, never silently merge; Task 3 tests pin this.
- An intent or attachment changes after approval: invalidate approval and refuse send; Task 5 tests pin this.
- Graph times out after draft creation or send: enter an in-doubt state and reconcile provider evidence before retry; Task 5 tests pin this.

---

### Task 1: Immutable Versioned Graph Capture

**Files:**
- Create: `adapters/microsoft_graph/mail_capture.py`
- Modify: `scripts/sync_outlook_mail.py`
- Test: `tests/test_outlook_immutable_capture.py`
- Test: `tests/test_phase9_graph_delta_baseline.py`

**Interfaces:**
- Consumes: hydrated Graph message objects and delta cursor state.
- Produces: `capture_message_version(state_root: Path, message: dict[str, Any], attachments: list[dict[str, Any]]) -> dict[str, Any]` returning `dio.mail_capture_receipt.v1`; `recover_delta_cursor(...) -> dict[str, Any]`.

- [ ] **Step 1: Write failing capture and cursor tests**

Assert canonical content hashing, immutable versions, exact replay, conflict hold, deleted-object tombstones, sparse hydration, delta cursor expiration, baseline archive, and no full-mailbox ingress during rebaseline.

- [ ] **Step 2: Run and confirm failure**

Run: `pytest -q tests/test_outlook_immutable_capture.py tests/test_phase9_graph_delta_baseline.py`
Expected: new immutable-version assertions FAIL.

- [ ] **Step 3: Implement capture receipts and version storage**

Key storage by provider message ID plus canonical content digest; retain internet-message ID, conversation ID, observed version, capture time, body digest, and attachment metadata. Do not overwrite a completed capture.

- [ ] **Step 4: Add safe cursor recovery**

Archive old cursor/error evidence, establish a new baseline without generating customer turns, and resume only from the new delta link.

- [ ] **Step 5: Verify**

Run: `pytest -q tests/test_outlook_immutable_capture.py tests/test_phase9_graph_delta_baseline.py tests/test_market_sensorium_mail_delta_recovery.py tests/test_microsoft_graph_client.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add adapters/microsoft_graph/mail_capture.py scripts/sync_outlook_mail.py tests/test_outlook_immutable_capture.py tests/test_phase9_graph_delta_baseline.py
git commit -m "feat: preserve immutable Outlook message versions"
```

### Task 2: Attachment Scan, Clearance, and Promotion

**Files:**
- Create: `presence_core/mail_attachment_clearance.py`
- Modify: `scripts/sync_outlook_mail.py`
- Modify: `presence_core/attachments.py`
- Test: `tests/test_outlook_attachment_clearance.py`

**Interfaces:**
- Consumes: captured Graph attachment receipts and immutable quarantine files.
- Produces: `inspect_mail_attachments(capture: dict[str, Any], *, scanner: Callable[[Path], dict[str, Any]] | None) -> dict[str, Any]`; `clear_mail_attachments(state_root: Path, *, capture_id: str, attachment_hashes: list[str], scan_receipt_sha256: str, cleared_by: str) -> dict[str, Any]`; `promote_mail_attachments(...) -> list[dict[str, Any]]`.

- [ ] **Step 1: Write failing hostile-input tests**

Cover PDF/DOCX magic and structure, MIME mismatch, malformed/password-protected files, oversized content, unsafe archive paths, member/expanded-size/nesting limits, scanner unavailable/detection, inline/reference/item attachments, changed quarantine bytes, and replayed clearance.

- [ ] **Step 2: Run and confirm failure**

Run: `pytest -q tests/test_outlook_attachment_clearance.py`
Expected: FAIL because scan/clearance/promotion contracts are absent.

- [ ] **Step 3: Implement non-promoting inspection and holds**

Inspection records detected type and scanner evidence but never extracts customer text. Scanner absence or unsupported structures yield `HELD_SECURITY`, not a pass.

- [ ] **Step 4: Implement clearance and canonical promotion**

Bind the named operator to exact hashes and scan receipt, then copy approved bytes into Presence attachment custody with new lineage records while preserving quarantine originals.

- [ ] **Step 5: Verify**

Run: `pytest -q tests/test_outlook_attachment_clearance.py tests/test_presence_wave2_attachments.py tests/test_dio_mail_core.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add presence_core/mail_attachment_clearance.py scripts/sync_outlook_mail.py presence_core/attachments.py tests/test_outlook_attachment_clearance.py
git commit -m "feat: govern Outlook attachment clearance"
```

### Task 3: Outlook-to-Presence Adapter and Case Binding

**Files:**
- Create: `presence_core/outlook_ingress.py`
- Modify: `presence_core/local_ingress.py`
- Modify: `commerce/orchestrator.py`
- Create: `scripts/dispatch_outlook_ingress.py`
- Test: `tests/test_outlook_presence_ingress.py`

**Interfaces:**
- Consumes: immutable capture receipt, cleared/promoted attachments, Presence config, and `LocalIngressLedger`.
- Produces: `build_outlook_envelope(capture: dict[str, Any], promoted: list[dict[str, Any]]) -> dict[str, Any]`; `dispatch_outlook_capture(dio_root: Path, state_root: Path, capture_id: str) -> dict[str, Any]`.

- [ ] **Step 1: Write failing adapter/identity/authority tests**

Assert typed `channel="outlook"` envelope, stable unverified external identity, Graph lineage metadata, exact replay, crash/in-doubt refusal, one canonical customer turn, ambiguous match to `NEEDS_YOU`, and refusal of any Presence result claiming external authority.

- [ ] **Step 2: Run and confirm failure**

Run: `pytest -q tests/test_outlook_presence_ingress.py`
Expected: FAIL because no production Outlook dispatcher exists.

- [ ] **Step 3: Implement the thin adapter and replay boundary**

Claim the capture hash before `process_envelope`, pass only cleared attachments, validate public-role/authority invariants, and complete the ledger with the redacted Presence result.

- [ ] **Step 4: Retire direct raw-mail job staging**

Change `triage_mail` so raw Graph ingress can only be ignored, held, or dispatched canonically. If legacy commercial reporting remains, feed it a projection of the resulting case rather than raw mail.

- [ ] **Step 5: Verify**

Run: `pytest -q tests/test_outlook_presence_ingress.py tests/test_presence_engine.py tests/test_phase9_sovereign_runtime.py tests/test_commercial_triune.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add presence_core/outlook_ingress.py presence_core/local_ingress.py commerce/orchestrator.py scripts/dispatch_outlook_ingress.py tests/test_outlook_presence_ingress.py
git commit -m "feat: dispatch Outlook mail into canonical Vesper cases"
```

### Task 4: Outlook Ingress Reconciliation Console

**Files:**
- Create: `scripts/manage_outlook_ingress.py`
- Create: `presence_core/ingress_reconciliation.py`
- Test: `tests/test_outlook_ingress_reconciliation.py`

**Interfaces:**
- Consumes: mail capture, attachment hold, identity hold, and local-ingress ledger records.
- Produces: commands `list`, `inspect`, `clear-attachments`, `bind-case`, `retry-safe`, `resolve-completed`, `abandon`, and `supersede` with immutable operator receipts.

- [ ] **Step 1: Write failing operator-recovery tests**

Assert no direct JSON edits, named actor/reason/evidence, safe retry only before possible external effects, exact before/after hashes, conflict refusal, and redacted output.

- [ ] **Step 2: Run and confirm failure**

Run: `pytest -q tests/test_outlook_ingress_reconciliation.py`
Expected: FAIL because reconciliation APIs are absent.

- [ ] **Step 3: Implement hold and resolution receipts**

Keep append-only reconciliation history and expose only transitions permitted by the current state and evidence.

- [ ] **Step 4: Implement the CLI**

Return machine-readable JSON by default and ensure inspect/list never emit body contents, attachment bytes, tokens, or secrets.

- [ ] **Step 5: Verify**

Run: `pytest -q tests/test_outlook_ingress_reconciliation.py tests/test_outlook_presence_ingress.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add presence_core/ingress_reconciliation.py scripts/manage_outlook_ingress.py tests/test_outlook_ingress_reconciliation.py
git commit -m "feat: add Outlook ingress reconciliation controls"
```

### Task 5: Content-Sealed Graph Draft and Send

**Files:**
- Modify: `scripts/manage_mail_intent.py`
- Modify: `scripts/sync_outlook_mail.py`
- Create: `adapters/microsoft_graph/mail_reconciliation.py`
- Modify: `scripts/serve_control_deck.py`
- Test: `tests/test_outlook_sealed_send.py`

**Interfaces:**
- Consumes: mail intent, case, optional deliverable manifest/release authority, approved attachment paths, and Graph client.
- Produces: `seal_intent(...) -> dict[str, Any]`; `approve_sealed_intent(...) -> tuple[dict[str, Any], str]`; `reconcile_graph_draft(...) -> dict[str, Any]`; `reconcile_graph_send(...) -> dict[str, Any]`.

- [ ] **Step 1: Write failing seal/idempotency/ambiguity tests**

Assert content digest covers normalized recipients, subject, selected body representation, ordered attachment names/hashes, case/manifest/release IDs; arbitrary paths, mutation after seal/approval, wrong release authority, expired lease, duplicate draft, draft timeout, send timeout, and blind resend are refused.

- [ ] **Step 2: Run and confirm failure**

Run: `pytest -q tests/test_outlook_sealed_send.py`
Expected: FAIL because approval is not content-bound and ambiguity is not reconciled.

- [ ] **Step 3: Seal intents and bind approval**

Permit attachments only from approved manifests or explicitly cleared correspondence inputs. Persist the content digest and make any later field/byte change require a new intent and approval.

- [ ] **Step 4: Reconcile Graph effects**

Embed a DIO correlation marker, search the provider before recreating a draft, use `DRAFT_IN_DOUBT`/`SEND_IN_DOUBT`, and query draft/sent state before allowing retry. Do not consume authority merely because the client observed a timeout.

- [ ] **Step 5: Emit lineage-complete send receipts**

Include intent/digest, Graph identifiers, recipients, attachment hashes, case, optional manifest/release authority, approval, sent time, and reconciliation evidence; ordinary correspondence uses explicit null release fields.

- [ ] **Step 6: Verify**

Run: `pytest -q tests/test_outlook_sealed_send.py tests/test_dio_mail_core.py tests/test_fulfilment_transport_authority.py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/manage_mail_intent.py scripts/sync_outlook_mail.py adapters/microsoft_graph/mail_reconciliation.py scripts/serve_control_deck.py tests/test_outlook_sealed_send.py
git commit -m "feat: seal and reconcile Outlook mail effects"
```

### Task 6: Runtime Cutover and Controlled Mailbox Proof

**Files:**
- Modify: `config/phase9_sovereign_runtime.json`
- Create: `scripts/verify_outlook_ingress.py`
- Create: `docs/runbooks/outlook-ingress.md`
- Create: `tests/test_outlook_ingress_readiness.py`

**Interfaces:**
- Consumes: external Graph config metadata, service definition, delta/capture/hold state, dispatcher state, and focused test evidence.
- Produces: redacted `dio.outlook_ingress_readiness.v1` plus a retained controlled-mailbox trace.

- [ ] **Step 1: Write failing readiness tests**

Assert the verifier catches missing external config, excessive scopes, stale service paths, Cloudflare mail enablement, inactive poller/dispatcher, stuck captures, uncleared attachments, unresolved holds, and secrets accidentally located under the repository.

- [ ] **Step 2: Run and confirm failure**

Run: `pytest -q tests/test_outlook_ingress_readiness.py`
Expected: FAIL because readiness verification is absent.

- [ ] **Step 3: Implement verifier and runbook**

Document minimum read scopes, separate send enablement, token-cache permissions, baseline/rebaseline, service installation, attachment clearance, identity binding, hold recovery, retention, rollback, and stop conditions.

- [ ] **Step 4: Run automated verification**

Run: `pytest -q tests/test_outlook_*.py tests/test_dio_mail_core.py tests/test_microsoft_graph_client.py tests/test_phase9_graph_delta_baseline.py tests/test_market_sensorium_mail_delta_recovery.py tests/test_market_sensorium_mail_readiness.py`
Expected: PASS.

- [ ] **Step 5: Run controlled mailbox acceptance**

Using a non-production test mailbox, capture one real PDF/DOCX, clear and dispatch it to one canonical case, repeat the poll, exercise one conflict hold, create an exact draft, simulate/reconcile one ambiguous send, and retain only redacted receipts and hashes.

- [ ] **Step 6: Commit**

```bash
git add config/phase9_sovereign_runtime.json scripts/verify_outlook_ingress.py docs/runbooks/outlook-ingress.md tests/test_outlook_ingress_readiness.py
git commit -m "docs: add Outlook ingress cutover proof"
```

