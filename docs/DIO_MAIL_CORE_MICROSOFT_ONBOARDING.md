# DIO Mail Core: Microsoft Onboarding

## Decision

Use a dedicated Microsoft mailbox for DIO customer operations.

For the first controlled pilots, a new personal `outlook.com` account is adequate and costs nothing. Before public launch, a Microsoft 365 mailbox on a DIO-owned domain is the stronger trust and administration boundary.

Never provide the mailbox password, MFA code, recovery code, refresh token or browser cookies to Codex or place them in this repository.

## Access Model

```text
Dedicated Outlook mailbox
  -> Microsoft OAuth device consent
  -> delegated Graph permissions
  -> local mode-0600 token cache
  -> DIO Mail Core
```

Initial delegated permissions:

- `User.Read`
- `Mail.ReadWrite`
- `Files.ReadWrite`

`Mail.Send` is deliberately excluded from the first consent. Graph can read mail and create drafts, but cannot send them. The Outlook browser fallback is also default-off and requires a one-time approved mail intent.

## Account Setup

1. Create the dedicated Outlook account.
2. Enable two-step verification and store recovery information outside this repository.
3. Sign in once at Outlook and OneDrive in the browser and complete any first-run prompts.
4. In Microsoft Entra, register an application named `DIO Mail Core Local`.
5. Select personal Microsoft accounts, or the combined organisational-and-personal account type if the app will later serve a Microsoft 365 mailbox.
6. Configure it as a public desktop client and enable public-client/device-code flow.
7. Add the three delegated Graph permissions listed above. Do not add application permissions or a client secret.
8. Copy `config/microsoft_graph.example.json` to `config/microsoft_graph.local.json` and replace only `client_id`.

The client ID identifies the application and is not a password. The token cache is the sensitive credential and remains outside version control at:

```text
/home/byron/.local/state/knowedge-dio/msal-token-cache.json
```

## Connect

Install the local adapter dependencies:

```bash
.venv/bin/pip install -r requirements-microsoft-graph.txt
```

Start device login and the safe connection probe:

```bash
.venv/bin/python scripts/connect_microsoft_graph.py --device-login
```

The terminal displays a Microsoft URL and short code. Open the URL, sign in to the new DIO account, inspect the requested permissions, and approve them. DIO never sees the password.

## Initialise OneDrive

The existing local work area is:

```text
/home/byron/KnowEdge_Microsoft_Mirror
```

It is currently only a local directory. Microsoft does not provide its OneDrive desktop synchronisation client for Linux. DIO therefore uses a narrow Graph transport instead of pretending the folder is already mirrored.

Create the controlled OneDrive tree:

```bash
.venv/bin/python scripts/sync_onedrive_jobs.py init
```

This creates:

```text
DIO/
  HOMS/{incoming,processing,done,deliveries,failed}
  EVIDEX/{incoming,processing,done,deliveries,failed}
  SOPHIA/{incoming,processing,done,deliveries,failed}
  VAMP/{incoming,processing,done,deliveries,failed}
```

Pull new HOMS and Evidex job folders without deleting either side:

```bash
.venv/bin/python scripts/sync_onedrive_jobs.py pull
```

Upload one reviewed delivery folder:

```bash
.venv/bin/python scripts/sync_onedrive_jobs.py push \
  --product HOMS \
  --job-dir /home/byron/KnowEdge_Microsoft_Mirror/HOMS/done/<job-id>
```

## Mail Ingress And Drafts

Pull Outlook changes through a delta cursor:

```bash
.venv/bin/python scripts/sync_outlook_mail.py pull
```

Create a governed mail intent:

```bash
.venv/bin/python scripts/manage_mail_intent.py create \
  --spec samples/mail/evidex_delivery_intent.json
```

Create an Outlook draft from that intent:

```bash
.venv/bin/python scripts/sync_outlook_mail.py draft <mail-intent-id>
```

This does not send the message. Initial Graph consent lacks `Mail.Send`.

## Browser Fallback

The browser agent remains useful for operator-visible work. Start it headed and sign in interactively. Its password-login endpoint is disabled by default.

Even with a valid browser session, `send_email` refuses unless all three conditions hold:

1. `DIO_OUTBOUND_MAIL_ENABLED=true` is deliberately set.
2. The request names an approved `dio.mail_intent.v1` object.
3. The request supplies that intent's unexpired one-time approval token.

After a successful send, the token is destroyed and the intent becomes `sent/consumed`.

## Production Progression

1. Connect with read, draft and file permissions only.
2. Prove new-mail delta ingestion.
3. Prove OneDrive HOMS intake and reviewed delivery.
4. Prove Outlook draft creation and human editing.
5. Add `Mail.Send` only after the one-time approval path and sent receipt are tested end to end.
6. Add the public HTTPS webhook. Delta polling remains the recovery mechanism because Graph subscriptions expire and notifications can be missed.

## Graph Webhook

The production receiver is the Cloudflare Worker at `https://dio-edge-gateway.dio-workflows.workers.dev`. It durably stores notifications in D1 while the local computer is offline. The localhost receiver remains a development fallback; never expose the Control Deck on port `8765`.

Set these two values in `config/microsoft_graph.local.json`:

```json
"notification_url": "https://YOUR_HOST/webhooks/microsoft-graph/notifications",
"lifecycle_url": "https://YOUR_HOST/webhooks/microsoft-graph/lifecycle"
```

For local-only development, start the fallback receiver:

```bash
.venv/bin/python services/microsoft_graph_webhook.py
```

After the HTTPS route is live, create the subscription:

```bash
.venv/bin/python scripts/manage_graph_subscription.py create
```

Microsoft validates both callback paths during creation. The Worker returns the opaque validation token as plain text, validates `clientState` on real notifications, strips that secret before storage, deduplicates deliveries and stores them in D1.

Pull edge events into the local durable queue:

```bash
python3 scripts/sync_dio_edge_events.py --watch
```

Run the delta reconciler as the mailbox worker:

```bash
.venv/bin/python scripts/process_graph_notifications.py --watch
```

Renew the Outlook subscription before its under-seven-day expiry:

```bash
.venv/bin/python scripts/manage_graph_subscription.py renew
```

The local subscription receipt is stored outside the repository at `/home/byron/.local/state/knowedge-dio/graph-subscription.json`.
