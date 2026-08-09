# Hugging Face Docker deployment

Wave 2 ships separate public and operator Space bundles because they are different trust domains.

## Public Space

Deploy `DIO_Lilith_Public_HF_Space_Wave2.zip` to a Docker Space. Its runtime may contain only the **public** DIO signing secret. It may also contain Telegram public-bot credentials, WhatsApp Cloud API credentials, and web-chat session secret.

The Docker Space listens on port 7860 and exposes:
- `/health`
- `/telegram/webhook`
- `/whatsapp/webhook`
- `/` Lilith web chat

Store sensitive values as HF Space Secrets. Docker Space runtime secrets are injected as environment variables.

## Operator Space

Deploy `DIO_Lilith_Operator_HF_Space_Wave2.zip` separately, preferably private/protected according to your deployment needs. It must use:
- a different Telegram bot token,
- a different Telegram webhook secret,
- `DIO_PRESENCE_EDGE_ROLE=operator`,
- `DIO_PRESENCE_OPERATOR_SHARED_SECRET`,
- no public WhatsApp credentials,
- no public web-chat deployment.

The DIO core independently requires the operator Telegram numeric ID allowlist before it grants operator role.

## Canonical state

Never use HF Space disk as the authoritative customer/order/payment store. Space state is edge/cache state only. The DIO core records canonical Presence receipts and business bindings.
