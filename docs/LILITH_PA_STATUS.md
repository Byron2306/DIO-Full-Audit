# Vesper Presence Status

> Legacy file name retained for compatibility. **Vesper** is now the public/operator persona. **Lilith** remains the internal deployment codename and accepted command alias.

Updated: 2026-08-10

DIO Presence Wave 2 is installed as a separated public/operator system. The public side remains a bounded concierge for HOMS, Evidex, Sophia, VAMP and Document Studio. The operator side is a read-only PA surface over the DIO operating spine.

C4 adds a shared cross-channel Conversation Context layer beneath the persona. Outlook, Telegram, WhatsApp and web-chat interactions can now project into the same bounded context model without granting the conversation layer truth or execution authority.

## What Vesper Can See

`operator_summary()` returns `dio.presence.operator_brief.v1` and reads:

- product jobs from `state/product_jobs`, `state/sophia_jobs`, `state/vamp_jobs` and future `state/document_studio_jobs`
- Outlook mail intents, pending approvals and delivery drafts
- sandbox and live commerce orders, including paid-but-unreleased states
- Market Command campaigns, content approvals and measurements
- local lead records
- recorded incidents
- Presence `Needs You` actions

C4 additionally creates canonical conversation artifacts under:

```text
state/conversation_context/CTX-*.json
state/conversation_context/INDEX.json
```

These artifacts may carry thread state, observed questions, requested actions, latest inbound excerpt and derived tone/style hints. They are expression context only.

The local CLI entry point remains:

```bash
./.venv/bin/python scripts/manage_presence.py summary
```

Operator Telegram phrases still work. The preferred persona invocation is now Vesper:

- `morning vesper` or `system summary`
- `market command status`
- `payment summary` or `paid orders`
- `pending mail`
- `work queue` or `delivery drafts`
- `needs you`

`morning lilith`, `hi lilith` and `hey lilith` remain accepted legacy aliases.

## Why the Rename Is Soft

Existing Hugging Face Space names, Telegram deployment identifiers, environment secrets and historical documentation may still contain `Lilith`. C4 deliberately does not perform a destructive repo-wide or deployment-wide rename.

The naming boundary is now:

```text
Public / operator persona: Vesper
Legacy deployment codename: Lilith
Canonical subsystem: DIO Presence
Canonical memory substrate: DIO Conversation Context
```

This lets the public-facing identity become professional without breaking working infrastructure.

## Authority Boundary

Vesper remains deliberately bounded. She can summarise, classify, prepare intake, preserve conversation context and create review-required state. She cannot:

- send arbitrary mail
- release fulfilment
- publish campaigns
- approve professional work
- spend money
- process or trust attachments
- expose public customer status without an operator-created identity binding
- turn conversation tone, requests or assertions into verified commercial facts
- manufacture consent, scope, budget, payment state, identity or execution authority

Telegram replies sent directly by the Presence bridge are journalled as `sent` only after Telegram reports success. Replies not externally confirmed remain `prepared` and do not count as external thread history.

Those restrictions are enforced across Presence policy, Conversation Context authority flags and the downstream commercial expression layer.

## Document Studio Route

Document Studio remains a first-class public route for technical editing, translation, proofreading, document formatting, templates, DOCX/PDF/PPTX delivery and Afrikaans, isiZulu, Sesotho and Setswana language work.

The route captures requests as held intakes. It does not promise certified translation, professional approval or delivery until the normal DIO gates are satisfied.
