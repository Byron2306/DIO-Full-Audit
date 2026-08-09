# DIO Market Command

## Purpose

Market Command is DIO's evidence-governed marketing control plane. It does not replace ad networks, publishers or agencies. It makes them comparable adapters inside one commercial lineage.

The core question is not **which platform generated the prettiest dashboard**. It is:

> Which observed campaign created qualified demand, which demand became an order, which order became a verified payment, what did fulfilment cost, and does the evidence justify repeating the experiment?

## Wave 2 architecture

```text
market/prospect signals
        ↓
campaign hypothesis
        ↓
proof asset + creative brief
        ↓
human approval
        ↓
channel / publisher / agency
        ↓
platform or provider measurement
        ↓
normalized channel snapshot
        ↓
DIO attribution spine
        ↓
lead → order → payment → job
        ↓
verified cross-channel economics
        ↓
promote / continue / revise / kill
```

## Authority model

Wave 2 platform adapters are **read-first**. Meta, Google Ads, Reddit Ads and TikTok Ads can be configured for performance ingestion, but the code intentionally omits ad/campaign/budget mutation methods.

Manual channels remain first-class:

- Facebook Page organic
- LinkedIn founder content
- Reddit community participation
- YouTube
- South African publishers
- newsletters and associations
- agencies / media buyers

## Two ledgers, one scoreboard

Platform observations:

- impressions
- reach
- clicks
- spend
- platform conversions

DIO commercial evidence:

- qualified lead
- order
- payment
- fulfilment
- delivery
- verified revenue

The scoreboard uses DIO revenue for `verified_roas`; provider conversion value is preserved as observation evidence but does not silently become revenue truth.

## Professional intelligence

A professional-role binding can be imported from LinkedIn, Apollo, a public website or manual verification. It stores identity/role confidence independently from outreach permission.

`person found` is not equivalent to `marketing allowed`.

## Manual media procurement

Any publisher or agency can become a governed DIO adapter through:

`research → RFQ brief → quote → approval → booking → publication proof → provider report → DIO attribution → settlement`

This makes no-API media comparable to API-native media without pretending the vendor is directly integrated.

## Security

- localhost-only server
- JSON-only control POSTs
- Host and Origin checks
- optional `DIO_MARKET_CONTROL_TOKEN`
- no credential persistence in Market Command state
- no write-capable paid-media adapter in Wave 2
- automatic spend remains hard-disabled
