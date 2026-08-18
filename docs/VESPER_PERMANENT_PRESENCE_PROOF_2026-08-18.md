# Vesper Permanent Presence Transport Proof

**Date:** 2026-08-18  
**Status:** CONTROLLED STAGING EXECUTION PROVED  
**Scope:** Telegram operator Presence transport only  
**Canonical transport role:** provider-authenticated durable custody with local DIO signing authority

## Claim

DIO Vesper has a repeatable operator Telegram path that no longer depends on a public inbound laptop tunnel or Hugging Face Space transport.

Canonical proved path:

```text
Telegram
  ↓ Telegram webhook secret authentication
Cloudflare Presence Worker
  ↓ raw provider update
Cloudflare D1 durable custody
  ↓ outbound-only polling
local DIO Presence reconciler
  ↓ local canonicalisation
  ↓ local operator-edge HMAC signing
DIO Presence Core on 127.0.0.1:8787
  ↓ LINGUA + Vesper routing
  ↓ explicit Telegram reply authority gate
Telegram reply
```

## Authority boundary

Cloudflare is transport and custody only.

The Cloudflare Worker:

- authenticates Telegram webhook delivery;
- stores the exact raw Telegram update in D1;
- exposes the event only through the separately authenticated pull rail;
- does not receive `DIO_PRESENCE_OPERATOR_SHARED_SECRET`;
- does not create DIO operator signatures;
- does not gain business authority;
- does not gain external reply authority.

The local reconciler:

- pulls provider-authenticated Telegram events outbound from the laptop;
- transforms the Telegram update into the existing DIO Presence envelope;
- signs the exact local envelope using the local operator-edge shared secret;
- forwards only to local Presence Core.

Presence Core remains the authority boundary for ingress verification and bounded Telegram replies.

## Deployment receipt

Observed Cloudflare staging health after deployment:

```json
{
  "ok": true,
  "service": "dio-presence-edge-buffer",
  "version": "1.1.0",
  "storage": "cloudflare_d1",
  "signature_verification": "deferred_to_dio_presence_core",
  "telegram_provider_authentication": true,
  "telegram_signing_authority": "local_dio_presence_reconciler_only",
  "business_authority": false,
  "external_reply_authority": false
}
```

Observed local Presence Core health:

```json
{
  "ok": true,
  "service": "dio-presence-bridge",
  "version": "2.0.0",
  "presence_identity": "Vesper",
  "automatic_external_actions": false,
  "telegram_reply_switch_enabled": true,
  "telegram_reply_authority": "explicit_environment_gate",
  "attachment_mode": "quarantine_only",
  "public_status": "verified_binding_only"
}
```

## Controlled synthetic proof

A synthetic Telegram-shaped update was submitted to the deployed Cloudflare webhook with the configured Telegram provider-authentication secret.

The Worker returned:

```json
{
  "schema": "dio.presence.telegram_edge_receipt.v1",
  "state": "queued",
  "duplicate": false,
  "custody": "cloudflare_d1_provider_authenticated_transport_only",
  "authority": "none",
  "signing_authority": "local_dio_presence_reconciler_only"
}
```

The event was subsequently processed by the local reconciler and Vesper produced a Telegram reply.

D1 recorded:

```text
id  update_id    status     attempts  last_error
1   1787039150   processed  1         null
```

## Real provider proof

Telegram's webhook was then changed from the legacy Hugging Face endpoint to:

```text
https://dio-presence-gateway-staging.dio-workflows.workers.dev/telegram/webhook
```

`getWebhookInfo` confirmed that Cloudflare endpoint as the active Telegram webhook with no pending updates at observation time.

Two subsequent real Telegram provider updates were independently processed:

```text
id  update_id   status     attempts  processed_at                 last_error
2   427678086   processed  1         2026-08-18T07:58:21.354Z    null
3   427678087   processed  1         2026-08-18T08:02:31.893Z    null
```

Vesper replied through the governed Telegram reply rail.

This demonstrates repeatable real-provider delivery rather than a one-shot synthetic success.

## What this proves

This controlled staging execution proves:

- Telegram → Cloudflare provider ingress;
- Telegram provider-secret verification at the Worker;
- durable D1 custody;
- outbound-only laptop polling;
- local-only DIO operator signing;
- Presence Core HMAC verification;
- Vesper/LINGUA processing;
- bounded Telegram reply execution;
- repeatability across multiple real Telegram updates;
- no critical-path Hugging Face transport dependency;
- no public Cloudflare tunnel dependency;
- no Cloudflare-held DIO operator signing authority.

## What this does not prove

This receipt does **not** claim:

- general production readiness for every Presence channel;
- WhatsApp or browser-chat execution proof through this Cloudflare path;
- unlimited uptime or provider SLA;
- automatic business authority;
- automatic publication, spend, payment, fulfilment or professional authority;
- public Persona Lab commercial validation;
- customer demand or willingness to pay.

## Canonical closure phrase

> **VESPER OPERATOR PRESENCE PERMANENT EDGE QUEUE PATH PROVED, WITH OUTBOUND-ONLY CORE CONNECTIVITY, LOCAL DIO SIGNING AUTHORITY, REPEATABLE REAL TELEGRAM DELIVERY, AND NO PUBLIC TUNNEL OR HUGGING FACE TRANSPORT DEPENDENCY.**

## Architectural consequence

The Hugging Face operator Space may remain as a non-critical interface or compatibility deployment, but it is no longer the canonical Telegram transport dependency.

Future Presence work should extend the Cloudflare custody membrane or another explicitly governed transport surface rather than reintroducing direct inbound access to local Presence Core.
