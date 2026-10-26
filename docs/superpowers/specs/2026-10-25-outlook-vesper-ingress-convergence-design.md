# Outlook-to-Vesper Ingress Convergence Design

Status: approved planning baseline  
Date: 2026-10-25  
Relationship: phase-two ingress surface for the ContractProof golden lane

## Intent

Make Outlook a governed customer ingress surface over the same Presence Core case, attachment, commercial, fulfilment, and release contracts used by Vesper web. Outlook must not create a second customer journey, payment ledger, or release path.

The canonical inbound route is:

```text
Microsoft Graph outbound delta poll
  -> immutable versioned mail capture
  -> attachment quarantine
  -> security/type/structure inspection
  -> operator clearance
  -> typed Outlook-to-Vesper envelope
  -> exact-replay local ingress ledger
  -> Presence Core conversation and case binding
  -> PREVIEW_ONLY response or Needs You action
```

Outbound mail is a separate effect boundary:

```text
case/release event
  -> content-addressed mail intent
  -> exact Graph draft reconciliation
  -> human approval bound to exact bytes and recipients
  -> Graph send
  -> provider reconciliation
  -> lineage-complete send receipt
```

## Evidence from inspection

- `config/phase9_sovereign_runtime.json` selects Microsoft Graph `outbound_delta_poll` and disables the Cloudflare mail webhook path.
- `scripts/sync_outlook_mail.py` can establish a delta baseline, hydrate sparse records, persist `dio.mail_ingress.v1`, and quarantine ordinary file attachments.
- Current attachment capture records SHA-256 and applies restrictive permissions, but has no malware/type/archive scan, clearance receipt, or promotion into canonical product input.
- `commerce/orchestrator.py::triage_mail` mutates ingress routing state and may stage legacy product jobs; it does not call `presence_core.engine.process_envelope` or create a canonical Vesper case.
- The observed state contained 16 inbound records: 11 `system_ignored`, 5 `needs_operator_triage`, no cleared attachments, and no lead bindings.
- The observed state contained 18 outbound intents and 15 send receipts, but no receipt was bound to a case, release manifest, or release authority.
- `create_outlook_draft` accepts arbitrary existing local attachment paths and can create duplicate provider drafts after ambiguous failure.
- `approve_intent` approves a mutable intent ID rather than a digest of recipient, subject, body, and attachment bytes.
- `send_outlook_draft` consumes the approval on any Graph exception without first determining whether the provider sent the draft.
- The V13-V16 bundles prove useful synthetic local adapters. V16 passes all 21 tests and demonstrates exact replay/refusal in SQLite, but explicitly does not authenticate a live mailbox, dispatch into Presence Core, create a customer case, or send mail. Its replay and redacted-receipt patterns should be ported selectively, not merged wholesale.
- The current focused Outlook/Graph suite passes 25 tests. This establishes component health, not end-to-end readiness.

## Goals

1. Preserve every observed version of a provider message without silent overwrite.
2. Make exact replay deterministic and conflicting reuse a reconciliation hold.
3. Keep all attachments quarantined until scanner checks and a named operator clearance pass.
4. Convert cleared inbound mail into the same canonical Vesper envelope and Presence Core case model as web ingress.
5. Bind Graph message, internet-message, conversation, local ingress, Presence conversation, case, source manifest, and eventual reply identifiers.
6. Default inbound processing to preview only; transport never creates product, payment, fulfilment, or release authority.
7. Bind outbound approval to the exact recipients, subject, body, attachments, case, manifest, and release authority.
8. Reconcile ambiguous draft creation and send outcomes before retry.
9. Preserve a durable, inspectable operator path for holds and recovery.

## Non-goals

- Using Outlook as the initial ContractProof pilot delivery channel.
- Enabling Cloudflare Graph webhook custody for phase two.
- Automatically opening, executing, or trusting mail attachments.
- Automatically replying to customers.
- Treating sender address alone as verified customer identity.
- Merging legacy V13-V16 archives wholesale.
- Expanding Graph permissions beyond the minimum needed by the selected read or send phase.

## Canonical source and transport

Microsoft Graph delta polling is the content source. The delta cursor is transport state, not customer truth. Each hydrated provider version is canonicalized and hashed before persistence. A provider message ID plus version/content digest identifies the immutable capture. An exact repeat returns the existing receipt; different content under an already completed event key creates `HELD_RECONCILIATION` and retains both observations.

Cloudflare Graph webhook code is disabled. A future webhook may act only as a wake-up hint that triggers the same local delta poll; the notification body never becomes message content truth.

## Attachment custody

Captured files remain beneath a per-ingress quarantine root with restrictive permissions and a manifest recording filename, size, provider type, declared media type, detected type, SHA-256, and capture state. Before extraction or promotion, each file must pass:

- size and aggregate limits;
- safe filename and path checks;
- magic-byte/type agreement;
- supported PDF/DOCX structure checks;
- archive member count, expanded-size, path traversal, and nesting limits;
- malware scanning where an approved local scanner is available;
- explicit operator clearance bound to the file hash and scan receipt.

Scanner unavailability yields a hold, not a pass. Inline, item, reference, password-protected, malformed, unsupported, or oversized attachments remain metadata-only or held. Promotion copies approved bytes into the canonical Presence attachment store and records a source manifest; it never mutates the quarantined original.

## Outlook-to-Vesper adapter

The adapter emits a public `channel="outlook"` envelope containing the provider message ID as `source_message_id`, a stable external identity derived from the normalized sender only as an unverified identity key, subject/body as untrusted customer text, and cleared attachments as quarantined Presence records. It carries Graph conversation and internet-message IDs as lineage metadata.

The adapter enters `LocalIngressLedger` before calling `process_envelope`. The ledger response is completed only after Presence Core returns a valid authority-bounded result. An in-doubt record requires operator reconciliation. The adapter refuses any result that claims send, spend, payment, fulfilment, attachment-processing, or release authority.

Conversation binding uses an explicit local binding record. Sender address and Graph conversation ID may propose a match but cannot silently merge two customer cases. Ambiguous matches create `NEEDS_YOU`.

The legacy commercial mail triage may consume a projection of the canonical case after dispatch, but it may not stage a parallel job directly from raw mail.

## Outbound mail authority

A mail intent becomes immutable when a draft or approval is requested. Its content digest covers normalized recipients, subject, selected body representation, ordered attachment names/hashes, case ID, purpose, manifest SHA-256 when delivering artifacts, and release-authority ID when external release is involved.

Draft creation uses the content digest as the local idempotency key. Before retrying after an ambiguous Graph response, the system searches/reconciles the provider draft using retained provider identifiers and a DIO correlation marker. A different digest requires a new intent and approval.

Human approval records the exact content digest, named approver, time, expiry, recipient verification when required, and permitted action. Send revalidates the digest, attachment bytes, case/manifest/release lineage, approval lease, and Graph draft identity immediately before the provider effect.

An ambiguous send transitions to `SEND_IN_DOUBT`. The system queries Graph sent items/draft state using the provider identity and correlation marker before either recording success or permitting a retry. It never reports a failure that invites a blind resend.

The final receipt includes mail intent/digest, provider draft/message/conversation IDs, recipients, attachment hashes, case ID, manifest SHA-256, release-authority ID, approval ID, sent time, and reconciliation evidence. For ordinary non-delivery correspondence, manifest and release fields are explicitly null.

## State and holds

Inbound states:

```text
CAPTURED -> QUARANTINED -> CLEARED -> DISPATCHING -> COMPLETED
                   |          |             \-> HELD_RECONCILIATION
                   +----------+----------------> HELD_SECURITY
```

Outbound states:

```text
MUTABLE -> SEALED -> DRAFTED -> APPROVED -> SENDING -> SENT
                         \-> DRAFT_IN_DOUBT       \-> SEND_IN_DOUBT
```

Every hold records the exact content hash, previous state, reason, actor or subsystem, timestamps, evidence, and allowed operator resolutions. Operator tools provide inspect, resolve-as-completed, retry-when-safe, and abandon/supersede actions without manual JSON editing.

## Security and permissions

Inbound deployment begins with the minimum delegated read permission that supports delta polling and attachment retrieval. Draft and send capabilities are enabled separately and only when required. `Mail.Send` is not added merely to complete inbound convergence. Token cache and connection files remain outside the repository with restrictive permissions; readiness checks report only metadata, never tokens.

Message bodies and attachments are sensitive customer data. Logs and receipts store hashes, IDs, state, and redacted summaries—not full bodies or secrets. Retention and deletion operate on the canonical case lineage while preserving the minimum immutable audit receipt.

## Verification and acceptance

Tests cover sparse delta hydration, immutable version capture, duplicate and conflicting replay, deleted provider objects, cursor expiration/rebaseline, malformed/oversized/archive-bomb attachments, scanner unavailable, clearance binding, ambiguous identity, Vesper authority refusal, process crash, draft timeout, intent mutation after approval, attachment mutation, send timeout, and provider reconciliation.

Phase two is ready only when a controlled mailbox exercise proves:

- one real inbound PDF or DOCX is captured, cleared, and bound to a canonical Vesper case;
- duplicate polling does not duplicate the case or message turn;
- changed content cannot overwrite completed custody;
- no uncleared attachment is parsed or promoted;
- no raw mail creates a parallel commercial job;
- an outbound draft cannot be sent after content or attachment mutation;
- an ambiguous send is reconciled without a duplicate message;
- the retained trace joins provider message through canonical case and, when applicable, exact release manifest and delivery receipt.

