# DIO Market Sensorium MS-3 — Dynamic Rank-Movement Proof

Status: IMPLEMENTED / LIVE WORLD-STATE VERIFICATION REQUIRED

## Purpose

MS-1 proved source-bound discovery and seed supersession. MS-2 established a truthful commercial clock. MS-3 makes rank change a governed temporal object rather than a display side effect.

The required chain is:

```text
prior ranked state
  -> new bounded observations / changed target features / changed competitive field
  -> deterministic score and rank pass
  -> persisted transition receipt
  -> exact prior/current lineage remains inspectable
```

A changed rank is not itself market demand, buyer intent, commercial validation, or execution authority.

## Transition ledger

`market_sensorium/rank_transitions.py` creates `rank_transitions` in the Sensorium SQLite store.

Each transition persists:

- previous and current rank;
- previous and current score;
- previous and current feature snapshots;
- feature snapshot digests;
- feature deltas and their deterministic score effects;
- relative field crossings such as targets passed, targets passing the subject, new entries ahead, and previously ranked competitors no longer present;
- source-bound observation references and provenance digests;
- previous and current rank-receipt IDs;
- an evidence digest and current world-state digest;
- explicit `authority_created=false` and `market_demand_claimed=false` boundaries.

## Rank-change classes

MS-3 distinguishes:

```text
FEATURE_AND_RELATIVE_FIELD_MOVEMENT
FEATURE_DRIVEN_RANK_MOVEMENT
RELATIVE_FIELD_RANK_MOVEMENT
SCORE_DRIVEN_RANK_MOVEMENT
UNEXPLAINED_RANK_MOVEMENT
SCORE_OR_FEATURE_CHANGE_RANK_STABLE
NO_MATERIAL_CHANGE
INITIAL_RANK_ENTRY
```

`UNEXPLAINED_RANK_MOVEMENT` is a refusal condition for final MS-3 acceptance.

## Relative-field truth

Rank is relative. A target can move while its own feature vector remains unchanged because another target entered, disappeared from the current rankable field, or crossed it.

MS-3 therefore records both direct feature changes and field crossings. It does not falsely attribute every rank delta to the subject target's own score.

## Evidence immutability

The MS-3 runtime fingerprints the observation ledger immediately before and after ranking.

A rank pass must not rewrite, delete, or mutate source observations. If the observation-ledger fingerprint changes during rank learning, MS-3 refuses the result.

The transition layer also repairs the older `rank()` metadata-overwrite behavior by restoring pre-ranking identity and temporal metadata and merging the new rank metadata into it. Historical evidence is not rewritten.

## Acceptance

The live gate is intentionally stronger than the unit tests.

Strong acceptance requires:

```text
historical ranked state exists
rank movement observed
all rank movement source-bound
unexplained rank movement = 0
prior rank receipts preserved
observation ledger unchanged by ranking
market demand claimed = false
authority created = false
```

Strong token:

`DIO_MARKET_SENSORIUM_DYNAMIC_RANK_MOVEMENT_VERIFIED`

Pending states include:

- `PENDING_SECOND_RANK_OBSERVATION`
- `PENDING_DYNAMIC_RANK_MOVEMENT`
- `PENDING_SOURCE_BOUND_RANK_MOVEMENT_EVIDENCE`

Refusal states include:

- `REFUSE_RANK_HISTORY_OR_EVIDENCE_MUTATION`
- `REFUSE_UNEXPLAINED_RANK_MOVEMENT`

## Verification

Run the deterministic proof tests first:

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q \
  tests/test_market_sensorium_rank_transitions.py
```

Then run a live public refresh so MS-3 has a chance to observe a real world-state change rather than manufacturing one:

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
scripts/run_market_sensorium_cycle.py \
  --refresh-public \
  --refresh-mail \
  | tee /tmp/dio-ms3-live.json
```

Inspect:

```bash
jq '{
  ms1_acceptance,
  ms2_acceptance,
  ms3_implementation,
  ms3_acceptance,
  ms3_truth,
  rank_transitions: .summary.rank_transitions,
  rank_movers: .summary.rank_movers[0:20],
  store: .summary.store
}' /tmp/dio-ms3-live.json
```

If the public world has not changed enough to move a rank, `PENDING_DYNAMIC_RANK_MOVEMENT` is the correct result. MS-3 must not perturb production evidence merely to manufacture a passing receipt.
