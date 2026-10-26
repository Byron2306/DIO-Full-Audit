# DIO Market Sensorium MS-9 — Autonomic Multi-Cycle Soak

**Implementation state:** `DIO_MARKET_SENSORIUM_AUTONOMIC_MULTI_CYCLE_SOAK_IMPLEMENTED`

**Strong acceptance token:** `DIO_MARKET_SENSORIUM_AUTONOMIC_MULTI_CYCLE_SOAK_VERIFIED`

MS-9 is the final bounded gauntlet for the Market Sensorium programme. It does not add a new commercial reasoning organ. It repeatedly exercises the already-built read-only organism and checks that evidence, temporal truth, ranking, hypotheses, offers, habitats, adaptive queries, cockpit truth classes and authority boundaries survive repetition without semantic drift.

## Loop under test

```text
learned query plan from prior settled evidence
        ↓
public-source refresh + mailbox refresh
        ↓
source-bound ingestion
        ↓
strict entity resolution
        ↓
dynamic ranking + transition lineage
        ↓
Hivenance rival commercial hypotheses
        ↓
competitive offer observation
        ↓
market habitat classification
        ↓
MS-7 relearns the NEXT bounded query plan
        ↓
MS-8 reconstructs the truth-aware cockpit
        ↓
MS-9 snapshots invariants
        ↺ next cycle
```

A query learned after cycle N is therefore eligible for governed public execution in cycle N+1. MS-9 never counts a newly synthesized query as already executed in the same pass.

## Strong gate

The default strong soak is three cycles. Every strong cycle must:

- complete the existing governed public read lane;
- complete the existing mailbox read lane;
- execute at least one MS-7 learned discovery query through the public refresh scheduler;
- bind the executed learned query back into query history;
- keep MS-2 in continuous observation-active or verified state;
- rebuild an MS-8 cockpit that remains verified;
- preserve all pre-soak historical event semantics;
- keep event-ledger counts non-decreasing;
- preserve Hivenance hypotheses as `UNPROVED`;
- preserve advertised offer/price evidence as observations rather than demand, realised price or willingness to pay;
- preserve public habitat visibility as observation rather than consent, membership, posting or DM authority;
- preserve the no-follow-up-from-silence boundary;
- create no outreach, publication, spend, membership, posting, DM, commerce or other external-effect authority.

## Historical integrity guards

MS-9 uses two guard classes.

### Strict append-only prefix guard

Used for:

- `observations`
- `rank_transitions`
- `competitive_offer_events`
- `habitat_intelligence_events`
- `learned_query_events`

The complete pre-soak SQLite rowid prefix is fingerprinted. New rows may append, but the guarded prefix may not change or disappear.

### Semantic replay guard

Used for:

- `commercial_hypotheses`
- `commercial_hypothesis_sets`

Hivenance may deterministically replay an already-known hypothesis object through SQLite `INSERT OR REPLACE`. Physical row placement is therefore not treated as epistemic history. Instead, every pre-soak semantic member fingerprint must remain present unchanged. New hypothesis revisions may be added, but old belief semantics may not be rewritten.

## Stable-world law

MS-9 does **not** require ranks, learned queries, offers, hypotheses or public observations to change on every cycle.

```text
no world change
    ≠ failed learning
    ≠ failed autonomy
```

A stable world is allowed to produce a stable query plan and stable ranking field. The proof requirement is that the already-learned query is genuinely executed, the evidence loop genuinely runs, and the organism settles the result without fabricating novelty.

## Commercial-time law

No-reply remains coverage-bound observation.

```text
NO_REPLY_OBSERVED
    ≠ rejection
    ≠ lack of demand
    ≠ follow-up permission
```

A legitimate Graph continuity reset may establish a new observation epoch. MS-9 does not require the original `continuous_from` value to survive every infrastructure reset. It requires the current state to be `CONTINUOUS`, unsupported no-reply inference to remain zero, and age-only silence inference to remain unused.

## Acceptance refusal conditions

The gauntlet refuses if it detects:

- historical event-ledger mutation or event-count regression;
- hypothesis truth promotion without evidence settlement;
- evidence-to-demand or advertised-price-to-WTP inflation;
- public-visibility-to-consent/permission inflation;
- age-only or unsupported silence inference;
- an upstream phase returning a `REFUSE_*` state;
- truth-class collapse in the MS-8 cockpit;
- any new execution authority or external effect created by the Sensorium.

It remains pending if the required number of cycles, public read refreshes, mailbox refreshes, continuous commercial-time cycles, learned-query executions or verified cockpit reconstructions are not present.

## Scope boundary

A successful MS-9 receipt proves a **bounded multi-cycle read-only autonomic soak**. It does not prove long-duration unattended endurance, commercial success, market demand, realised pricing, willingness to pay, repeatability of customer acquisition, or production authority.

The receipt therefore explicitly carries:

```text
long_duration_endurance_proved = false
market_demand_claimed = false
willingness_to_pay_proved = false
commercial_success_proved = false
customer_claimed = false
authority_created = false
external_effects = false
```

## Runner

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
scripts/run_market_sensorium_ms9.py --cycles 3
```

The strong runner refreshes public intelligence and mail by default. Diagnostic runs may disable either lane with `--no-refresh-public` or `--no-refresh-mail`, but such runs cannot satisfy the strong MS-9 gate.

Artifacts:

```text
state/market_sensorium/MARKET_SENSORIUM_MS9_RECEIPT.json
state/market_sensorium/MS9_SOAK_LEDGER.jsonl
state/market_sensorium/ms9_soak/<session-id>/IMMUTABLE_BASELINE.json
state/market_sensorium/ms9_soak/<session-id>/cycle-01.json
...
state/market_sensorium/ms9_soak/<session-id>/FINAL_RECEIPT.json
```
