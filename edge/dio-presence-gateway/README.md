# DIO Presence Gateway — staging membrane

This Worker is a **transport/custody membrane**, not a Presence authority.

It accepts an already-signed Vesper Presence envelope from a remote edge, preserves the exact raw JSON body plus the four `X-DIO-Presence-*` custody headers in the staging D1 database, and exposes a separately token-protected pull/ack API for the local reconciler.

It does **not** know the public/operator Presence shared secrets and cannot validate or create Presence authority. Cryptographic verification remains in `scripts/serve_presence_bridge.py` / DIO Presence Core.

## Staging-only topology

```text
Telegram
   ↓
HF operator edge
   ↓  signed body + X-DIO-Presence-* headers
DIO Presence Gateway (Cloudflare Worker)
   ↓  durable D1 custody
scripts/sync_vesper_presence_edge.py
   ↓  exact original body + headers
127.0.0.1:8787/api/presence/ingress
   ↓
Presence Core verifies HMAC + TTL + nonce
   ↓
Vesper → governed Telegram reply
```

The supplied `wrangler.jsonc` binds **only** the staging `dio-commerce` D1 database. There is deliberately no `env.live` block.

## Safety properties

- Cloudflare never receives `DIO_PRESENCE_OPERATOR_SHARED_SECRET` or `DIO_PRESENCE_PUBLIC_SHARED_SECRET`.
- The original signed body is stored as text without JSON reserialization.
- The Worker performs only shape, size, key-id and freshness prechecks. These are anti-junk checks, not authority verification.
- Pull/ack requires a separate `DIO_PRESENCE_EDGE_TOKEN`.
- Local Core 4xx rejection is terminal and may be acknowledged `failed`; network/5xx failures remain pending for retry.
- The default signature window is 300 seconds, matching Presence Core. If the local reconciler is offline beyond that window, Core will correctly reject stale capsules.

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

Then load that same value into the Worker secret without printing it:

```bash
cat ~/.local/state/knowedge-dio/presence-edge-pull-token | npx wrangler secret put DIO_PRESENCE_EDGE_TOKEN
npm run deploy
```

Run the local Core and reconciler:

```bash
python3 scripts/serve_presence_bridge.py
python3 scripts/sync_vesper_presence_edge.py --watch
```

After deployment, point the HF operator Space `DIO_CORE_URL` at:

```text
https://dio-presence-gateway-staging.dio-workflows.workers.dev
```

The HF edge already appends `/api/presence/ingress`.

## Promotion rule

Do not create or deploy a live Presence Worker until the staging proof succeeds with the temporary Quick Tunnel stopped. Live promotion requires a separate review and explicit operator decision.
