# DIO Presence · Wave 2

**Lilith is DIO's public interaction layer, not DIO's authority.**

Wave 2 turns the Wave 1 Telegram concierge into a multi-channel public edge with WhatsApp Cloud API, a browser chat surface, quarantine-only document intake, and explicitly verified public status lookup.

## Implemented

- Telegram public concierge, voice-note transcription hook, photo/document intake.
- WhatsApp Cloud API webhook verification, signed webhook validation, text/audio/document/image intake, bounded text replies.
- Public Lilith web chat with signed anonymous session cookies, per-session rate limits, campaign hints, and no identity authority by default.
- Binary uploads are downloaded at the untrusted edge, bounded by size, SHA-256 hashed, extension/MIME/magic checked, then sent to DIO and written as `content.blob` in a quarantine directory.
- Quarantined uploads are **not parsed, rendered, executed, indexed, or passed to models automatically**.
- Public customer status is locked unless an operator explicitly binds a conversation to one or more exact local DIO order IDs.
- Bound status disclosure is deliberately minimal: order ID, payment state, and whether fulfilment has been released. Provider, amount, email, and unrelated orders are not disclosed.
- Public and operator Lilith remain separate cryptographic trust domains. Only the operator Telegram edge plus server-side Telegram allowlist can acquire `operator` role.
- Product intake remains human-held. No public message automatically releases fulfilment, sends outbound mail, approves professional work, changes policy, or spends money.

## Trust model

```text
Telegram / WhatsApp / Web Chat
             │
             ▼
      PUBLIC LILITH EDGE
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
       HUMAN AUTHORITY
```

Operator Lilith is a **separate Telegram bot/deployment** using a different signing key. WhatsApp and web chat cannot become operator channels in Wave 2.

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

Allowed public types in Wave 2: PDF, DOCX, XLSX, PPTX, CSV, TXT, PNG, JPEG.

Active/macro/archive/script formats including EXE, JS, HTML, SVG, ZIP, DOCM, XLSM and PPTM are rejected.

Default DIO public attachment ceiling: **8 MiB**, deliberately below Telegram's provider-side download maximum. Change only after reviewing your ingress/reverse-proxy limits.

## Identity-bound status

A phone number, Telegram ID, web-chat cookie, or order number alone is **not** sufficient authority.

When a public user requests status without a binding, Lilith creates a `Needs You` item. An operator verifies the relationship out-of-band and creates an exact conversation→order binding:

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

Deploy `DIO_Lilith_Public_HF_Space_Wave2.zip` as the public Docker Space. Store credentials in Space Secrets, never in the repository.

Deploy `DIO_Lilith_Operator_HF_Space_Wave2.zip` separately if you want PA Lilith. It uses a different Telegram bot and `DIO_PRESENCE_OPERATOR_SHARED_SECRET`.

See `docs/HF_SPACE_DEPLOYMENT.md`, `docs/WHATSAPP_ONBOARDING.md`, `docs/TELEGRAM_ONBOARDING.md`, and `docs/IDENTITY_BINDING.md`.

## Wave 2 authority boundary

DIO Presence can receive, classify, quarantine, create held intakes, expose explicitly bound minimal status, draft customer-facing responses, and surface human attention.

It cannot silently:

- spend money,
- create/refund payments,
- release fulfilment,
- approve educator/research/HR work,
- send arbitrary outbound campaigns,
- change DIO control policy,
- parse customer files automatically,
- expose unbound customer/order records,
- turn public WhatsApp or web-chat identity into operator authority.
