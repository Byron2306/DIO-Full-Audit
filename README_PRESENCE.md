# DIO Presence · Vesper

**Vesper is DIO's public/operator interaction persona, not DIO's authority.**

`Lilith` remains the legacy deployment codename and accepted invocation alias so existing Hugging Face Space names, Telegram bot deployments, secrets and operator habits do not break.

DIO Presence is a multi-channel public edge with Telegram, WhatsApp Cloud API and browser chat, quarantine-only document intake, explicitly verified public status lookup, a separated read-only operator surface, and C4 cross-channel Conversation Context.

## Implemented

- Telegram public concierge, voice-note transcription hook, photo/document intake.
- WhatsApp Cloud API webhook verification, signed webhook validation, text/audio/document/image intake, bounded text replies.
- Public Vesper web chat with signed anonymous session cookies, per-session rate limits, campaign hints, and no identity authority by default.
- Binary uploads are downloaded at the untrusted edge, bounded by size, SHA-256 hashed, extension/MIME/magic checked, then sent to DIO and written as `content.blob` in a quarantine directory.
- Quarantined uploads are **not parsed, rendered, executed, indexed, or passed to models automatically**.
- Public customer status is locked unless an operator explicitly binds a conversation to one or more exact local DIO order IDs.
- Bound status disclosure is deliberately minimal: order ID, payment state, and whether fulfilment has been released. Provider, amount, email, and unrelated orders are not disclosed.
- Public and operator Presence remain separate cryptographic trust domains. Only the operator Telegram edge plus server-side Telegram allowlist can acquire `operator` role.
- Product intake remains human-held. No public message automatically releases fulfilment, sends arbitrary outbound mail, approves professional work, changes policy, or spends money.
- Outlook and Presence now project into `dio.conversation_context.v1` for bounded thread awareness.
- Conversation Context may shape wording and response order but cannot establish commercial facts, consent, scope, budget, payment state, identity or execution authority.
- Telegram replies are recorded as `sent` only after the Telegram API confirms delivery acceptance; otherwise they remain `prepared`.

## Trust model

```text
Telegram / WhatsApp / Web Chat
             │
             ▼
      PUBLIC PRESENCE EDGE
       Vesper persona
       non-canonical state
             │
      signed public ingress
             ▼
        DIO PRESENCE CORE
             │
   classify / bind / quarantine
             │
     ┌───────┴────────┐
     ▼                ▼
  Needs You       product intake
     │                │
     └───────┬────────┘
             ▼
     Conversation Context
       expression-only
             │
             ▼
       HUMAN AUTHORITY
```

Operator Vesper is a **separate Telegram bot/deployment** using a different signing key. Existing deployments may still be named Lilith. WhatsApp and web chat cannot become operator channels under the current trust model.

## Conversation Context

C4 introduces a shared context substrate beneath Outlook and Presence:

```text
state/conversation_context/CTX-*.json
state/conversation_context/INDEX.json
```

The context can record:

- received inbound turns;
- actually sent outbound turns;
- prepared-but-unsent replies;
- thread state;
- observed questions and request-like statements;
- latest requested action;
- latest inbound excerpt; and
- derived tone/style hints.

It cannot become commercial truth or grant authority.

Reconcile manually with:

```bash
python scripts/reconcile_conversation_context.py
```

The commercial orchestrator performs the same reconciliation before each normal commercial projection.

For a bound Outlook lead whose thread is waiting for DIO, prepare a context-aware review-required reply with:

```bash
python scripts/prepare_conversation_reply.py <LEAD_ID>
```

This creates a normal DIO mail intent with approval pending. It does not send mail.

## Safe upload path

```text
provider media id
→ provider-authenticated download
→ edge size limit
→ SHA-256
→ signed DIO ingress
→ extension + MIME + file-signature checks
→ random attachment id
→ content.blob (0600 where supported)
→ metadata receipt
→ Needs You
```

Allowed public types: PDF, DOCX, XLSX, PPTX, CSV, TXT, PNG, JPEG.

Active/macro/archive/script formats including EXE, JS, HTML, SVG, ZIP, DOCM, XLSM and PPTM are rejected.

Default DIO public attachment ceiling: **8 MiB**, deliberately below Telegram's provider-side download maximum. Change only after reviewing ingress and reverse-proxy limits.

## Identity-bound status

A phone number, Telegram ID, web-chat cookie, or order number alone is **not** sufficient authority.

When a public user requests status without a binding, Vesper creates a `Needs You` item. An operator verifies the relationship out-of-band and creates an exact conversation→order binding:

```bash
python3 scripts/manage_presence.py conversations
python3 scripts/manage_presence.py bind-status \
  --conversation CONV-ABC123 \
  --order DIO-ORDER-001 \
  --method "matched caller to payment receipt and confirmed contact"
```

Revoke at any time:

```bash
python3 scripts/manage_presence.py revoke-binding --conversation CONV-ABC123
```

The same operation is available through the operator-token-protected Presence API.

## Installation

```bash
unzip DIO_Presence_Wave2.zip
cd DIO_Presence_Wave2
python3 install_presence.py --target ~/DIO

cd ~/DIO
source .venv/bin/activate
python -m pytest -q tests/test_presence_*.py
python3 scripts/serve_presence_bridge.py
```

The Wave 2 installer backs up overwritten Presence-owned files into `.dio_presence_backups/<timestamp>/`.

## Hugging Face

Existing Spaces named `DIO_Lilith_Public_HF_Space_Wave2` and `DIO_Lilith_Operator_HF_Space_Wave2` may remain unchanged. Vesper is a persona-level soft rename, not a destructive deployment rename.

Store credentials in Space Secrets, never in the repository. Public and operator deployments continue to use different Presence shared secrets.

See `docs/HF_SPACE_DEPLOYMENT.md`, `docs/WHATSAPP_ONBOARDING.md`, `docs/TELEGRAM_ONBOARDING.md`, `docs/IDENTITY_BINDING.md`, and `docs/CONVERSATION_CONTEXT_V1.md`.

## Authority boundary

DIO Presence can receive, classify, quarantine, create held intakes, expose explicitly bound minimal status, prepare customer-facing responses, preserve bounded conversation context, and surface human attention.

It cannot silently:

- spend money,
- create/refund payments,
- release fulfilment,
- approve educator/research/HR work,
- send arbitrary outbound campaigns,
- change DIO control policy,
- parse customer files automatically,
- expose unbound customer/order records,
- turn public WhatsApp or web-chat identity into operator authority,
- turn conversation wording into verified customer facts,
- infer consent, scope, budget or payment authority from conversational tone.
