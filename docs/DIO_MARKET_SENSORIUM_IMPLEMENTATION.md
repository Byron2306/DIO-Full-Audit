# DIO Market Sensorium Implementation

Status: IMPLEMENTED FOUNDATION + MS-1 DISCOVERY RESOLUTION / LOCAL VALINOR VERIFICATION REQUIRED

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

### MS-1 discovery resolution and seed supersession

`market_sensorium/resolution.py` adds a conservative resolver between public discovery and ranking.

A discovery may become a **rankable discovered target hypothesis** only when source-bound evidence can establish an organisation identity. The resolver currently accepts:

- explicit organisation/company/institution/employer fields supplied by the governed source record; or
- a conservative organisation-form marker in a sufficiently relevant headline, such as `University`, `Foundation`, `Council`, `Trust`, `Association`, `Institute`, `Authority`, `Board`, `Group`, `Holdings`, and related forms.

The resolver deliberately does **not** treat a news publisher or URL host by itself as the buyer organisation. Google News publisher suffixes are stripped before headline resolution so a publisher is not promoted merely because it appears after ` - ` in a title.

A resolved organisation remains:

`DISCOVERED_ORGANISATION_BUYER_UNIT_PENDING`

with buyer unit state:

`UNRESOLVED_BUYER_UNIT`

It is not a lead, verified buyer unit, consent state, demand claim or outreach permission.

Resolved discoveries are converted into `TargetFeatures` and participate in the same domain-local ranking as curated baselines and the historical Wave 4 prospect registry. The cycle now emits a `seed_supersession` section showing whether fresh discovered target hypotheses actually outranked curated seed priors, which seeds were displaced, and in which ATLAS domains. This is an observational ranking result only. `best_target_claimed` remains false.

Expected MS-1 acceptance label:

`DIO_MARKET_SENSORIUM_DISCOVERY_RESOLUTION_READY`

This label means the resolution/ranking machinery executed. It does not mean seed supersession occurred in the current world-state. The stronger proof is `seed_supersession.seed_supersession_observed=true` with source-bound examples.

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
  tests/test_market_sensorium_queries.py \
  tests/test_market_sensorium_resolution.py

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

The expected foundation acceptance labels are `DIO_MARKET_SENSORIUM_BASELINE_CANDIDATES_READY` and `DIO_MARKET_SENSORIUM_READ_ONLY_CYCLE_READY`. MS-1 additionally emits `DIO_MARKET_SENSORIUM_DISCOVERY_RESOLUTION_READY`. They are not considered locally proven until the Valinor run produces them.

For MS-1, inspect these receipt fields after the cycle:

```text
summary.discovery_resolution.candidates_resolved
summary.discovery_resolution.unique_resolved_target_hypotheses
summary.discovery_resolution.targets_created
summary.discovery_resolution.unresolved_remaining
summary.seed_supersession.discovered_targets_ranked
summary.seed_supersession.seed_targets_outranked
summary.seed_supersession.domains_with_seed_supersession
summary.seed_supersession.seed_supersession_observed
summary.seed_supersession.examples
summary.rank_movers
```

The desired strong result is not a fixed count. It is at least one defensible source-bound discovered organisation entering the ranking and, if the current evidence warrants it, outranking a weaker curated seed with an explainable rank receipt.

## Proof boundary

Market Sensorium may learn **where to look, what to compare, which hypothesis deserves attention and why a rank changed**. It may resolve a public discovery into a rankable organisation hypothesis when the source evidence supports that identity. It may not turn observation into capability, verified buyer-unit identity, lead status, demand, consent, revenue, market validation or authority.
