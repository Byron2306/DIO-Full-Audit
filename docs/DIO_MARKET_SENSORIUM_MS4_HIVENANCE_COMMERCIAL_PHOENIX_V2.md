# DIO Market Sensorium MS-4 — Hivenance Commercial Phoenix v2

Status: IMPLEMENTED / LIVE SENSORIUM VERIFICATION REQUIRED

## Purpose

MS-1 established source-bound target discovery. MS-2 established truthful commercial time. MS-3 proved real rank movement with preserved evidence and rank history.

MS-4 turns an observed rank transition into a **competition between commercial explanations**, not a single story.

```text
source-bound MS-3 rank transition
        ↓
Hivenance Commercial Phoenix v2
        ↓
rival commercial hypotheses
        ↓
Michael evidence validation
        +
Loki adversarial alternatives
        +
Metatron synthesis
        ↓
one bounded read-only research test
        ↓
future observation / M2 settlement
```

A selected hypothesis is not market truth. A selected test is not execution authority.

## Hypothesis vocabulary

The engine recognises the following commercial hypothesis classes:

```text
BUYER
OFFER
PRICE
CHANNEL
TIMING
HABITAT
COMPETITION
PRODUCT
PIVOT
```

The vocabulary is broader than the hypotheses emitted on any one cycle. A type is emitted only when the available evidence supports forming that question.

For example, MS-4 does **not** manufacture `PRICE` or `OFFER` hypotheses merely because those types exist. Observed price or offer evidence must exist before those explanations can become evidence-bearing candidates.

## Hivenance inheritance

The earlier Hivenance professional-services lane already established the useful architecture:

- independent evidence workers;
- a market-regime oracle;
- competing hypotheses;
- Michael validation;
- Loki challenge;
- Metatron synthesis;
- Ainur-style research routing;
- no publication, outreach or commerce authority.

MS-4 keeps those laws but moves the trigger from fixed campaign families to **live Sensorium events**.

The engine therefore asks questions such as:

- Did a new organisation target hypothesis enter the field?
- Is the movement a relative-field effect rather than deterioration in the incumbent?
- Is current visibility transient timing?
- Is the connected source mix biasing what is visible?
- Does the movement actually say anything about product fit?
- If a cluster persists, should discovery broaden?
- Is the signal about a habitat/source rather than organisation-level commercial intent?

## Persisted lineage

MS-4 creates two SQLite ledgers:

```text
commercial_hypothesis_sets
commercial_hypotheses
```

Each hypothesis persists:

- its MS-3 transition ID;
- target and domain identity;
- hypothesis type;
- statement and explicit counter-explanation;
- research-priority score;
- Michael validation receipt;
- Loki challenge receipt;
- Metatron synthesis receipt;
- bounded research test;
- evidence references and evidence digest;
- world-state digest;
- stable hypothesis lineage key;
- parent hypothesis ID when the same target/domain/type is revised later;
- `truth_state=UNPROVED`;
- `authority_created=false`.

Historical hypotheses are not overwritten by later revisions.

## Bounded tests

MS-4 may select tests such as:

```text
TRACK_RELATIVE_FIELD_PERSISTENCE
COMPARE_BUYER_ROLE_EVIDENCE
REOBSERVE_AFTER_TIME_ELAPSES
CROSS_SOURCE_CORROBORATION
COMPARE_WORKFLOW_CAPABILITY_FIT
MAP_ADJACENT_TARGET_CLUSTER
COMPARE_HABITAT_VS_ORGANISATION_SIGNAL
```

Every MS-4 test is currently:

```text
mode = READ_ONLY_OBSERVATION_OR_RESEARCH
outreach_permitted = false
publication_permitted = false
spend_permitted = false
join_or_dm_permitted = false
commerce_permitted = false
external_effects = false
authority_created = false
```

## Truth boundaries

MS-4 explicitly preserves:

```text
hypothesis != fact
selected hypothesis != truth
rank movement != demand
new organisation hypothesis != verified buyer unit
seed displacement != market share
target priority != product preference
research test != execution authority
```

No MS-4 receipt proves willingness to pay, customer acceptance, market demand, product-market fit, a verified buyer unit, or commercial success.

## Acceptance

Strong acceptance requires:

```text
persisted source receipt says MS-3 VERIFIED
real rank movements feed Phoenix
one rival hypothesis set per movement
at least three rival explanations per set
all hypotheses source-bound
all hypotheses Michael-validated
all hypotheses Loki-challenged
all hypotheses Metatron-synthesised
one bounded research test selected per set
zero unbounded/authority tests
zero truth promotions
at least three hypothesis types represented
```

Strong token:

`DIO_MARKET_SENSORIUM_HIVENANCE_COMMERCIAL_PHOENIX_V2_VERIFIED`

Important refusal/pending states include:

- `PENDING_VERIFIED_MS3_RECEIPT`
- `PENDING_MS3_DYNAMIC_RANK_INPUT`
- `PENDING_REAL_RANK_MOVEMENT_INPUT`
- `REFUSE_NON_RIVAL_COMMERCIAL_HYPOTHESIS_SET`
- `PENDING_SOURCE_BOUND_COMMERCIAL_HYPOTHESES`
- `REFUSE_INCOMPLETE_HIVENANCE_TRIUNE_CHALLENGE`
- `PENDING_BOUNDED_RESEARCH_TEST_SELECTION`
- `REFUSE_HYPOTHESIS_TRUTH_OR_AUTHORITY_PROMOTION`
- `PENDING_COMMERCIAL_HYPOTHESIS_DIVERSITY`

## Verification

Run the focused tests:

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q \
  tests/test_market_sensorium_rank_transitions.py \
  tests/test_market_sensorium_ms3_gate.py \
  tests/test_market_sensorium_commercial_phoenix.py \
  tests/test_market_sensorium_ms4_gate.py
```

For the **initial MS-4 proof**, do not manufacture another world-state change. The verified MS-3 transition ledger already exists and is the correct input. Run:

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
scripts/run_market_sensorium_ms4.py \
  | tee /tmp/dio-ms4-live.json
```

This runner requires the persisted `MARKET_SENSORIUM_CYCLE_RECEIPT.json` to carry the strong MS-3 acceptance token and then reasons over the persisted MS-3 rank-transition ledger. It writes `state/market_sensorium/MARKET_SENSORIUM_MS4_RECEIPT.json` and performs no external effect.

Use the compact inspection view:

```bash
jq '{
  ms3: .ms3_acceptance,
  ms4: .ms4_acceptance,
  ms4_truth: .ms4_truth,
  top3: [
    (.summary.commercial_phoenix.examples // [])[]
    | {
        org: .organisation,
        domain: .domain_id,
        move: .rank_move,
        rivals: .rival_count,
        types: .hypothesis_types,
        selected: .selected_hypothesis_type,
        test: .selected_test_kind,
        sources: .source_units,
        crossing_evidence: .crossing_targets_with_evidence
      }
  ][0:3]
}' /tmp/dio-ms4-live.json
```

After initial verification, normal `scripts/run_market_sensorium_cycle.py` runs MS-4 automatically after the MS-3 rank pass. If no new rank movement occurs, the current cycle's MS-3 gate may correctly remain pending; that does not erase the separately persisted verified MS-3 or MS-4 receipts.

A high research-priority score remains only a routing score. It is never a probability of truth or a commercial success score.
