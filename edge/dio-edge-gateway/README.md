# DIO Edge Gateway

Cloudflare Worker ingress for Microsoft Graph and verified commerce events.

The Worker stores webhook deliveries in the `dio-commerce` D1 database. Local DIO services pull and acknowledge those events over an authenticated API. Provider webhook endpoints remain fail-closed until their signature-verification adapters and secrets are installed.

## Deploy

```bash
npm install
npx wrangler login
npm run db:remote
npm run deploy
```

Required encrypted Worker secrets:

```text
GRAPH_CLIENT_STATE
DIO_EDGE_TOKEN
```

Do not place either value in `wrangler.jsonc`, shell history, chat, or source control.

Install both from local mode-`0600` files without displaying their values:

```bash
python3 ../../scripts/configure_dio_edge.py
```

## Routes

```text
GET  /health
POST /webhooks/microsoft-graph/notifications
POST /webhooks/microsoft-graph/lifecycle
GET  /api/dio/events
POST /api/dio/events/ack
POST /webhooks/paypal
POST /webhooks/payfast
```

The payment endpoints intentionally return `503` until payment verification is activated. Install provider credentials without exposing them:

```bash
python3 ../../scripts/configure_payment_secrets.py paypal
python3 ../../scripts/configure_payment_secrets.py payfast
```

Keep each provider in sandbox mode until a signed webhook has produced the expected D1 order transition. A browser return URL never changes payment state.
