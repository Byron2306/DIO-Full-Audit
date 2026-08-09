# DIO Market Command Wave 2: Read-First Channel Integration

Wave 2 deliberately adds **measurement access before mutation access**.

## Why

Advertising platforms are external authorities over inventory, not over DIO's business truth. A platform may report impressions, clicks, spend and attributed conversions. DIO separately binds qualified leads, orders, payments, fulfilment and delivery to the campaign lineage.

Therefore the first live integration surface is:

`platform reporting -> normalized channel snapshot -> DIO attribution spine -> commercial settlement`

not:

`optimizer -> automatically edit budgets -> hope`.

## Implemented read adapters

### Reddit Ads API v3

- OAuth 2.0 / `adsread` oriented.
- Uses the reporting endpoint under `/ad_accounts/{ad_account_id}/reports`.
- DIO does not expose Reddit campaign-create/update endpoints in Wave 2.
- The current Reddit Ads documentation notes that v3 is the active API and that reporting endpoints return performance data. It also documents current 2026 migration notices which should be reviewed before a future write-capable adapter is attempted.

Official research: https://ads-api.reddit.com/docs/v3/

### TikTok API for Business

- Reporting-only adapter.
- Current API docs describe `v1.3` and the synchronous integrated reporting endpoint.
- DIO does not expose campaign/adgroup/ad creation endpoints in Wave 2 even though the platform offers them.

Official research: https://business-api.tiktok.com/portal

### Google Ads API

- Reporting-only adapter using the official Python client when installed/configured.
- Pulls campaign impressions, clicks, cost, conversions and conversion value.
- No mutate services are used by DIO Wave 2.

Official research: https://developers.google.com/google-ads/api/docs/reporting/overview

### Meta Ads

- Read-only insights adapter with an **explicit `META_GRAPH_VERSION` environment variable**.
- DIO intentionally does not freeze a Graph API version into code. Platform version changes must be operator-visible.
- Before enabling a live account, validate the configured version and field set against the current Meta Marketing API documentation for that account/app.
- No ad/campaign mutation routes are present in DIO Wave 2.

## Evidence grades

- `platform_api`: directly observed through a read adapter.
- `provider_report`: supplied by a publisher/agency report.
- `operator_import`: manually copied/exported into DIO.
- `estimated`: planning-only and unsuitable for settlement claims.

## Professional intelligence

Professional identity evidence is stored separately from outreach permission. LinkedIn/Apollo/public-site enrichment can tell DIO *who appears to own the problem*. That fact does not grant electronic-marketing permission.

## Future write-capable wave

A future wave may add campaign draft creation after each platform connection has:

1. stable read sync,
2. external campaign ID binding,
3. attribution reconciliation,
4. operator approval controls,
5. idempotency/retry tests,
6. account-level spend caps,
7. rollback/pause controls.

Wave 2 has no platform write adapter.
