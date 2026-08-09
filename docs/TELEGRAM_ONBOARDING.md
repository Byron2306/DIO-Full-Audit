# Telegram onboarding · Wave 2

Create two bots if you want both surfaces:

1. **Public Lilith**: customer/product concierge.
2. **Operator Lilith**: your PA surface.

Never reuse bot tokens or DIO signing keys between them.

For the public bot, configure the webhook to:

```text
https://YOUR-PUBLIC-SPACE.hf.space/telegram/webhook
```

The Space validates Telegram's webhook secret header before accepting an update.

Wave 2 additionally supports documents/photos. Telegram documents are rejected at the edge if their declared size exceeds the configured DIO public limit. Accepted media is downloaded using Telegram `getFile`, hashed, and transferred to DIO quarantine. DIO intentionally uses a smaller default public limit than Telegram's provider-side Bot API download ceiling.

Operator role is possible only when all of the following are true:
- request is signed by the operator-edge DIO key,
- channel is Telegram,
- Telegram numeric user ID is present in `DIO_OPERATOR_TELEGRAM_IDS`.

A public edge knowing your Telegram ID is insufficient.
