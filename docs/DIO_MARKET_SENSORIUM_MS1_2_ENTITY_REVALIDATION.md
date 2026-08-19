# DIO Market Sensorium MS-1.2 — Strict Entity Revalidation

Status: IMPLEMENTED / LOCAL VALINOR REAL-DATA VERIFICATION REQUIRED

## Why MS-1.2 exists

MS-1.1 achieved real source-bound entity resolution and real seed supersession, but the first real receipt also exposed false target identities such as content/course/event tokens promoted from bare all-caps headline text.

The observed result therefore contained both real subject organisations and contaminated identities. MS-1.2 treats that as a belief-correction event, not as a reason to erase history.

## New law

```text
all-caps token
!= organisation

YouTube title acronym
!= target identity

prior resolved identity
!= permanently trusted identity
```

Identity confidence remains distinct from market relevance, but identity evidence itself must now survive a stricter source-family revalidation.

## Revalidation behaviour

`market_sensorium/revalidation.py` wraps the source-aware resolver with a second validation pass.

It:

- preserves explicit organisation-field evidence;
- preserves organisation-form headline evidence;
- permits short, source-bound subject acronyms from RSS/news evidence where they survive semantic guards;
- rejects acronym-like content words and course/event labels;
- rejects digit/hyphen event-like acronym shapes unless stronger evidence exists;
- refuses bare YouTube-title acronyms as target identities;
- preserves YouTube channels as market-habitat/provider observations instead;
- revalidates identities that were already promoted by MS-1.1;
- moves failed identities to `REJECTED_ENTITY_RESOLUTION`;
- writes `DISCOVERY_RESOLUTION_INVALIDATION` observations;
- preserves prior resolution lineage in `resolution_history`;
- removes invalidated targets from the current rankable discovered-feature set;
- marks stale target-memory rows `INVALIDATED_ENTITY_RESOLUTION` rather than deleting historical evidence.

## Current truth contract

A clean MS-1 acceptance now requires:

```text
strict_revalidation_complete = true
entity_role_confusion = 0
candidates_resolved > 0
unique_resolved_target_hypotheses > 0
seed_supersession_observed = true
```

The CLI gate becomes:

```text
PENDING_STRICT_ENTITY_REVALIDATION
PENDING_REAL_ENTITY_RESOLUTION
PENDING_REAL_SEED_SUPERSESSION
DIO_MARKET_SENSORIUM_DISCOVERY_RESOLUTION_AND_SEED_SUPERSESSION_VERIFIED
```

The strong verified label is therefore only available after false identities have been removed from the current rankable set.

## Proof boundary

A surviving MS-1.2 target is still only:

```text
RANKABLE_DISCOVERED_TARGET_HYPOTHESIS
```

It is not a verified buyer unit, lead, consent state, demand signal, customer, payment event or authority grant.

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
  tests/test_market_sensorium_source_aware_resolution.py \
  tests/test_market_sensorium_revalidation.py

PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
scripts/run_market_sensorium_cycle.py \
  | tee /tmp/dio-ms1-2-cycle.json

jq '{
  ms1_implementation,
  ms1_acceptance,
  ms1_strict_revalidation_complete,
  ms1_entity_role_confusion,
  ms1_truth,
  discovery_resolution: .summary.discovery_resolution,
  seed_supersession: .summary.seed_supersession,
  rank_movers: .summary.rank_movers[0:20],
  store: .summary.store
}' /tmp/dio-ms1-2-cycle.json
```

Do not refresh public sources before this bounded run. The already captured corpus is sufficient to prove that the contaminated MS-1.1 belief state can be corrected and that seed supersession survives after correction.
