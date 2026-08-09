# WhatsApp Cloud API onboarding

Wave 2 implements the public Cloud API edge. You still need to configure your Meta business/app assets.

## Space secrets

- `WHATSAPP_VERIFY_TOKEN`: random string you choose and also configure in Meta's webhook settings.
- `WHATSAPP_APP_SECRET`: Meta App Secret, used to validate `X-Hub-Signature-256` on incoming POST webhooks.
- `WHATSAPP_ACCESS_TOKEN`: token with the required WhatsApp messaging authority for the configured business setup.
- `WHATSAPP_PHONE_NUMBER_ID`: Cloud API phone-number ID.
- `META_GRAPH_VERSION`: a currently supported Graph API version. It is deliberately not hard-coded into DIO.

Callback URL:

```text
https://YOUR-SPACE.hf.space/whatsapp/webhook
```

Verification uses the GET challenge/verify-token flow. Incoming POST payloads are rejected unless their `X-Hub-Signature-256` validates against the app secret.

For incoming document/image/audio messages the edge retrieves the media URL, downloads it with the WhatsApp access token, and either transcribes audio or forwards a bounded, hashed attachment to DIO quarantine. Retrieved media URLs are short-lived, so the edge downloads immediately and never stores the provider URL as canonical state.

Wave 2 sends only bounded direct replies to inbound messages. It does not implement unsolicited marketing sends, template-campaign automation, or bulk WhatsApp outreach.

Official implementation references used for Wave 2:
- Meta WhatsApp Business Platform Postman collection: Cloud API media, messages, webhooks, and webhook payload reference.
- Meta-hosted WhatsApp Node.js SDK webhook documentation for GET verification-token and POST `x-hub-signature-256` authenticity checks.
