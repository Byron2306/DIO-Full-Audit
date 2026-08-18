# DIO Presence · Wave 2 — Vesper

**Vesper is DIO's public interaction and communication layer, not DIO's authority.**

`Lilith` remains a legacy deployment/bundle alias only where older Hugging Face artifacts still carry that name. New semantic communication, telemetry and deployment receipts use the canonical identity **Vesper**.

Wave 2 provides Telegram, WhatsApp and browser-chat ingress through a non-canonical public edge, with signed delivery to the separately trusted DIO Presence Core.

## Implemented

- Telegram public concierge, voice-note transcription hook, photo/document intake.
- WhatsApp Cloud API webhook verification, signed webhook validation, text/audio/document/image intake, bounded text replies.
- Public Vesper web chat with signed anonymous session cookies, per-session rate limits, campaign hints, and no identity authority by default.
- Binary uploads are downloaded at the untrusted edge, bounded by size, SHA-256 hashed, extension/MIME/magic checked, then sent to DIO and written as `content.blob` in a quarantine directory.
- Quarantined uploads are **not parsed, rendered, executed, indexed, or passed to models automatically**.
- Public customer status is locked unless an operator explicitly binds a conversation to one or more exact local DIO order IDs.
- Bound status disclosure is deliberately minimal: order ID, payment state, and whether fulfilment has been released.
- Public and operator Presence edges remain separate cryptographic trust domains.
- Product intake remains human-held.
- Vesper replies and governed Outlook mail register shared LINGUA semantic lineage before channel rendering.

## Trust model

```text
Telegram / WhatsApp / Web Chat
             │
             ▼
      PUBLIC VESPER EDGE
       non-canonical state
             │
      signed public ingress
             ▼
        DIO PRESENCE CORE
             │
 LINGUA / classify / bind / quarantine
             │
     ┌───────┴────────┐
     ▼                ▼
  Needs You       product intake
     │                │
     └───────┬────────┘
             ▼
       HUMAN AUTHORITY
```

The operator Telegram edge remains a **separate bot/deployment** using a different signing key. WhatsApp and web chat cannot become operator channels.

## LINGUA public communicator

Telegram, WhatsApp, web chat, voice, email and Outlook are rendering surfaces over shared governed meaning rather than independent linguistic authorities.

The communication lifecycle binds subject/body meaning, source/requested language, channel/audience, product context, source hash/version and explicit authority boundaries.

LINGUA may reuse a current human-approved translation lane. A new translation does not become approved merely because a model can produce it.

LINGUA does **not** create consent, send authority, payment state, fulfilment authority, professional judgment, publication authority or spend authority.

## Telegram reply truth

The hardened Presence Core owns the bounded Telegram reply action after trusted ingress. External replies are fail-closed unless the runtime permits that exact reply rail. A healthy reasoning path therefore does **not** prove that the public bot is reachable or that Telegram delivery is enabled.

## Deployment identity receipt

Deployment instructions are not a live deployment identity. Record the actual public edge in `state/presence/deployment.json` without secrets. It should bind at least the HF Space ID, public URL, observed Space SHA, public edge role, Telegram webhook path, governed Core/backhaul URL and observation timestamp.

Run the redacted live diagnostic:

```bash
python3 scripts/diagnose_vesper_presence.py --write-receipt
```

If the Space has not yet been recorded:

```bash
python3 scripts/diagnose_vesper_presence.py \
  --space-id 'namespace/space-name' \
  --public-url 'https://space-subdomain.hf.space' \
  --write-receipt
```

It checks Core reachability, reply-gate state, required secret presence, Telegram bot identity/webhook information, public-edge health and the recorded HF Space identity without printing credentials.

## Safe upload path

```text
provider media id
→ provider-authenticated download
→ edge size limit
→ SHA-256
→ signed DIO ingress
→ extension + MIME + file-signature checks
→ random attachment id
→ content.blob
→ metadata receipt
→ Needs You
```

Allowed public types remain PDF, DOCX, XLSX, PPTX, CSV, TXT, PNG and JPEG. Active/macro/archive/script formats remain rejected. Quarantined uploads are not parsed or trusted automatically.

## Identity-bound status

A phone number, Telegram ID, web-chat cookie or order number alone is not sufficient authority. Public status disclosure remains locked until an operator explicitly binds the conversation to exact local DIO order identity.

## Installation

```bash
cd ~/DIO
source .venv/bin/activate
python -m pytest -q tests/test_presence_*.py
python3 scripts/serve_presence_bridge.py
```

Older deployment bundles may still be named `DIO_Lilith_Public_HF_Space_Wave2.zip` and `DIO_Lilith_Operator_HF_Space_Wave2.zip`. Those filenames are compatibility artifacts, not the canonical Presence identity.

## Authority boundary

DIO Presence may receive, classify, preserve semantic lineage, quarantine, create held intakes, expose explicitly bound minimal status, draft customer-facing responses and surface human attention.

It cannot silently spend money, create or refund payments, release fulfilment, approve educator/research/HR work, send arbitrary outbound campaigns, change DIO control policy, parse customer files automatically, expose unbound customer/order records or turn public-channel identity into operator authority.
