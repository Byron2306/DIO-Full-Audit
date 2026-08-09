# DIO Presence architecture · Wave 2

```text
                 PUBLIC INTERNET
                       │
       ┌───────────────┼───────────────┐
       ▼               ▼               ▼
   Telegram         WhatsApp        Web Chat
       │               │               │
       └───────────────┼───────────────┘
                       ▼
              PUBLIC LILITH EDGE
          HF Docker / non-canonical
                       │
            signed public ingress
                       ▼
                DIO PRESENCE CORE
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
    classifier      quarantine     identity binding
        │              │              │
        └──────────────┼──────────────┘
                       ▼
              DIO EVENT / STATE SPINE
                       │
          ┌────────────┼─────────────┐
          ▼            ▼             ▼
       intake       Needs You     minimal status
          │            │
          └──────┬─────┘
                 ▼
           HUMAN AUTHORITY

SEPARATE TRUST DOMAIN
Professor → Operator Telegram bot → operator edge key + server allowlist
          → read-only PA brief over jobs, mail, commerce, Market Command, leads and incidents
```

The edge is disposable. DIO core owns conversation receipts, attachment quarantine metadata, identity bindings and product intakes.

The operator PA brief is documented in [LILITH_PA_STATUS.md](LILITH_PA_STATUS.md). It can summarise operating state, but cannot send mail, approve work, publish campaigns, release fulfilment, spend money or process attachments.
