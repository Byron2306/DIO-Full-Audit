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

Invoice issuance, checkout creation/capture, outbound email, fulfillment execution, release approval, and return-pack delivery continue through their existing gated systems. The web journey does not call those external actions. A displayed payment link is considered available only when canonical case state already contains one; payment becomes verified only from the settlement reconciliation receipt.

## Operational boundary

This implementation adds the journey API to the local Vesper service and public API allowlist, and adds the matching panel to the website checkout. The website checkout already had a user-owned retry-safety diff; that change was preserved. The website edits are local and uncommitted, and the public API package/site have not been installed or published from this workspace.
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
