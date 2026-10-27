# Vesper Commercial Spine + Mobile Operator Rail Design

Date: 2026-09-09

## Purpose

Launch Vesper as DIO's governed customer interface and Byron's operator chief of staff over one commercial/customer lifecycle shared by Presence, Outlook, Commerce, Needs You, Control Deck, and product runtimes.

The design separates three launch slices: Commercial Case Backbone, Mobile Operator Cockpit, and Public Web Vesper + Pocket TTS. Each slice must be independently testable and must not create new external authority merely because a model generated persuasive text.

## Core invariant

**DIO determines what is true and allowed. Qwen determines how Vesper says it.**

Vesper must never infer that work started, an invoice was sent, a payment occurred, a file was processed, or a deliverable was released unless the corresponding governed receipt/state exists.

## Channel roles

Operator Telegram is a private/operator surface. It may brief Byron on system state, cases, quotes, invoices, payments, jobs, Market Command, mail, Needs You, and incidents. It must not pitch DIO to Byron or invent external actions.

Public channels may explain products, qualify scope, receive bounded intake/uploads, provide governed price ranges or quote recommendations, and report verified case/payment/status state. They must not expose operator/private data.

## Canonical customer case

A commercially meaningful interaction creates or attaches to one durable `customer_case`. Email is transport, not the system of record.

Required fields include `case_id`, timestamps, `channel_origins`, `conversation_ids`, customer identity/contact, `product_id`, requested outcome, scope, attachments, commercial state, Outlook state, job links, Needs You IDs, stage/history, last customer/operator timestamps, and `authority_created=false`.

Commercial state supports pricing mode, reference offer/band, quote recommendation/reasoning/state, invoice ID/state, payment state/evidence, currency, and amount.

## Case lifecycle

Canonical stages:

`NEW_LEAD -> QUALIFIED -> INTAKE_OPEN -> FILES_RECEIVED_QUARANTINED -> SCOPE_ASSESSED -> PRICE_RECOMMENDED -> QUOTE_READY -> NEEDS_YOU -> INVOICE_DRAFTED -> INVOICE_SEND_APPROVAL -> INVOICE_SENT -> PAYMENT_PENDING -> PAYMENT_VERIFIED -> WORK_QUEUED -> PROCESSING -> REVIEW_READY -> RELEASE_APPROVAL -> DELIVERED -> CLOSED`

Stages may skip only when product rules allow it; they may never move backwards or jump over required authority/evidence gates silently.

## Attachment firewall

`received -> quarantined -> human/routed review -> authorised open/parse -> processed`

Until evidence proves a later state, Vesper may not claim processing, analysis, parsing, opening, generation, invoicing, charging, delivery, release, publication, submission, or fulfilment.

## Commercial intelligence

Current website/product prices are reference offer bands, not universal tariffs. Pricing modes are `known_band`, `scope_sensitive`, and `needs_operator`. Deterministic DIO code computes recommendations from governed offers, scope, complexity, urgency, manual-review burden, and structured comparable evidence. Qwen only explains the result.

## Evidex invoice bridge

Existing invoice/payment artifacts project into the canonical case. `PAID.txt` alone is not verified provider payment. Browser-return success is not payment proof. External invoice sending continues through the existing Outlook/Graph authority rail.

## Outlook ingress and egress

Normalized inbound Outlook messages may attach to an existing case or create a candidate case, quarantine attachments, and create Needs You items. Egress may prepare drafts, but sending remains behind existing authority/lease semantics and must write a send receipt.

## Needs You

Create Needs You when scope exceeds the proven envelope, pricing needs review, invoice send requires approval, attachments need review, fulfilment/release needs authority, or identity/payment/status evidence is ambiguous. It is the shared human decision queue for Telegram operator Vesper and Control Deck.

## Operator briefing contract

“What needs me?” returns a compact state-derived brief ordered by value/urgency. Exact values must come from current case/commercial state.

## Control Deck / mobile contract

Control Deck consumes the same case and Needs You projections and does not maintain a second CRM. Required mobile projection: `Customer | Product | Value | Stage | Needs You`. Drill-down exposes conversation, files/quarantine, scope, quote reasoning, invoice, payment, mail, jobs, receipts, approvals, outputs, and release state.

## Public web Vesper

The public website uses the same Presence Core and customer-case path. It supports continuity, product discovery, scope qualification, bounded quarantine uploads, pricing discussion, quote/intake creation, verified status, and Needs You escalation. It does not create a second commercial database.

## Pocket TTS / Vera

Pocket TTS is a renderer only. It never changes meaning, pricing, scope, state, identity, or authority. Text commercial correctness must be proven before voice output.

## Runtime deployment

The permanent DIO spine remains the always-on Presence/commercial orchestration host. Runtime commercial state must live in persistent state outside disposable worktrees before production customer cases are accepted.

## Acceptance gauntlets

1. Operator role regression: owner-facing operational answers, not public sales copy.
2. Research Integrity transcript regression: bounded scope remains bounded; uploads remain quarantined; no invented processing duration or invoice state.
3. Evidex round trip: intake -> case -> scope -> quote/invoice draft -> Needs You -> approval -> Outlook receipt -> payment evidence -> PAYMENT_VERIFIED.
4. Outlook reconciliation: web start + later email reply remain one case.
5. Mobile operator view: Telegram brief and PWA show the same Needs You/case truth with only approved server-side actions.
6. Voice: only after text/web gauntlets pass, Pocket TTS renders exact approved text without state mutation.

## Slice 2 success definition

A real conversation can become a governed customer case, move through scope/pricing/invoice/mail/payment/job gates without invented state, surface the right decisions to Byron, and expose truthful operator/customer status from one case lineage. Investor market class remains Slice 3; portfolio-wide pricing governance remains Slice 4; Production Studio runtime restoration remains Slice 5 carry-forward issue #52.
