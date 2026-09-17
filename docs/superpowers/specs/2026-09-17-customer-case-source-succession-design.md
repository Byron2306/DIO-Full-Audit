# Customer Case Source Succession Design

## Problem

DIO currently maps one Telegram conversation to one customer case.

A case may reach derived states such as SCOPE_ASSESSED or QUOTE_READY. If a materially different source artifact is later uploaded in the same conversation, the new attachment is appended to that existing case while the old scope, quote and checkout remain current.

Observed production example:

- Existing scoped source:
  - ATT-942F51710DD00194
  - SHA-256 bfbe05c...
  - 8 manuscript pages
  - approved quote DIO-Q-20260916-SOPHIA-001
- New source:
  - ATT-8502503D57846115
  - SHA-256 d02f085...
- Case incorrectly remained QUOTE_READY and resurfaced the old checkout.

## Governing invariant

A scope, quote, checkout and payment instruction are authoritative only for the exact source artifact from which they were derived.

Same source SHA means continuity.

A different source SHA after scope or commercial derivation means a new governed work item.

## Required behaviour

Given current case A scoped against source SHA A:

- upload with SHA A:
  - continue case A
  - do not create a successor solely because the custody receipt/attachment ID differs

- upload with SHA B:
  - if case A has not yet derived scope/commercial truth, continue case A
  - if case A has derived scope or quote truth, create successor case B

Case A:
- remains historically intact
- retains its scope
- retains its quote and commercial evidence
- retains its monotonic stage
- is never rolled backward

Case B:
- points to case A via predecessor_case_id
- retains customer identity, channel continuity and product routing
- binds the new source
- starts without inherited scope
- starts without inherited quote/order/checkout/payment truth
- advances normally to FILES_RECEIVED_QUARANTINED
- becomes the current case for the conversation

## Case identity

The original case may continue using the historical stable conversation-derived case ID.

Successor case IDs are deterministic from:

conversation_id + predecessor_case_id + new source SHA-256

This makes replay/idempotency safe. Reprocessing the same source transition must resolve to the same successor rather than minting duplicate cases.

## Conversation index

Keep the existing:

conversations[conversation_id] = current_case_id

for backward compatibility.

Add:

conversation_case_history[conversation_id] = [case_id, ...]

The current pointer moves to the successor. Historical cases remain loadable by ID.

## Successor state inheritance

Carry forward:
- customer_id
- customer_identity
- contact_email
- channel_origins
- conversation_ids
- product_id
- product_history where present
- requested_outcome where appropriate

Do not inherit:
- scope
- quote
- checkout URL
- order IDs
- payment state/evidence
- invoice state
- job links
- release authorities
- fulfilment state
- Needs You items belonging to prior work

Commercial state starts from the canonical fresh-case defaults.

## Authority boundary

Uploading new customer content does not create authority.

Source succession:
- creates no payment authority
- creates no fulfilment authority
- creates no execution authority
- creates no release authority

The new attachment remains quarantined and unsafe to parse/execute until the normal governed path permits further work.

## Acceptance

A quoted source-A case receiving source B with a different SHA must:

1. preserve case A unchanged in scope/commercial truth;
2. create deterministic successor case B;
3. move the conversation's current-case pointer to B;
4. bind B's source attachment;
5. leave B scope empty;
6. leave B quote not_prepared;
7. expose no inherited checkout;
8. put B at FILES_RECEIVED_QUARANTINED;
9. create no authority;
10. not fork when the newly uploaded bytes have the same SHA as the scoped source.
