# Vesper Public Edge on Hugging Face Spaces

DIO Presence uses a public Docker Space as a **non-canonical edge** for Telegram, WhatsApp and browser chat. The canonical Presence identity is **Vesper**. Older bundle filenames may still contain `Lilith` for compatibility.

The Space terminates public webhooks and forwards normalized signed ingress to the separately trusted DIO Presence Core. The Space does not own canonical leads, orders, payments, jobs, approval state or professional authority.

## Public routes

The public edge is expected to expose `/health`, `/telegram/webhook`, `/whatsapp/webhook` and `/`.

## Trust separation

Public and operator Presence deployments are separate trust domains. They must not share Telegram bot tokens, webhook secrets, DIO signing keys, operator allowlists or operator tokens.

## Live deployment identity is mandatory

A ZIP filename or deployment instruction is not evidence of which Space is currently serving Vesper. After deployment or any rebuild, record the observed public deployment under `state/presence/deployment.json` without secrets:

```json
{
  "schema": "dio.vesper.presence_deployment.v1",
  "hf_space_id": "namespace/space-name",
  "public_url": "https://space-subdomain.hf.space",
  "space_sha": "<observed deployed revision>",
  "edge_role": "public",
  "telegram_webhook_path": "/telegram/webhook",
  "core_url": "<reachable Presence Core base URL or governed backhaul endpoint>",
  "observed_at": "<UTC timestamp>"
}
```

## Core reachability

Presence Core normally binds to localhost for safety. A remote HF Space cannot use the Core's `127.0.0.1` address. Production therefore requires an explicitly governed reachable backhaul endpoint or tunnel from the HF edge to Presence Core. Reachability is transport, not authority; signed ingress still applies.

## Telegram delivery

The hardened Core owns the bounded Telegram reply action after trusted ingress. External Telegram replies are fail-closed unless the exact runtime reply rail is enabled and has the correct Telegram token/chat metadata.

```text
message received
→ signed ingress accepted
→ Vesper classifies and prepares reply
→ LINGUA binds meaning
→ external-reply authority gate
→ Telegram send
```

A prepared reply is not proof of a delivered reply.

## Health diagnostic

Run:

```bash
python3 scripts/diagnose_vesper_presence.py --write-receipt
```

If the live deployment has not yet been recorded:

```bash
python3 scripts/diagnose_vesper_presence.py \
  --space-id 'namespace/space-name' \
  --public-url 'https://space-subdomain.hf.space' \
  --write-receipt
```

The diagnostic checks, without printing secrets: recorded Space identity/public URL, Core health, public edge health, HF Space metadata when an exact repo ID is known, Telegram bot identity/webhook target, pending updates/recent webhook error, Presence shared-secret presence, and Core Telegram reply-switch state.

## LINGUA boundary

Vesper public response meaning is registered through LINGUA before channel rendering. Outlook drafts use the same semantic communication rail.

LINGUA may preserve meaning and select a current human-approved translation lane, but it cannot create send permission, consent, spend, payment state, fulfilment release, publication authority or professional judgment.
