# DIO Market Command Integration Status

## Operating model

Market Command is a native DIO control surface. Hivenance supplies observed hypotheses, NicheFoundry supplies proof-led creative, Lingua versions every language/channel variant, external channels supply attention evidence, and DIO owns commercial attribution and settlement.

```text
signals -> hypothesis -> proof -> governed content -> Lingua -> approval
        -> channel -> lead -> order -> verified payment -> fulfilment -> settlement
```

Automatic spend is off. The global experiment budget is zero. Translation never creates outreach permission or publication authority.

## Lingua market coverage

The shared semantic organ now covers:

- campaign copy, proof stories, advertisements and landing pages
- outreach drafts and conversion messages
- publisher, newsletter, association and agency briefs
- NicheFoundry video scripts, titles, descriptions, thumbnails and captions
- Facebook, Instagram, Messenger, WhatsApp, LinkedIn, YouTube, Google Ads, Reddit and TikTok variants
- South African publisher and manual media-buy creative

Campaign ID, product line, proof asset, CTA and channel are retained as origin context. UTM parameters, prices, dates and spend caps are protected from translation. Each channel variant is a separate semantic object so shortening one post cannot silently alter another.

## Current real state

- Five Hivenance Wave 4 hypotheses imported as Market Command experiments.
- Five proof-bound content objects registered with Lingua.
- All campaign and content approvals remain pending operator review.
- HOMS and Evidex YouTube videos are bound to their campaign lineage.
- YouTube public statistics sync is live through the existing NicheFoundry credentials.
- Repeated channel sync windows are idempotent and cannot inflate the scoreboard.

## Adapter authority

| Channel | Read path | Publication/write path |
| --- | --- | --- |
| YouTube | Live public video statistics | Existing NicheFoundry OAuth, operator approval required |
| Meta Ads | Insights adapter, credentials required | Blocked in Wave 2 |
| Facebook Page | API read optional, manual import ready | Meta Business Suite after approval |
| Instagram | API read optional, manual import ready | Meta Business Suite after approval |
| LinkedIn | Organization analytics optional, manual import ready | Human publication only |
| TikTok Ads | Reporting adapter, credentials required | Blocked in Wave 2 |
| TikTok organic | Manual result import | Human publication only |
| Google Ads | Official client reporting, setup required | Blocked in Wave 2 |
| Reddit Ads | Reporting adapter, credentials required | Blocked in Wave 2 |
| Reddit organic | Community research and manual evidence | Human publication only |
| Outlook | DIO mail receipts | Mail-intent approval required |
| WhatsApp | Existing conversation/manual evidence | Existing conversation or opt-in only |
| SA media/agencies | Quote and provider-report import | Approved media buy required |

## Credentials

Install private credentials at `/home/byron/.config/dio/market_channels.env`. Market Command parses this file directly and never shell-evaluates it. The complete variable template is `config/market_channels.env.example`.

## Commands

```bash
./.venv/bin/python scripts/import_hivenance_market_command.py
./.venv/bin/python scripts/sync_marketing_channels.py YOUTUBE_ORGANIC
./.venv/bin/python scripts/bind_owned_video_campaigns.py
./.venv/bin/python scripts/serve_market_command.py
```

The native Control Deck subpage is at `http://127.0.0.1:8765/`. The expanded Market Command surface is at `http://127.0.0.1:8770/`.

## South African Agency Procurement Update

Market Command now treats agencies as governed procurement adapters rather than a decorative directory. The registry includes verified public enquiry routes, service and measurement fit, small-pilot fit, product suitability, risk notes and a DIO-specific score. The control surface can:

```text
prepare campaign-specific RFQ
-> create media-buy research record
-> create governed Outlook draft or public-form package
-> capture quote evidence and approved cap
-> apply separate agency-spend release
-> capture provider report
-> bind reported delivery to DIO campaign metrics
```

The first controlled Adclick Africa RFQ is prepared as `MAIL-683374577109CC45`, bound to `BUY-76A8EE97F753` and campaign `MKT-B3FB86BF5CB7`. It is unsent, unquoted and has a zero approved cap. See [SA_AGENCY_PROCUREMENT.md](SA_AGENCY_PROCUREMENT.md).
