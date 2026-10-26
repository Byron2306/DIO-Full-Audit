# DIO Market Sensorium MS-1.1 — Source-Aware Entity Resolution

Status: IMPLEMENTED / LOCAL VALINOR REAL-DATA VERIFICATION REQUIRED

## Why MS-1.1 exists

The first MS-1 resolver passed its synthetic gauntlet but resolved `0/53` real discovery candidates. The source-shape audit showed why:

- candidate market relevance had been incorrectly used as a gate for identity extraction;
- real Google News/RSS observations often expose `title`, `description`, `link`, `feed_title` and related fields rather than an explicit `organisation` field;
- compressed campaign opportunities preserve provenance in `source_hints` rather than a simple `link` field;
- YouTube opportunities may need to be rehydrated from their source `LIVE_MARKET_SIGNALS.json` record to recover channel and source context;
- publisher/provider identity is not the same thing as target/buyer identity.

MS-1.1 separates these dimensions instead of weakening the evidence threshold.

## Constitutional separation

```text
identity confidence
!= market relevance
!= buyer-role confidence
!= target rank
!= lead status
!= demand
!= authority
```

A low-scoring observation may still identify a named organisation. Resolving that identity does not increase the observation's market score and does not create a buyer unit, lead, contact permission, demand claim or authority.

## Source-aware resolution

`market_sensorium/resolution.py` now supports:

1. explicit organisation fields where a source provides them;
2. organisation-form extraction from headlines independent of market score;
3. conservative subject-acronym extraction for named entities such as `NSFAS`, `SAPS`, `IEB`, `PAMA` or similar source-bound subjects;
4. a generic/domain acronym stop-list so terms such as `CAPS`, `NGO`, `PIP`, `AI`, `SDG`, `TVET` and similar tokens are not promoted as organisations;
5. publisher-suffix and publisher-acronym exclusion so a source such as `WIPO - World Intellectual Property Organization` is not automatically treated as the target organisation;
6. `source_hints` as provenance-bearing links;
7. rehydration of compressed `MARKET_OPPORTUNITY` records from the referenced `LIVE_MARKET_SIGNALS.json` file where possible;
8. explicit non-target source roles such as `PUBLISHER_OR_PROVIDER` and `MARKET_HABITAT_OR_PROVIDER`.

## Entity-role law

A public record may expose several entities at once:

```text
SUBJECT_ORGANISATION       -> may become a rankable target hypothesis
PUBLISHER_OR_PROVIDER      -> source/market actor; not auto-promoted
MARKET_HABITAT_OR_PROVIDER -> channel/community/provider observation; not auto-promoted
```

Publisher/channel observations are written as `DISCOVERY_ENTITY_ROLE` observations with `target_promoted=false`.

## Target truth class

A successfully resolved subject may become:

```text
RANKABLE_DISCOVERED_TARGET_HYPOTHESIS
```

with:

```text
buyer_unit_state = UNRESOLVED_BUYER_UNIT
lead_created = false
market_demand_claimed = false
authority_created = false
```

## Receipt semantics

`scripts/run_market_sensorium_cycle.py` now derives an evidence-bearing MS-1 gate:

- `PENDING_REAL_ENTITY_RESOLUTION` when no real discovery resolves;
- `PENDING_REAL_SEED_SUPERSESSION` when real entities resolve but none outrank a seed;
- `DIO_MARKET_SENSORIUM_DISCOVERY_RESOLUTION_AND_SEED_SUPERSESSION_VERIFIED` only when real resolved discovery evidence actually supersedes at least one curated seed prior.

The implementation label remains separately visible as:

```text
DIO_MARKET_SENSORIUM_SOURCE_AWARE_RESOLUTION_IMPLEMENTED
```

## Verification

```bash
cd /home/byron/DIO-Full-Audit

git fetch origin
git checkout agent/dio-atlas-m4-universal-pivot
git pull --ff-only origin agent/dio-atlas-m4-universal-pivot

PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q \
  tests/test_market_sensorium.py \
  tests/test_market_sensorium_queries.py \
  tests/test_market_sensorium_resolution.py \
  tests/test_market_sensorium_source_aware_resolution.py

PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
scripts/audit_market_sensorium_unresolved.py \
  --samples 30 \
  | tee /tmp/dio-ms1-1-audit.json

PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
scripts/run_market_sensorium_cycle.py \
  | tee /tmp/dio-ms1-1-cycle.json

jq '{
  ms1_implementation,
  ms1_acceptance,
  ms1_truth,
  discovery_resolution: .summary.discovery_resolution,
  seed_supersession: .summary.seed_supersession,
  rank_movers: .summary.rank_movers[0:20],
  store: .summary.store
}' /tmp/dio-ms1-1-cycle.json
```

Do not refresh the public Internet before this bounded run. The existing unresolved corpus is sufficient to prove whether the source-aware resolver can extract real target hypotheses from already captured evidence.

## Strong acceptance

MS-1.1 is not accepted merely because extraction returns a positive number. The strong milestone remains:

```text
real source-bound discovery
-> subject organisation resolved
-> publisher/provider kept separate
-> rankable target hypothesis
-> discovered target outranks at least one curated seed
-> rank receipt explains the result
-> no lead/demand/authority minted
```
