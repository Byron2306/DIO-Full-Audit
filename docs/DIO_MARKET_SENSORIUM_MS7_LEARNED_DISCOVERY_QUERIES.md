# DIO Market Sensorium MS-7 — Learned Discovery Queries

Status: IMPLEMENTED / LIVE SENSORIUM VERIFICATION REQUIRED

## Purpose

MS-1 taught the Sensorium to resolve source-bound market entities. MS-2 gave it truthful commercial time. MS-3 proved dynamic rank movement. MS-4 formed rival commercial hypotheses. MS-5 observed provider offers and advertised price states. MS-6 mapped market habitats while preserving permission boundaries.

MS-7 closes the first discovery feedback loop:

```text
settled Sensorium evidence
        ↓
weak domains + unresolved entities + productive habitats
+ competitive offers + Hivenance research questions
        ↓
DETERMINISTIC ADAPTIVE QUERY SYNTHESIS
        ↓
source-bound next-search candidates
        ↓
bounded selection
        ↓
LEARNED_DISCOVERY_QUERY_PLAN.json
        ↓
next explicitly requested --refresh-public cycle
        ↓
public YouTube / RSS observation
        ↺
```

“Learned” means **the deterministic query policy changes because observed evidence changed**. MS-7 does not claim that a statistical or neural model was trained.

## Separation of query formation and execution

MS-7 itself performs no search.

A selected query has:

```text
query_execution_performed = false
execution_authority = NONE
authority_created = false
```

The existing `--refresh-public` cycle remains the only path that may execute a bounded public read through the already-governed connectors. The query scheduler automatically uses an MS-7 learned plan when present and falls back to the prior static domain template otherwise.

Therefore:

```text
query selected != query executed
query executed != lead created
search hit != organisation identity
search hit != buyer
search hit != demand
query priority != market truth
```

## Evidence drivers

MS-7 may form candidates from these evidence classes:

- `BASELINE_GAP` — ATLAS domain remains family-fallback-only;
- `ENTITY_RESOLUTION` — unresolved public discoveries need better organisation-role evidence;
- `HABITAT_CORROBORATION` — public source/habitat evidence exists and should be corroborated across recurring sources;
- `COMPETITIVE_OFFER` — provider-owned offers or advertised price states justify deeper read-only offer research;
- `HIVENANCE_RESEARCH_TEST` — an active bounded Hivenance question can be converted into a public discovery query without treating the hypothesis as truth;
- `BROADEN_DISCOVERY` — conservative fallback when no stronger adaptive evidence driver exists.

The engine deliberately does not insert individual Google News article URLs into query text. Content endpoints may contribute source evidence, but the learned query asks for recurring source/provider/organisation patterns rather than treating one article as a durable market habitat.

## Persisted lineage

MS-7 adds:

```text
learned_query_events
learned_query_memory
```

Every candidate persists:

- stable query ID;
- domain identity;
- query kind;
- query text;
- rationale;
- evidence references;
- evidence digest;
- source-driver count;
- novelty score against the prior executed domain query;
- parent query ID when the same domain receives a later selected query;
- selected/not-selected state;
- `execution_performed=0`;
- `authority_created=0`;
- `market_demand_claimed=0`.

The selected plan is written to:

`state/market_sensorium/LEARNED_DISCOVERY_QUERY_PLAN.json`

## Bounded exploration

MS-7 selects at most one query per domain and caps the total selected domains. The initial proof cap is eight.

The old scheduler remains as the fallback. If a valid learned plan exists, learned domains are consumed first in their evidence-ranked order. Any unused slots are filled by the previous weak-domain/least-recently-refreshed scheduler.

This prevents two opposite failures:

1. **stagnation**, where DIO repeats the original template forever;
2. **query explosion**, where every observation generates unbounded new searches.

## Truth boundaries

MS-7 preserves:

```text
adaptive query != correct query
selected query != best market query
search result != lead
search volume != demand
habitat visibility != consent
provider offer != customer acceptance
Hivenance hypothesis != fact
query execution != outreach authority
```

No MS-7 object proves market demand, willingness to pay, buyer identity, customer acceptance, product-market fit, or commercial success.

## Acceptance

Strong acceptance requires:

```text
persisted MS-6 receipt VERIFIED
candidate queries generated > 0
selected queries > 0
selected queries <= exploration cap
all selected queries source-bound
at least one evidence-adaptive selected query
at least one novel selected query
at least two query-driver classes represented
source-driver count >= selected query count
query execution performed = false
zero truth/lead/demand/authority inflation
```

Strong token:

`DIO_MARKET_SENSORIUM_LEARNED_DISCOVERY_QUERIES_VERIFIED`

Important pending/refusal states include:

- `PENDING_VERIFIED_MS6_RECEIPT`
- `PENDING_LEARNED_DISCOVERY_QUERY_EVIDENCE`
- `REFUSE_UNBOUNDED_QUERY_EXPLORATION`
- `PENDING_SOURCE_BOUND_QUERY_CAUSALITY`
- `PENDING_EVIDENCE_ADAPTIVE_QUERY_SELECTION`
- `PENDING_QUERY_NOVELTY`
- `PENDING_QUERY_DRIVER_DIVERSITY`
- `REFUSE_QUERY_TRUTH_OR_AUTHORITY_INFLATION`

## Verification

Run:

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q \
  tests/test_market_sensorium_query_learning.py \
  tests/test_market_sensorium_ms7_gate.py
```

Then synthesize the first learned plan from the already verified MS-6 state:

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
scripts/run_market_sensorium_ms7.py \
  | tee /tmp/dio-ms7-live.json
```

Compact inspection:

```bash
jq '{
  ms6: .ms6_acceptance,
  ms7: .ms7_acceptance,
  ms7_truth: .ms7_truth,
  queries: [
    (.summary.learned_queries.examples // [])[]
    | {
        domain: .domain_id,
        name: .domain_name,
        kind: .query_kind,
        query,
        novelty: .novelty_score,
        drivers: .source_driver_count,
        previous: .previous_query
      }
  ][0:8]
}' /tmp/dio-ms7-live.json
```

After MS-7 verifies, the next explicitly requested `scripts/run_market_sensorium_cycle.py --refresh-public` automatically consumes the learned query plan. The plan itself never grants execution authority.