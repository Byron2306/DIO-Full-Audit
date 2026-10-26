# DIO Market Sensorium MS-5 — Competitive Offer Intelligence

Status: IMPLEMENTED / LIVE SENSORIUM VERIFICATION REQUIRED

## Purpose

MS-1 discovered source-bound organisation hypotheses. MS-2 established truthful commercial time. MS-3 proved dynamic rank movement. MS-4 turned movement into rival Hivenance explanations.

MS-5 gives the Sensorium a governed memory for **what providers publicly offer and what prices they explicitly advertise**.

It does not turn listings, promotional copy or asking prices into demand, realised prices, willingness to pay, market share or commercial success.

```text
already-governed public connector receipts
        ↓
provider-role gate
        ↓
self-promotional offer evidence
        ↓
canonical offer memory + immutable observation events
        ↓
explicit advertised-price parser
        ↓
dedupe / persistence / provenance
        ↓
future OFFER / PRICE Hivenance hypotheses
```

## Existing spine reused

The Market Sensorium already contained:

```text
offer_observations
MarketSensoriumStore.record_offer(...)
```

MS-5 activates that dormant organ rather than creating a separate incompatible marketplace store.

It also adds two stricter companion ledgers:

```text
competitive_offer_events
competitive_offer_memory
```

The first preserves individual source-bound observations. The second groups repeated or syndicated observations under a stable canonical offer key.

## Initial source boundary

The first live extractor intentionally accepts only **provider-owned YouTube channel evidence** from the already-governed `LIVE_MARKET_SIGNALS.json` connector receipts.

A record is admitted only when:

- the public record is relevant under the existing connector gate;
- the channel identity is available;
- the channel description contains self-promotional provider language;
- the description contains a concrete CTA or route;
- a public source URL is preserved.

This means:

```text
channel self-promotion -> seller candidate evidence may be admitted
article publisher       -> NOT automatically a seller
organisation mentioned  -> NOT automatically a seller
source/channel identity -> NOT automatically a target
```

The first lane is intentionally conservative. News/blog publishers can be added later only with stronger seller-role resolution.

## Observed offer schema

Each competitive offer event preserves:

- source kind and source URL;
- source receipt path;
- observation and publication time;
- seller;
- seller role and role basis;
- ATLAS domain and morphology;
- headline;
- pitch angle;
- CTA;
- explicit audience only when available;
- advertised price state/value/currency/basis;
- evidence confidence;
- access and terms state;
- provenance digest;
- authority boundary.

The richer payload also retains the source relevance terms without treating them as buyer proof.

## Advertised-price truth

MS-5 parses only explicit public asking-price language.

Examples:

```text
ZAR 1,499 per month
R 850 per report
USD 99 / month
first report FREE — no credit card needed
free trial
```

Price states include:

```text
EXPLICIT_MONETARY_ADVERTISED
EXPLICIT_FREE_ADVERTISED
PRICE_NOT_OBSERVED
PRICE_PARSE_ERROR
```

An explicit free entry offer is legitimate **advertised price evidence at zero**, but it proves none of the following:

```text
realised transaction price
willingness to pay
market price
revenue
buyer demand
commercial success
```

Likewise, a paid asking price is only the provider's observed asking price.

## Dedupe and persistence

A canonical competitive offer key is formed from:

```text
seller × domain × normalised headline
```

Individual source events remain preserved.

The memory layer records:

- first seen;
- last seen;
- observation count;
- distinct source count;
- distinct content count;
- latest explicit price state;
- persistence state.

Repeated observations do not become independent sellers. Syndicated copies do not become independent demand evidence.

## Truth boundaries

MS-5 explicitly preserves:

```text
advertised offer != demand
offer prevalence != demand
advertised price != market price
advertised price != realised price
free tier != willingness to pay
ad/listing persistence != success
seller identity != buyer identity
seller identity != target promotion
offer absence != no market
candidate whitespace != untapped market
```

No send, publish, spend, join, DM, payment or commerce authority is created.

## Acceptance

Strong acceptance requires:

```text
persisted MS-4 receipt is VERIFIED
real source-bound competitive offers observed
at least two seller identities observed
provider/source role confusion = 0
all accepted offers source-bound
at least one explicit advertised-price observation
price normalization errors = 0
zero demand/WTP/realised-price/market-price promotion
zero authority or external effects
```

Strong token:

`DIO_MARKET_SENSORIUM_COMPETITIVE_OFFER_INTELLIGENCE_VERIFIED`

Important pending/refusal states include:

- `PENDING_VERIFIED_MS4_RECEIPT`
- `PENDING_COMPETITIVE_OFFER_EVIDENCE`
- `PENDING_MULTI_SELLER_COMPETITIVE_EVIDENCE`
- `REFUSE_SELLER_SOURCE_ROLE_CONFUSION`
- `PENDING_SOURCE_BOUND_COMPETITIVE_OFFER_EVIDENCE`
- `REFUSE_ADVERTISED_PRICE_NORMALIZATION_ERROR`
- `PENDING_EXPLICIT_ADVERTISED_PRICE_EVIDENCE`
- `REFUSE_OFFER_PRICE_TRUTH_OR_AUTHORITY_INFLATION`

## Verification

Run the focused tests:

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q \
  tests/test_market_sensorium_competitive_offers.py \
  tests/test_market_sensorium_ms5_gate.py
```

Then consume the already-verified MS-4 receipt and existing public connector evidence:

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
scripts/run_market_sensorium_ms5.py \
  | tee /tmp/dio-ms5-live.json
```

Compact inspection:

```bash
jq '{
  ms4: .ms4_acceptance,
  ms5: .ms5_acceptance,
  ms5_truth: .ms5_truth,
  top5: [
    (.summary.competitive_offers.examples // [])[]
    | {
        seller,
        domain: .domain_id,
        offer: .headline,
        price_state,
        price_value,
        currency: .price_currency,
        basis: .price_basis,
        seller_role_basis
      }
  ][0:5]
}' /tmp/dio-ms5-live.json
```

After the initial proof, `scripts/run_market_sensorium_cycle.py` also runs the same MS-5 observation pass after the normal Sensorium cycle. It remains read-only with respect to the external world.

## Relationship to Hivenance

MS-4 already recognises `OFFER` and `PRICE` as hypothesis classes but correctly emitted neither when evidence was absent.

MS-5 supplies the evidence substrate required for future evidence-bearing OFFER and PRICE hypotheses. The existence of competitive offer evidence does not force those hypothesis types into an unrelated target/domain transition. Domain and evidence binding remain mandatory.
