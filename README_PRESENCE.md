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

## Vesper Conversational Presence v2

Vesper's conversational cognition is a Lingua-first guide layer behind the existing Presence transport. It does not replace the browser, Cloudflare, D1, reconciler, signature, attachment-quarantine, policy or authority boundaries.

```text
public message
    ↓
Presence conversation custody
    ↓
Lingua conversational resolver
    ├─ deterministic conversational primitives
    ├─ bounded same-conversation recall
    ├─ verified read-only BEAST semantic-crystal reuse
    ├─ governed ATLAS + route-contract product knowledge
    ├─ bounded Ollama-compatible synthesis fallback
    └─ deterministic safe fallback
    ↓
ordinary conversation reply
    or
explicit typed action proposal
    ↓
deterministic action bridge
    ↓
authorize()
    ↓
existing held side-effect path
```

The governing invariant is:

```text
LANGUAGE != AUTHORITY
```

A model, Lingua answer frame, semantic crystal, recalled turn or fluent Vesper sentence may understand, explain, compare, clarify, infer and propose. None of those language paths can create send, spend, payment, publication, fulfilment, identity, professional, legal or release authority.

The conversational guide is **disabled by default**. The machine-readable rollout policy lives in `config/presence.json`. Controlled testing enables it with:

```bash
DIO_PRESENCE_CONVERSATIONAL_GUIDE=1 \
PYTHONPATH=. PYTHONNOUSERSITE=1 \
python -m pytest -q tests/test_vesper_conversational_presence_v2.py
```

Provider synthesis reuses the existing Ollama-compatible transport. A fast Qwen-class or equivalent instruction model may be selected through `OLLAMA_MODEL` without giving the provider tools or mutation authority. Provider outage, timeout, malformed JSON or validation failure degrades to Lingua/local/fallback behavior rather than creating authority or breaking the public rail.

Conversation continuity is bounded. Recent turns are stored per Presence conversation and capped by policy. Direct recall only consults the same conversation's bounded user-turn window. It does not search other visitors' conversations or grant a provider unrestricted repository memory.

Product meaning is federated from existing DIO truth rather than a new chatbot catalogue. The conversational knowledge layer uses the ATLAS incarnation crosswalk, product-class route contract and bounded public enrichment. This preserves distinctions such as a named incarnation being explainable while its route remains non-auto-promotable.

Verified BEAST semantic crystals are read-only in the live conversational path. A provider answer cannot promote itself into a crystal. Automatic crystal promotion is disabled.

Before rollout, the focused regression wall is:

```bash
PYTHONPATH=. PYTHONNOUSERSITE=1 python -m pytest -q \
  tests/test_vesper_conversation_state.py \
  tests/test_vesper_lingua_conversation.py \
  tests/test_vesper_conversation_knowledge.py \
  tests/test_vesper_conversation_crystals.py \
  tests/test_vesper_conversation_provider.py \
  tests/test_vesper_conversation_action_bridge.py \
  tests/test_vesper_conversational_presence_v2.py \
  tests/test_presence_pa.py \
  tests/test_presence_wave2_identity.py
```

The broader safety regression is:

```bash
PYTHONPATH=. PYTHONNOUSERSITE=1 \
python -m pytest -q tests -k 'presence or lingua or vesper'
```

A green conversational test does not itself authorize production rollout. Production activation remains an explicit operator deployment decision after the focused and broader regression walls are green.

## Authority boundary

DIO Presence may receive, classify, preserve semantic lineage, quarantine, create held intakes, expose explicitly bound minimal status, draft customer-facing responses and surface human attention.

It cannot silently spend money, create or refund payments, release fulfilment, approve educator/research/HR work, send arbitrary outbound campaigns, change DIO control policy, parse customer files automatically, expose unbound customer/order records or turn public-channel identity into operator authority.
