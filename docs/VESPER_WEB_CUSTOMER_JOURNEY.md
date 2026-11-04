# Vesper web customer journey

Vesper now projects the canonical customer case into both the local intake dashboard and the existing DIO-Workflows website flow. The public route remains session-token bound:

- `GET /api/vesper/web/journey?conversation_id=VWC-…` returns the bounded journey view.
- `POST /api/vesper/web/journey` accepts an action ID, current stage-bound action reference, and a typed payload.

The service allowlist, website-origin gate, token ownership check, and `schemas/vesper_journey_action.schema.json` define this boundary. Action refs expire when the case stage changes. Replays of the same action ref and exact payload return the recorded outcome.

## Customer actions

The web surface supports structured intake, scope review, governed quote preparation, and a customer request for operator follow-up. Intake fields are derived from the selected commercial product definition: requested outcome, buyer class, and positive scope quantity. Contact name, email, and organisation are validated and retained as customer-provided, unverified details.

When pricing needs human review, the quote contract now creates a linked `Needs You` queue item. A customer can also request an operator follow-up for invoice/payment next steps; that request enters the canonical queue without creating a checkout, invoice, or email send.

Vesper writes a conversational receipt for each journey action into the existing session history. The same session-token read path can recover those messages after a browser reload.

## Commercial and delivery projection

The journey card reads invoice and payment state, settlement evidence class, fulfillment state, return-pack manifest/release state, delivery receipt, and Outlook draft/send receipt counts from the canonical case. It does not infer successful delivery from a prepared artifact or a browser return.

Invoice issuance, checkout creation/capture, outbound email, fulfillment execution, release approval, and return-pack delivery continue through their existing gated systems. A displayed payment link is considered available only when canonical case state already contains one; payment becomes verified only from the settlement reconciliation receipt. An issued invoice can be opened from the session-bound invoice route only when the canonical case links to it, the invoice is issued, and any recorded case email matches the invoice recipient. The web portal serves a return ZIP only after an operator created release authority that explicitly includes `web_portal`, portal delivery completed, the case reached `DELIVERED`, and receipt, manifest, and package hashes still match.

## Operational boundary

This implementation adds the journey API to the local Vesper service and public API allowlist, and adds the matching panel to the website checkout. The website checkout already had a user-owned retry-safety diff; that change was preserved. The website edits are local and uncommitted, and the public API package/site have not been installed or published from this workspace.

## Outlook Graph intake runbook

Graph polling remains a separate capture operation. To review captured messages without printing message content, run:

```sh
python scripts/manage_outlook_ingress.py list
python scripts/manage_outlook_ingress.py inspect MAILCAP-<capture-id>
```

Captured attachments are held until the operator rescans them with a current local ClamAV engine and signatures (maximum accepted age: 48 hours). A successful scan records an immutable clearance receipt; it moves files only into Vesper's quarantine. To clear and dispatch:

```sh
python scripts/manage_outlook_ingress.py clear-attachments MAILCAP-<capture-id> --actor-id <operator-id>
python scripts/manage_outlook_ingress.py dispatch MAILCAP-<capture-id> --operator-id <operator-id> --customer-id <customer-id> --binding-reason <reason> --evidence-ref <evidence-reference>
```

Where a valid signed customer identity token is available, use `--session-token-file <private-file>` instead of the operator binding fields. Shared mailbox use must be explicit with `--shared-mailbox`. The bridge validates the immutable capture against the Graph ingress record, binds the sender to the selected customer, records a bounded receipt, and routes the message through the canonical Presence engine. Attachment contents remain quarantined, non-executable and unavailable to parsing until a separate review action. A missing or mismatched clearance returns `needs_operator`; it does not route the body or create authority. An interrupted dispatch is left in the idempotency ledger for manual reconciliation and must not be blindly replayed.

For a Graph send that timed out after submission, reconcile the exact provider draft identity before considering any retry:

```sh
python scripts/reconcile_outlook_send.py <mail-intent-id>
```

The command checks Graph's exact immutable message id, intended recipient, draft state and provider sent timestamp. It records a sent receipt only when provider evidence identifies the message as sent. A still-draft or mismatched result remains held; the command never sends or retries. A provider sent state is not proof that the recipient received or read the message.

## Quotes, invoices and return packages

The customer web journey supports structured intake, quote preparation, opening an issued invoice and requesting operator follow-up. Invoice creation and issuance remain in the operator Business invoice desk; payment and settlement are recorded by their existing reconciliation paths. Return files remain held until fulfilment, manifest validation, explicit release approval and delivery through a channel listed in that approval. To deliver an already-approved web-portal release, run `python scripts/deliver_vesper_web_package.py <authority-id>`. The configured presence root defaults to `state/presence`; set `DIO_VESPER_PRESENCE_ROOT` when deployment uses another path. This command cannot broaden an existing authority's channel scope. The session-bound package route serves only the exact ZIP whose hash is recorded in the successful delivery receipt.
# Durable Journey Command Ledger (2026-11-04)

`presence_core.production_journey.advance_production_journey` adds a SQLite
command ledger around the existing canonical Vesper action runtime. It binds a
caller command ID to the case, action, action reference, actor labels and payload
hash. Reusing a completed command returns its saved result; reusing the ID with
different inputs fails closed.

An interrupted handler is recorded as `NEEDS_RECONCILIATION` and is never
automatically replayed. An operator must record evidence to confirm whether the
effect completed. If no effect occurred, the original command stays held and a
new command ID is required. This protects against duplicate external effects,
but it does not make downstream handlers transactional or prove that their
effects succeeded. `actor_id` is an audit label supplied by the caller; this
module does not authenticate it. Controlled Outlook send, attempt leasing,
provider reconciliation, service cutover and a customer mailbox trace remain
separate unfinished release gates in the production journey plan.
