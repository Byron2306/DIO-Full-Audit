# LILITH PA Status

Updated: 2026-08-09

Lilith Presence Wave 2 is installed as a separated public/operator system. The public side remains a bounded concierge for HOMS, Evidex, Sophia, VAMP and Document Studio. The operator side is now a read-only PA surface over the DIO operating spine.

## What The PA Can See

`operator_summary()` now returns `dio.presence.operator_brief.v1` and reads:

- product jobs from `state/product_jobs`, `state/sophia_jobs`, `state/vamp_jobs` and future `state/document_studio_jobs`
- Outlook mail intents, pending approvals and delivery drafts
- sandbox and live commerce orders, including paid-but-unreleased states
- Market Command campaigns, content approvals and measurements
- local lead records
- recorded incidents
- Presence `Needs You` actions

The local CLI entry point is:

```bash
./.venv/bin/python scripts/manage_presence.py summary
```

Operator Telegram phrases now route to focused read-only briefs:

- `morning lilith` or `system summary`
- `market command status`
- `payment summary` or `paid orders`
- `pending mail`
- `work queue` or `delivery drafts`
- `needs you`

## Current Real Brief

The current local summary reports:

- 5 jobs: Evidex 1, HOMS 1, Sophia 1, VAMP 2
- 5 delivery drafts ready
- 2 pending mail intents requiring approval
- 2 paid PayPal orders, including 1 live paid order
- 2 paid orders still unreleased
- 9 Market Command campaigns, 4 active or approved, 8 released
- 1 local lead record
- 1 recorded incident

The most important operator actions are delivery drafts, paid-unreleased orders and two pending outreach/RFQ mail intents.

## Authority Boundary

Lilith PA is deliberately read-only. She can summarise, classify, prepare intake and create review-required state. She cannot:

- send mail
- release fulfilment
- publish campaigns
- approve professional work
- spend money
- process or trust attachments
- expose public customer status without an operator-created identity binding

Those restrictions are enforced in `presence_core/policy.py` and repeated in the returned operator brief.

## Document Studio Route

Document Studio is now a first-class public route for technical editing, translation, proofreading, document formatting, templates, DOCX/PDF/PPTX delivery and Afrikaans, isiZulu, Sesotho and Setswana language work.

The route captures requests as held intakes. It does not promise certified translation, professional approval or delivery until the normal DIO gates are satisfied.
