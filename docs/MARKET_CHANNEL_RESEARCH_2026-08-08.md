# DIO Market Command — channel research snapshot

Verified: 2026-08-08

This snapshot records why Wave 1 treats marketing channels as adapters rather than letting any platform become the system of record.

## Programmable paid channels

- **Meta Ads:** Meta's official Facebook Marketing API Postman workspace describes campaign, ad set and ad create/edit operations and ad insights. DIO therefore models Meta as an API candidate, but keeps spend locked until credentials and a test account are configured.
- **Google Ads:** Google's current API documentation describes programmatic account/campaign management and reporting. A developer token and account setup are required.
- **Reddit Ads:** Reddit Ads API v3 supports campaign, creative, business, conversion and reporting functions. Reddit states the Ads API is open to developers without allowlisting, but a business/developer app and ad account are still required. Wave 1 keeps organic subreddit participation human-governed.
- **TikTok:** TikTok API for Business exposes Marketing API capabilities for campaign management, creative assets, audiences and performance data after business/developer configuration.

## Facebook organic

Facebook Pages can be managed and posted through Facebook/Meta Business Suite, and Page Insights expose performance data. Wave 1 uses a manual Business Suite publication adapter until a suitable Meta Page API app is configured and reviewed.

## South African manual media layer

- **Bizcommunity:** current 2026 rate pages expose B2B website, newsletter and promoted-content inventory, including Education & Training and HR & Recruitment verticals. This is a high-value HOMS/Sophia/VAMP test channel.
- **Broad Media:** owns BusinessTech, MyBroadband, TopAuto and Daily Investor and sells campaign packages. Treat as quote-based.
- **SME South Africa:** advertises banners, sponsored content, newsletters, social promotion and lead generation to South African SME audiences. Treat as quote-based.
- **Arena Holdings:** Adroom exposes current publisher audience/readership pages and rate-card downloads. Treat individual placements as rate-card/quote verification tasks.
- **Mail & Guardian:** exposes an advertising enquiry route; treat pricing and placement as quote-based.
- **Adspace24 / Media24:** public rates page currently links a 2025 rate card, therefore any future spend requires a fresh quote rather than relying on the stale public card.
- **IAB South Africa:** current membership exceeds 150 organisations and provides a practical discovery universe for local publishers, agencies and adtech partners. Membership is not treated as an endorsement or ranking.

## DIO principle

An API channel and a manual publisher buy are measured against the same downstream objects:

```text
campaign_id -> lead_id -> order_id -> paid_order -> revenue
```

The platform can therefore compare channels on qualified demand and commercial outcomes rather than forcing all channels into one vendor's analytics vocabulary.
