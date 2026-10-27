# Vesper Outlook Production Journey Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Carry an Outlook customer message from immutable capture and verified identity through canonical Vesper fulfilment, professional packaging, exact approval, controlled Graph delivery, and reconciled receipt.

**Architecture:** Implement the immutable capture and quarantine baseline from the 2026-10-25 Outlook plan, then supersede its preview-only limit with a sealed outbox and one-use attempt lease. Capture, dispatch, and reconciliation run as separate services against one pinned release and state root.

**Tech Stack:** Python 3.13, Microsoft Graph/MSAL, ClamAV, JSON/JSONL, SQLite ledgers, pytest, systemd.

**Spec:** `docs/superpowers/specs/2026-10-27-production-convergence-design.md`

## Global Constraints

- Provider IDs and sender addresses are hints, never identity authority.
- Only hash-bound cleared attachments enter Presence custody.
- Shared mailboxes require signed token or identified operator approval.
- Controlled send requires `Mail.Send`; no broader delegated Graph scope is accepted.
- Ambiguous provider effects retain the release lease until reconciliation.
- Writers emit only `dio.delivery_receipt.v3`; v2 remains read-only.

## Review Focus

- Sparse Graph updates and reused message IDs must preserve all versions; Task 1 pins this.
- Scanner outage/stale signatures and archive bombs must hold attachments; Task 2 pins this.
- Shared or ambiguous customer identities must never merge automatically; Task 3 pins this.
- Crash/timeouts around draft/send must not duplicate an effect; Task 6 pins this.
- A changed body or attachment after approval must invalidate delivery; Task 5 pins this.

---

### Task 1: Immutable Outlook Capture

**Files:**
- Create: `adapters/microsoft_graph/mail_capture.py`
- Modify: `scripts/sync_outlook_mail.py`
- Create: `tests/test_outlook_immutable_capture.py`
- Modify: `tests/test_microsoft_graph_client.py`

**Interfaces:**
- Produces: `capture_message_version(state_root: Path, message: Mapping[str, Any], attachments: Sequence[Mapping[str, Any]]) -> MailCaptureReceiptV1`; `recover_delta_cursor(...) -> DeltaRecoveryReceipt`.

- [ ] Write failing tests for canonical hashes, replay, conflict, sparse hydration, tombstones, etags, previous-version links, expired cursor, and baseline without customer ingress.
- [ ] Implement content-addressed immutable capture and safe delta recovery.
- [ ] Run `pytest -q tests/test_outlook_immutable_capture.py tests/test_microsoft_graph_client.py tests/test_market_sensorium_mail_delta_recovery.py`; expect PASS.
- [ ] Commit with `feat: preserve immutable Outlook captures`.

### Task 2: ClamAV Attachment Quarantine and Clearance

**Files:**
- Create: `presence_core/mail_attachment_clearance.py`
- Modify: `presence_core/attachments.py`
- Modify: `scripts/sync_outlook_mail.py`
- Create: `tests/test_outlook_attachment_clearance.py`

**Interfaces:**
- Produces: `inspect_mail_attachments(..., scanner: ClamAvScanner) -> AttachmentInspection`; `clear_mail_attachments(..., actor_id: str) -> AttachmentClearance`; `promote_mail_attachments(...) -> list[PresenceAttachment]`.

- [ ] Write failing tests for magic/MIME mismatch, unsafe names, PDF/Office structure, encrypted/malformed files, archive depth/ratio/member limits, mutation, detection, missing daemon, stale signatures, and engine-version receipts.
- [ ] Implement immutable quarantine, ClamAV readiness, hash-bound identified clearance, and custody promotion.
- [ ] Run `pytest -q tests/test_outlook_attachment_clearance.py tests/test_presence_wave2_attachments.py`; expect PASS.
- [ ] Commit with `feat: quarantine and clear Outlook attachments`.

### Task 3: Verified Customer Binding and Canonical Ingress

**Files:**
- Create: `presence_core/outlook_identity.py`
- Create: `presence_core/outlook_ingress.py`
- Modify: `presence_core/local_ingress.py`
- Modify: `commerce/orchestrator.py`
- Create: `scripts/dispatch_outlook_ingress.py`
- Create: `tests/test_outlook_presence_ingress.py`

**Interfaces:**
- Produces: `verify_outlook_identity(binding_request: IdentityBindingRequest) -> IdentityBindingReceipt`; `dispatch_outlook_capture(dio_root: Path, state_root: Path, capture_id: str) -> OutlookIngressReceipt`.

- [ ] Write failing tests for signed session token, one-time reply challenge, identified operator approval, replay/expiry, shared mailbox, multiple cases, changed address, ledger crash recovery, and no direct raw-mail job staging.
- [ ] Implement durable provider-to-customer bindings, canonical Presence envelopes, `LocalIngressLedger` claims, `process_envelope`, and full lineage.
- [ ] Project completed canonical cases to legacy reporting and disable raw-mail job creation.
- [ ] Run `pytest -q tests/test_outlook_presence_ingress.py tests/test_presence_engine.py tests/test_commercial_triune.py`; expect PASS.
- [ ] Commit with `feat: bind Outlook ingress to canonical Vesper cases`.

### Task 4: Production Journey Coordinator

**Files:**
- Create: `presence_core/production_journey.py`
- Modify: `presence_core/fulfilment_egress.py`
- Modify: `presence_core/product_binding_registry.py`
- Modify: `products/customer_journey.py`
- Create: `tests/test_vesper_production_journey.py`

**Interfaces:**
- Produces: `advance_production_journey(case_id: str, *, command_id: str, actor_id: str) -> JourneyTransitionReceipt`; a registered map from the ten route adapter IDs to existing production handlers.

- [ ] Write failing tests spanning intake, scope, quote, settlement evidence, handler dispatch, Format Core/Production Studio finish, manifest, exact approval, and held release; reject Phase 7 simulated settlement/approval.
- [ ] Implement durable idempotent transitions and outbox records over existing case and fulfilment contracts.
- [ ] Run `pytest -q tests/test_vesper_production_journey.py tests/test_customer_journey_phase8.py tests/test_customer_journey_phase7.py`; expect PASS.
- [ ] Commit with `feat: coordinate Vesper production journeys`.

### Task 5: Sealed Outlook Intent and Release Lease

**Files:**
- Create: `presence_core/delivery_authority.py`
- Modify: `scripts/manage_mail_intent.py`
- Modify: `scripts/serve_control_deck.py`
- Create: `tests/test_outlook_delivery_authority.py`

**Interfaces:**
- Produces: `seal_delivery_intent(...) -> SealedDeliveryIntent`; `approve_delivery_intent(...) -> DeliveryApproval`; `acquire_attempt_lease(...) -> DeliveryAttemptLease`; `release_pre_effect_lease(...)`; `consume_successful_lease(...)`.

- [ ] Write failing tests proving the digest covers recipients, subject, body representation, ordered attachment names/bytes, case, manifest, authority, binding, and marker; cover mutation, expiry, concurrency, crash, proven pre-effect failure, and ambiguous retention.
- [ ] Implement sealed intents, exact approvals, atomic leases, and append-only attempt history.
- [ ] Run `pytest -q tests/test_outlook_delivery_authority.py tests/test_fulfilment_transport_authority.py`; expect PASS.
- [ ] Commit with `feat: seal Vesper Outlook delivery authority`.

### Task 6: Graph Draft, Send, and Reconciliation

**Files:**
- Create: `adapters/microsoft_graph/mail_reconciliation.py`
- Modify: `scripts/sync_outlook_mail.py`
- Create: `scripts/reconcile_outlook_delivery.py`
- Create: `adapters/microsoft_graph/delivery_receipt.py`
- Create: `tests/test_outlook_sealed_send.py`

**Interfaces:**
- Produces: `dispatch_sealed_delivery(intent_id: str) -> DeliveryAttempt`; `reconcile_graph_delivery(attempt_id: str) -> DeliveryAttempt`; `write_delivery_receipt_v3(...) -> DeliveryReceiptV3`; `read_delivery_receipt(...)` with v2 compatibility.

- [ ] Write failing tests for draft/send success, stable correlation marker, both in-doubt states, provider search before retry, duplicate evidence, impossible ambiguity, v2 reads, v3 lineage, and no v2 writes.
- [ ] Implement Graph effects and reconciliation; consume the lease only after provider evidence proves success.
- [ ] Run `pytest -q tests/test_outlook_sealed_send.py tests/test_dio_mail_core.py tests/test_outlook_delivery_authority.py`; expect PASS.
- [ ] Commit with `feat: reconcile controlled Outlook delivery`.

### Task 7: Service Cutover and Controlled-Mailbox Proof

**Files:**
- Create: `deploy/systemd/dio-outlook-capture.service`
- Create: `deploy/systemd/dio-outlook-dispatch.service`
- Create: `deploy/systemd/dio-outlook-reconcile.service`
- Modify: `config/phase9_sovereign_runtime.json`
- Create: `scripts/verify_outlook_journey.py`
- Create: `docs/runbooks/outlook-vesper-production.md`
- Create: `tests/test_outlook_journey_readiness.py`

**Interfaces:**
- Produces: `dio.outlook_journey_readiness.v1` and one redacted controlled-mailbox trace from capture through v3 delivery receipt.

- [ ] Write failing tests for Graph scope progression, configured mailbox metadata, pinned paths/venv/state root, ClamAV readiness, superseded active units, stuck holds/leases, and secret-bearing output.
- [ ] Add the three services, host verifier, explicit legacy-unit disable list, rollback steps, and shadow acceptance threshold.
- [ ] Run the full Outlook/Vesper focused suite and a controlled mailbox dry run; then enable `Mail.Send` only for the controlled-send proof.
- [ ] Reconcile the proof, retain redacted receipts, and commit with `ops: cut over canonical Outlook Vesper journey`.
