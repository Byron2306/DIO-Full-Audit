# Lilith public web chat

The public HF Space serves a dependency-free Lilith chat UI at `/`.

Web chat identities are signed anonymous session cookies. They are useful for conversation continuity, not customer authentication. Consequently web chat receives no order-status authority until an operator explicitly identity-binds the conversation.

A campaign can link to:

```text
https://YOUR-SPACE.hf.space/?campaign=MKT-HOMS-42
```

The value is carried to DIO only as a bounded campaign hint and must be reconciled by Market Command before being treated as attribution truth.

Default rate limit is 20 messages per minute per session. Set `WEBCHAT_SESSION_SECRET` to a random 32+ character secret in the HF Space and leave `WEBCHAT_COOKIE_SECURE=1` in production.
