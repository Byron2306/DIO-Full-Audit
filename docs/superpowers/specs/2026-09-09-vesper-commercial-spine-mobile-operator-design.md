# Vesper Commercial Spine + Mobile Operator Rail Design

Date: 2026-09-09

## Purpose

Launch Vesper as DIO's governed customer interface and Byron's operator chief of staff over one commercial/customer lifecycle shared by Presence, Outlook, Commerce, Needs You, Control Deck, and product runtimes.

The design deliberately separates three launch slices so the system can ship vertically without repeating the prior all-at-once launcher failure:

1. **Commercial Case Backbone** — canonical customer case, role-correct conversation, product scope, pricing/quote recommendation, Evidex invoice bridge, Outlook ingress/egress, Needs You, and operator summaries.
2. **Mobile Operator Cockpit** — Control Deck/PWA projection of the same case truth, optimized for phone use. Native Android is not a launch dependency.
3. **Public Web Vesper + Pocket TTS** — public website chat/voice surface using the same Presence and case APIs, with Vera/Pocket TTS as rendering only.

Each slice must be independently testable and must not create new external authority merely because a model generated persuasive text.

## Core invariant

**DIO determines what is true and allowed. Qwen determines how Vesper says it.**

Vesper must never infer that work started, an invoice was sent, a payment occurred, a file was processed, or a deliverable was released unless the corresponding governed receipt/state exists.

## Channel roles

### Operator Telegram

The existing authenticated Telegram lane is an **operator/private** surface. It is not a customer concierge.

It may:

- brief Byron on system state, leads, cases, quotes, invoices, payments, jobs, Market Command, mail, Needs You, and incidents;
- discuss implementation/proof maturity and internal product scope;
- show quote reasoning and comparable commercial evidence;
- request or record operator decisions through existing authority mechanisms.

It must not:

- pitch DIO to Byron;
- use customer-service closers such as “How can I assist you today?” by default;
- invent an account portal, billing team, processing time, pricing, or capability;
- claim an external action occurred merely because Byron approved it conversationally.

### Public website / future public Telegram

Public channels are customer-facing. They may explain products, qualify scope, receive bounded intake/uploads, provide governed price ranges or quote recommendations, and report verified case/payment/status state.

They must not expose operator/private data or internal implementation details that are not deliberately published.

## Canonical customer case

A customer interaction that becomes commercially meaningful creates or attaches to one durable `customer_case` object. Email is a transport, not the system of record.

Minimum fields:

```text
case_id
created_at
updated_at
channel_origins[]
conversation_ids[]
customer_identity
contact_email
product_id
requested_outcome
scope
attachments[]
commercial
outlook
job_links[]
needs_you_ids[]
stage
stage_history[]
last_customer_message_at
last_operator_action_at
authority_created=false
```

`scope` must support workload evidence such as page count, file count, reference count, requested depth, turnaround, manual review burden, and product-specific units.

`commercial` must support:

```text
pricing_mode
reference_offer
reference_band
quote_recommendation
quote_reasoning
quote_state
invoice_id
invoice_state
payment_state
payment_evidence_ref
currency
amount
```

No field transition may be created from conversational text alone when a stronger receipt is required.

## Case lifecycle

Canonical stages:

```text
NEW_LEAD
QUALIFIED
INTAKE_OPEN
FILES_RECEIVED_QUARANTINED
SCOPE_ASSESSED
PRICE_RECOMMENDED
QUOTE_READY
NEEDS_YOU
INVOICE_DRAFTED
INVOICE_SEND_APPROVAL
INVOICE_SENT
PAYMENT_PENDING
PAYMENT_VERIFIED
WORK_QUEUED
PROCESSING
REVIEW_READY
RELEASE_APPROVAL
DELIVERED
CLOSED
```

Stages may skip when a product does not require a particular commercial step, but they may never move backwards or jump over a required authority/evidence gate silently.

## Product scope truth

Product marketing copy is descriptive context, not execution authority.

For example, DIO Research Integrity currently advertises a **One-Section Claim Lineage Pilot**. A customer asking for a full 20-page manuscript must not cause Vesper to silently promote that pilot into a proven full-document production offer.

Vesper may instead say that the public offer is narrower, estimate the expanded scope, and create a quote/scope approval candidate for the operator.

## Attachment state firewall

Public/customer uploads follow:

```text
received -> quarantined -> human/routed review -> explicitly opened/parsed by an authorised workflow -> processed
```

Until a receipt proves the later state, Vesper may not say “I am processing it”, “analysis has started”, “I will send the results”, or equivalent.

The LLM claim guard must cover action-state language beyond completed send/payment verbs, including at minimum process, analyse/analyze, parse, open, start, queue, generate, invoice, charge, deliver, release, publish, submit, and fulfil.

## Commercial intelligence

Current website/product prices remain **reference offer bands**, not universal tariffs.

Vesper may use three pricing modes:

1. **Known fixed/banded offer** — cite the governed current public price/range.
2. **Scope-sensitive quote** — derive a bounded recommendation from product offer, scope units, complexity, urgency, manual-review burden, and structured historical commercial evidence.
3. **Outside known envelope** — prepare scope and escalate to operator rather than invent a number.

Historical invoices may inform pricing only after projection into structured commercial evidence. The LLM must not inspect arbitrary invoice text and freehand a price.

Structured comparable evidence should include where available:

```text
product_id
offer_id
scope_units
page_count
file_count
reference_count
complexity
urgency
manual_review_burden
quoted_amount
final_invoice_amount
payment_outcome
actual_fulfilment_effort
```

Qwen explains a price recommendation; deterministic DIO code computes the recommendation and records its evidence.

## Evidex invoice bridge

Evidex is the seed commercial implementation, not a separate side system.

Existing invoice/payment artifacts and controls must be projected into the canonical case:

- `INVOICE.docx`
- `INVOICE.txt`
- `INVOICE_ID.txt`
- `INVOICE_SENT.txt`
- `PAID.txt`
- `PAYMENT_RECEIPT.txt`

Existing payment-provider evidence remains authoritative. Browser-return success is not payment proof.

The first release may auto-create invoice drafts/candidates inside governed scope. Final external sending continues to use the existing Outlook/Graph authority rail unless an explicit bounded automation policy is later approved.

## Outlook ingress and egress

`dio_workflows@outlook.com` is the operational mail address.

### Ingress

Microsoft Graph / Smart Outlook may:

- read inbound mail;
- classify/route it;
- associate it with an existing customer case or create a candidate case;
- extract allowed attachments into quarantine;
- update case conversation history;
- create Needs You items for ambiguous/high-authority decisions.

Replies to website/public-Telegram customers must reconcile into the same case rather than create parallel mail-only truth.

### Egress

DIO may automatically prepare mail drafts for:

- scope confirmation;
- quote/invoice correspondence;
- upload instructions;
- payment reminders within approved policy;
- review-ready/delivery communication.

The Smart Outlook agent does not gain raw send authority. External sending uses the exact provider draft ID plus existing Control Deck approval/lease semantics and must write a send receipt.

## Needs You

Needs You is the shared human decision queue for Telegram operator Vesper and Control Deck.

Create an item when at least one of these applies:

- requested scope exceeds proven/marketed product envelope;
- price falls outside approved automatic band;
- unusual discount, urgency, or manual work is proposed;
- invoice requires operator approval;
- outbound draft requires send approval;
- attachment requires human inspection/routing;
- fulfilment/release requires human authority;
- ambiguous identity/payment/status evidence exists;
- a product-specific professional/legal/academic authority gate applies.

Operator Vesper should summarize the highest-value items first and explain why each needs Byron.

## Operator briefing contract

A normal operator question such as “What needs me?” should return a compact state-derived brief, for example:

```text
Four things need you.
1. Research Integrity: 20-page article. Recommended quote R1,450. Full-document scope exceeds the public one-section pilot; approve expanded scope/price.
2. Evidex: invoice draft R950. Customer accepted scope; approve send.
3. HOMS: payment verified; job ready for fulfilment. No decision needed.
4. Evidex: delivery pack review complete; release approval required.
```

The exact numbers above are illustrative only. Production replies must come from current case/commercial state.

## Control Deck / mobile contract

Control Deck consumes the same case and Needs You projections. It does not maintain a second CRM.

Required mobile-first commercial projection:

```text
Customer | Product | Value | Stage | Needs You
```

Case drill-down must expose:

```text
conversation
files / quarantine state
scope
quote recommendation + reasoning
invoice
payment
mail drafts / sends
job links
proof / receipts
approvals
outputs / release state
```

For the launch path, the installable PWA is the preferred phone cockpit because it already exists and avoids making the native Android wrapper a blocker. Operator Telegram provides push/briefing; the PWA provides pull/drill-down. Native Android may later wrap the same APIs and PWA once the transport is stable.

The browser must not receive long-lived DIO signing secrets or unrestricted action authority. Any approval action must call an existing server-side authority lease/confirmation mechanism.

## Public web Vesper

The public website uses the same Presence Core and customer-case creation path as other public channels.

It must support:

- session/conversation continuity;
- governed product discovery;
- scope qualification;
- bounded uploads into quarantine;
- price/range discussion;
- quote/intake creation;
- verified case/payment/status reporting;
- escalation to Needs You where authority is required.

It must not create a separate commercial truth database.

## Pocket TTS / Vera

Pocket TTS is a renderer only.

- Public web Vesper may render approved reply text through the Vera/Pocket TTS voice profile.
- Operator Telegram voice may be enabled later for concise briefs.
- TTS never changes meaning, pricing, scope, state, identity, or authority.
- Text-only commercial correctness must be proven before voice output is enabled.

## Runtime deployment

The permanent `dio-spine` remains the always-on Presence/commercial orchestration host.

Presence Core remains localhost-bound. Public/mobile surfaces must reach governed front-door endpoints through the approved web/edge layer, not by exposing `127.0.0.1:8787` directly.

Runtime state must live under `/srv/dio/state` (or another persistent state root outside disposable git worktrees) before production customer cases are accepted.

## Acceptance gauntlets

### A. Operator role regression

Byron asks ordinary questions about DIO/Sophia and receives owner-facing operational answers, not public sales copy.

### B. Research Integrity transcript regression

Replay this intent sequence:

```text
What exactly is DIO?
Tell me about Sophia.
Especially the integrity offering. What do I send and how does payment work?
It is a 20-page academic article.
Can I send the whole thing?
[file upload]
How long will that take and will you send an invoice?
```

Pass conditions:

- Vesper does not expand one-section proof into full-document production authority;
- upload remains quarantined until a workflow receipt says otherwise;
- no invented processing duration;
- no invented billing team/account portal;
- public/operator role is correct;
- price/invoice state is grounded in commercial truth;
- quote/scope approval is surfaced to Needs You if required.

### C. Evidex invoice round trip

```text
customer intake -> case -> scope -> quote/invoice draft -> Needs You -> operator approval -> Outlook send receipt -> payment evidence -> case PAYMENT_VERIFIED
```

Every transition must be auditable.

### D. Outlook reconciliation

A customer who starts on web and later replies by email remains one customer case with one conversation/commercial lineage.

### E. Mobile operator view

On Android, Byron can receive a Telegram operator brief, open the mobile PWA, see the same Needs You count, open the corresponding case, inspect quote/invoice/mail/payment state, and invoke only approved server-side authority actions.

### F. Voice

After text/web commercial gauntlets pass, Pocket TTS renders the exact approved Vesper reply without creating or mutating commercial/authority state.

## Launch order

1. Commercial Case Backbone on the Vesper/Presence branch.
2. Operator truth separation + expanded action-state guard + transcript regression tests.
3. Evidex invoice projection + Outlook case reconciliation + Needs You commercial events.
4. Stable read APIs for operator summary/case list/case detail.
5. Control Deck mobile commercial cockpit consuming those APIs.
6. Public web Vesper using the same case API.
7. Pocket TTS/Vera public rendering.
8. Native Android wrapper only after the PWA/mobile transport is stable.

## Success definition

Vesper is considered launched when a real public conversation can become a governed customer case, move through scope/pricing/invoice/mail/payment/job gates without invented state, surface the right decisions to Byron in Telegram and Control Deck on his phone, and return truthful customer status from the same underlying case lineage.
