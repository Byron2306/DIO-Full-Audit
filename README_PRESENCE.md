# DIO Presence · Wave 2 — Vesper

**Vesper is DIO's public interaction and communication layer, not DIO's authority.**

`Lilith` remains a legacy deployment/bundle alias only where older Hugging Face artifacts still carry that name. New semantic communication, telemetry and deployment receipts use the canonical identity **Vesper**.

## Canonical operator Telegram transport

The proved operator Telegram transport is now the Cloudflare Presence custody membrane with outbound-only local reconciliation:

```text
Telegram
   ↓ provider webhook authentication
Cloudflare Presence Gateway
   ↓ exact raw provider update
staging D1 durable custody
   ↓ outbound-only local polling
local Presence reconciler
   ↓ local envelope construction + operator-edge HMAC signing
DIO Presence Core on 127.0.0.1:8787
   ↓
LINGUA / Vesper / authority gates
   ↓
Telegram reply
```

Hugging Face Presence Spaces remain compatibility/non-critical deployments. They are no longer the canonical operator Telegram transport dependency.

The controlled staging execution proof is recorded in `docs/VESPER_PERMANENT_PRESENCE_PROOF_2026-08-18.md`.

## Implemented

- Telegram operator ingress through the Cloudflare/D1 custody membrane with local DIO signing.
- Legacy/compatibility Telegram, WhatsApp and browser-chat edge implementations remain available for bounded use and further migration.
- Telegram photo/document/voice custody can be reconciled locally, preserving the quarantine-first attachment boundary.
- WhatsApp Cloud API webhook verification, signed webhook validation, text/audio/document/image intake, bounded text replies in the existing edge implementation.
- Public Vesper web chat with signed anonymous session cookies, per-session rate limits, campaign hints, and no identity authority by default in the existing edge implementation.
- Quarantined uploads are **not parsed, rendered, executed, indexed, or passed to models automatically**.
- Public customer status is locked unless an operator explicitly binds a conversation to one or more exact local DIO order IDs.
- Bound status disclosure is deliberately minimal: order ID, payment state, and whether fulfilment has been released.
- Public and operator Presence trust domains remain separate.
- Product intake remains human-held.
- Vesper replies and governed Outlook mail register shared LINGUA semantic lineage before channel rendering.

## Trust model

For the proved operator Telegram path:

```text
Telegram
   │
   ▼
Cloudflare provider-authenticated custody
   │
   ▼
D1 pending event
   │
   ▼ outbound-only pull
local reconciler
   │ local DIO signing
   ▼
DIO Presence Core
   │
LINGUA / classify / bind / quarantine
   │
   ├───────────────┐
   ▼               ▼
Needs You      product intake
   │               │
   └───────┬───────┘
           ▼
     HUMAN AUTHORITY
```

Cloudflare receives the Telegram webhook-authentication secret and the separate edge pull token. It does **not** receive the DIO public/operator shared signing secrets and therefore cannot create DIO Presence authority.

WhatsApp and web chat cannot become operator channels merely because they share Vesper's communication layer.

## LINGUA public communicator

Telegram, WhatsApp, web chat, voice, email and Outlook are rendering surfaces over shared governed meaning rather than independent linguistic authorities.

The communication lifecycle binds subject/body meaning, source/requested language, channel/audience, product context, source hash/version and explicit authority boundaries.

LINGUA may reuse a current human-approved translation lane. A new translation does not become approved merely because a model can produce it.

LINGUA does **not** create consent, send authority, payment state, fulfilment authority, professional judgment, publication authority or spend authority.

## Telegram reply truth

The hardened Presence Core owns the bounded Telegram reply action after trusted ingress. External replies are fail-closed unless the runtime permits that exact reply rail.

The permanent staging proof goes beyond a prepared-reply claim: multiple real Telegram provider updates were durably queued, locally signed, accepted by Presence Core and answered through the governed reply rail.

## Deployment identity receipts

Deployment instructions are not live deployment evidence.

For the canonical operator Telegram path, use the Cloudflare/D1 proof receipt:

```text
docs/VESPER_PERMANENT_PRESENCE_PROOF_2026-08-18.md
```

If a Hugging Face compatibility deployment is intentionally inspected, its diagnostic/receipt must state that it is non-canonical unless an authorised architecture change says otherwise.

The existing redacted diagnostic remains available for compatibility/runtime inspection:

```bash
python3 scripts/diagnose_vesper_presence.py --write-receipt
```

## Safe upload path

```text
provider media id
→ provider-authenticated custody/download path
→ size limit
→ SHA-256
→ locally signed DIO ingress
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
python3 scripts/sync_vesper_presence_edge.py --watch
```

Older deployment bundles may still be named `DIO_Lilith_Public_HF_Space_Wave2.zip` and `DIO_Lilith_Operator_HF_Space_Wave2.zip`. Those filenames are compatibility artifacts, not the canonical Presence identity or operator Telegram topology.

## Authority boundary

DIO Presence may receive, classify, preserve semantic lineage, quarantine, create held intakes, expose explicitly bound minimal status, draft customer-facing responses and surface human attention.

It cannot silently spend money, create or refund payments, release fulfilment, approve educator/research/HR work, send arbitrary outbound campaigns, change DIO control policy, parse customer files automatically, expose unbound customer/order records or turn public-channel identity into operator authority.
