# DIO Presence Gateway — staging membrane

This Worker is a **transport/custody membrane**, not a Presence authority.

It supports two deliberately separate custody lanes:

1. an existing signed-envelope lane that accepts an already-signed Vesper Presence envelope, preserves the exact raw JSON body plus the four `X-DIO-Presence-*` headers in staging D1, and exposes a token-protected pull/ack API; and
2. the canonical operator Telegram lane, which authenticates Telegram webhook delivery with Telegram's provider secret, preserves the exact raw provider update in D1, and leaves DIO envelope construction and signing to the local reconciler.

The Worker does **not** know `DIO_PRESENCE_OPERATOR_SHARED_SECRET` or `DIO_PRESENCE_PUBLIC_SHARED_SECRET` and cannot validate or create DIO Presence authority. Cryptographic DIO signing/verification remains local in the reconciler and `scripts/serve_presence_bridge.py` / DIO Presence Core.

## Canonical operator Telegram topology

```text
Telegram
   ↓ X-Telegram-Bot-Api-Secret-Token
DIO Presence Gateway (Cloudflare Worker)
   ↓ exact raw provider update
staging D1 durable custody
   ↓ token-protected outbound poll
scripts/sync_vesper_presence_edge.py
   ↓ local envelope construction
   ↓ local operator-edge HMAC signing
127.0.0.1:8787/api/presence/ingress
   ↓
Presence Core verifies HMAC + TTL + nonce
   ↓
LINGUA + Vesper
   ↓ explicit Telegram reply authority gate
Telegram reply
```

The Hugging Face operator Space is no longer a canonical Telegram transport dependency. It may remain as a compatibility or non-critical interface deployment.

The supplied `wrangler.jsonc` binds **only** the staging `dio-commerce` D1 database. There is deliberately no `env.live` block.

## Safety properties

- Cloudflare never receives `DIO_PRESENCE_OPERATOR_SHARED_SECRET` or `DIO_PRESENCE_PUBLIC_SHARED_SECRET`.
- Telegram's webhook secret authenticates provider delivery only; it grants no DIO business, operator-signing, publication or reply authority.
- Raw Telegram updates are stored without inventing DIO signatures at the edge.
- The existing signed-envelope lane continues to preserve the original signed body without JSON reserialization.
- Pull/ack requires a separate `DIO_PRESENCE_EDGE_TOKEN`.
- Telegram events are signed locally when reconciled, so DIO's short signature TTL starts at local processing time rather than provider-ingress time.
- Local Core 4xx rejection is terminal and may be acknowledged `failed`; network/5xx failures remain pending for retry.
- Provider custody and DIO authority are separate trust domains.

## Staging deployment

From this directory:

```bash
npm install
npm test
npm run check
npm run db:remote
```

Create a high-entropy staging transport token locally and keep a copy for the local reconciler:

```bash
mkdir -p ~/.local/state/knowedge-dio
python3 - <<'PY' > ~/.local/state/knowedge-dio/presence-edge-pull-token
import secrets
print(secrets.token_urlsafe(48))
PY
chmod 600 ~/.local/state/knowedge-dio/presence-edge-pull-token
```

Load that same value into the Worker secret without printing it:

```bash
cat ~/.local/state/knowedge-dio/presence-edge-pull-token | npx wrangler secret put DIO_PRESENCE_EDGE_TOKEN
```

The canonical Telegram lane also requires the configured Telegram webhook secret at the Worker. Load it from the operator environment without echoing the value, then deploy:

```bash
set -a
source ~/.config/dio/presence.operator.env
set +a
printf '%s' "$TELEGRAM_WEBHOOK_SECRET" | npx wrangler secret put TELEGRAM_WEBHOOK_SECRET
npm run deploy
```

Run the local Core and reconciler:

```bash
python3 scripts/serve_presence_bridge.py
python3 scripts/sync_vesper_presence_edge.py --watch
```

The active staging Telegram webhook is:

```text
https://dio-presence-gateway-staging.dio-workflows.workers.dev/telegram/webhook
```

## Controlled execution proof

The staging path has been proved with one synthetic Telegram-shaped event and multiple real Telegram provider updates. The canonical proof receipt is:

```text
docs/VESPER_PERMANENT_PRESENCE_PROOF_2026-08-18.md
```

That proof establishes repeatable Telegram → Cloudflare → D1 → outbound local reconciliation → local DIO signing → Presence Core → Telegram reply execution without a public tunnel or Hugging Face transport dependency.

## Promotion rule

Staging execution proof does not itself authorize a live/production Presence Worker. Live promotion remains a separate operator decision and must preserve the same custody/authority separation.
