# Vesper Presence Edges on Hugging Face Spaces

## Current canonical status

Hugging Face Docker Spaces are now **compatibility/non-critical Vesper deployments, not the canonical operator Telegram transport**.

The proved operator Telegram path is:

```text
Telegram
→ Cloudflare Presence Gateway
→ staging D1 durable custody
→ outbound-only local reconciler
→ local operator-edge HMAC signing
→ Vesper Presence Core
→ LINGUA + Vesper
→ explicit Telegram reply authority gate
→ Telegram
```

The controlled staging proof is recorded in `docs/VESPER_PERMANENT_PRESENCE_PROOF_2026-08-18.md`.

Older Hugging Face bundles and deployed repo names may still contain the legacy alias `Lilith`. The canonical Presence identity is **Vesper**.

## Known operator compatibility deployment

User-confirmed on 2026-08-18:

```text
HF Space: Byron230686/dio-lilith-operator-wave2
Role: operator compatibility deployment
Canonical Presence identity: Vesper
Legacy deployment alias: Lilith
Critical Telegram transport dependency: false
Runtime state: must be observed, never inferred from the repo name
```

This Space may remain useful as a non-critical operator UI, compatibility witness or future bounded interface. It must not be treated as evidence that Telegram is routed through Hugging Face.

## Legacy edge behavior

The existing HF edge implementation may expose `/health` and `/telegram/webhook`, normalize provider updates and sign them for Presence Core. Public variants may additionally expose WhatsApp and browser chat.

That historical capability is retained for compatibility and diagnostic purposes. It is no longer the preferred operator Telegram architecture because the permanent staging membrane removes the remote-edge-to-local-Core backhaul dependency.

## Trust separation

Public and operator Presence deployments remain separate trust domains. They must not share Telegram bot tokens, webhook secrets, DIO signing keys, operator allowlists or operator tokens.

If an HF operator edge is deliberately re-enabled for a controlled compatibility test, it signs with `DIO_PRESENCE_OPERATOR_SHARED_SECRET`, and the Core independently requires the operator Telegram numeric-ID allowlist before granting operator role.

The canonical Cloudflare Telegram membrane is different: Cloudflare receives only the Telegram provider-authentication secret and a separate transport pull token. It does **not** receive the DIO operator shared secret and does not create DIO signatures.

## Deployment identity

A ZIP filename or deployment instruction is not evidence of which Space is currently serving Vesper. If an HF compatibility deployment is used, record the observed deployment under `state/presence/deployment.json` without secrets.

A compatibility receipt should state explicitly that the deployment is not the canonical Telegram transport unless an authorised architecture change says otherwise.

## Core reachability

Presence Core normally binds to localhost for safety. A remote HF Space cannot use the Core's `127.0.0.1` address. The old topology therefore required an explicitly governed reachable backhaul endpoint or tunnel from the HF edge to Presence Core.

The canonical Cloudflare/D1 topology avoids that requirement. The local reconciler initiates outbound polling and forwards locally to `127.0.0.1:8787` after constructing and signing the DIO Presence envelope.

## Telegram delivery

The hardened Core still owns the bounded Telegram reply action after trusted ingress. External Telegram replies remain fail-closed unless the exact runtime reply rail is enabled and has the required Telegram token/chat metadata.

A prepared reply is not proof of a delivered reply. The permanent Presence proof records actual repeatable Telegram delivery through the Cloudflare/D1/local-signing path.

## Compatibility diagnostics

The existing diagnostic remains useful when intentionally inspecting the HF operator deployment:

```bash
python3 scripts/diagnose_vesper_presence.py \
  --edge-role operator \
  --space-id 'Byron230686/dio-lilith-operator-wave2' \
  --write-receipt
```

The resulting receipt should be interpreted as an HF compatibility/runtime observation, not as the canonical Presence transport receipt.

## LINGUA boundary

Vesper response meaning is registered through LINGUA before channel rendering. Outlook drafts use the same semantic communication rail.

LINGUA may preserve meaning and select a current human-approved translation lane, but it cannot create send permission, consent, spend, payment state, fulfilment release, publication authority or professional judgment.
