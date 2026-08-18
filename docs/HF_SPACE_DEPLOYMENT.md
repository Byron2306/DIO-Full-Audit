# Vesper Presence Edges on Hugging Face Spaces

DIO Presence uses Hugging Face Docker Spaces as **non-canonical edges**. The canonical Presence identity is **Vesper**. Older bundle filenames and deployed repo names may still contain `Lilith` for compatibility.

The edge terminates public or operator Telegram webhooks and forwards normalized signed ingress to the separately trusted DIO Presence Core. The Space does not own canonical leads, orders, payments, jobs, approval state or professional authority.

## Known operator deployment

User-confirmed on 2026-08-18:

```text
HF Space: Byron230686/dio-lilith-operator-wave2
Role: operator
Canonical Presence identity: Vesper
Legacy deployment alias: Lilith
Runtime state: must be observed, never inferred from the repo name
```

The Hugging Face repository metadata identifies this as a Docker Space. Its repository metadata was last updated on 2026-08-09, so it must not be assumed to contain later Vesper/LINGUA hardening without a current runtime or source observation.

## Routes

A Presence edge is expected to expose `/health` and `/telegram/webhook`. The public edge may additionally expose `/whatsapp/webhook` and browser chat.

## Trust separation

Public and operator Presence deployments are separate trust domains. They must not share Telegram bot tokens, webhook secrets, DIO signing keys, operator allowlists or operator tokens.

The operator edge signs with `DIO_PRESENCE_OPERATOR_SHARED_SECRET`. The Core independently requires the operator Telegram numeric-ID allowlist before granting operator role.

## Live deployment identity

A ZIP filename or deployment instruction is not evidence of which Space is currently serving Vesper. After deployment or any rebuild, record the observed deployment under `state/presence/deployment.json` without secrets:

```json
{
  "schema": "dio.vesper.presence_deployment.v1",
  "hf_space_id": "Byron230686/dio-lilith-operator-wave2",
  "edge_role": "operator",
  "edge_url": "https://byron230686-dio-lilith-operator-wave2.hf.space",
  "space_sha": "<observed deployed revision>",
  "telegram_webhook_path": "/telegram/webhook",
  "core_url": "<reachable Presence Core base URL or governed backhaul endpoint>",
  "observed_at": "<UTC timestamp>"
}
```

The URL above is the standard Hugging Face Space subdomain derived from the repo ID. Reachability still has to be observed.

## Core reachability

Presence Core normally binds to localhost for safety. A remote HF Space cannot use the Core's `127.0.0.1` address. Production therefore requires an explicitly governed reachable backhaul endpoint or tunnel from the HF edge to Presence Core. Reachability is transport, not authority; signed ingress still applies.

## Telegram delivery

The hardened Core owns the bounded Telegram reply action after trusted ingress. External Telegram replies are fail-closed unless the exact runtime reply rail is enabled and has the correct Telegram token/chat metadata.

```text
Telegram
→ operator HF edge
→ operator-signed ingress
→ Vesper Presence Core
→ LINGUA binds response meaning
→ external-reply authority gate
→ Telegram send
```

A prepared reply is not proof of a delivered reply.

## Operator-edge diagnostic

For the known operator Space:

```bash
python3 scripts/diagnose_vesper_presence.py \
  --edge-role operator \
  --space-id 'Byron230686/dio-lilith-operator-wave2' \
  --write-receipt
```

The diagnostic derives the standard Space URL when `--edge-url` is omitted and checks, without printing secrets:

- exact Space identity and role;
- Core health;
- HF edge `/health`;
- HF Space metadata/runtime when API access permits it;
- operator shared-secret presence on Core;
- operator Telegram allowlist presence;
- Core Telegram reply-switch state;
- Core Telegram token presence;
- Telegram bot identity;
- Telegram webhook target, pending updates and last reported webhook error.

## Public-edge diagnostic

Use the same script with `--edge-role public` and the public Space ID. Public and operator receipts are written separately.

## LINGUA boundary

Vesper response meaning is registered through LINGUA before channel rendering. Outlook drafts use the same semantic communication rail.

LINGUA may preserve meaning and select a current human-approved translation lane, but it cannot create send permission, consent, spend, payment state, fulfilment release, publication authority or professional judgment.
