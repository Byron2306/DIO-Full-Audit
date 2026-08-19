# DIO Market Sensorium Implementation

Status: IMPLEMENTED FOUNDATION / LOCAL VALINOR VERIFICATION REQUIRED

This implementation turns the Market Sensorium design into a read-only, temporal market-intelligence loop. It does not grant send, publish, spend, join, DM, payment, purchase or deployment authority.

## Implemented surfaces

### Temporal commercial memory

`market_sensorium/core.py` provides a SQLite-backed memory at `state/market_sensorium/market_sensorium.sqlite` with distinct stores for:

- source-bound observations;
- commercial target memory;
- explainable rank-change receipts;
- market habitats / communities;
- observed competing offers;
- unresolved discovery candidates;
- cycle receipts.

A target remembers first/last observation, last contact, reply/consent state, conversation lineage, current/previous score and rank, silence state and recommended next action.

Silence is context-specific evidence. It may decay an organisation × offer × channel hypothesis, but it is not treated as rejection and never creates follow-up authority.

### Existing Outlook lineage

The cycle can call the existing Microsoft Graph inbox delta pull when local Graph configuration and token cache already exist. Inbound mail is then compared against the conversation IDs on sent mail intents so actual replies can be distinguished from elapsed silence. If Graph is not configured, mail refresh reports `not_configured` and the rest of the read-only Sensorium still runs.

### Dynamic ranking

Target ranking incorporates domain fit, morphology fit, capability fit, buyer-role confidence, problem signals, recency, organisation fit, route quality, market momentum, prior engagement, competitive whitespace and seed prior, with explicit penalties for silence, rejection, authority uncertainty and stale evidence.

Rankings are domain-local and every material change can produce a receipt explaining contributing signals. Seed candidates can be overtaken by stronger discovered evidence.

### Five baseline candidates per ATLAS domain

`config/market_sensorium/seeds/` contains curated South African bootstrap organisations across the ATLAS domain families. They are marked `CURATED_BASELINE_PRIOR` / `SEED_PRIOR_REQUIRES_REFRESH`.

`scripts/compile_market_sensorium_baselines.py` projects those organisations against each ATLAS `DOMAIN` row and selects exactly five baseline candidates using this order:

1. explicit domain binding;
2. domain-tag overlap;
3. domain-family fallback.

Family-only domains are explicitly reported as weak priors. The output is `state/market_sensorium/domain_baseline_candidates.csv`.

The compiler does **not** claim these are verified best buyers. Its purpose is to prevent a cold start while giving the continual discovery loop something that fresh evidence can replace.

### ATLAS-wide continual public discovery

`scripts/refresh_market_sensorium_domain_signals.js` reuses the existing NicheFoundry YouTube public-discovery and RSS connectors. `market_sensorium/queries.py` selects a rotating batch of ATLAS domains, prioritising weak baseline domains and domains least recently observed.

The default batch is eight domains per cycle, with up to five YouTube and five Google News/RSS observations per selected domain. Results are written to `state/market_sensorium/domain_signals/<domain_id>.json` and ingested as unresolved knowledge-only discovery candidates and market habitats.

A public search hit does not automatically become a target or lead.

### Existing campaign sensing and Hivenance Phoenix

The cycle also ingests the existing Wave 4 `LIVE_MARKET_SIGNALS.json` observations and `HIVENANCE_MARKET_AGENTS.json` receipts. Hivenance remains the hypothesis engine: observations can alter test/refine/hold hypotheses and priority, but do not create market truth or authority.

### Competitive offer intelligence

`scripts/import_market_offers.py` imports permitted/operator-collected CSV or JSON observations of competing/adjacent advertised offers. It can preserve asking price, price basis, pitch angle, audience and morphology while explicitly refusing to infer realised price, sales, profitability or demand.

HTML crawling is not implicitly authorised. `config/market_sensorium/source_policy.json` records source-specific access states for YouTube, RSS/news, Meta, Facebook communities, Discord, Reddit, classifieds, Locanto, News24, tenders and public job listings.

### Continual operation

`ops/systemd/dio-market-sensorium.service` and `.timer` provide a six-hour read-only cycle template. The timer is intentionally not installed or enabled automatically. It should be activated only after local verification on Valinor.

## Verification sequence

```bash
cd /home/byron/DIO-Full-Audit

PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q \
  tests/test_market_sensorium.py \
  tests/test_market_sensorium_queries.py

PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
scripts/compile_market_sensorium_baselines.py

PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
scripts/run_market_sensorium_cycle.py
```

Only after the bounded local cycle is clean should the connected public refresh be exercised:

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
scripts/run_market_sensorium_cycle.py --refresh-public --refresh-mail
```

The expected acceptance labels are `DIO_MARKET_SENSORIUM_BASELINE_CANDIDATES_READY` and `DIO_MARKET_SENSORIUM_READ_ONLY_CYCLE_READY`. They are not considered locally proven until the Valinor run produces them.

## Proof boundary

Market Sensorium may learn **where to look, what to compare, which hypothesis deserves attention and why a rank changed**. It may not turn observation into capability, demand, consent, revenue, market validation or authority.
