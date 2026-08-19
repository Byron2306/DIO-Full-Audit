# DIO Market Sensorium MS-2 — Commercial Time and Reply Truth

Status: IMPLEMENTED / REAL MAIL-OBSERVATION VERIFICATION REQUIRED

## Purpose

MS-1 proved that DIO can discover source-bound organisations outside the curated seed registry and allow defensible discoveries to supersede weak priors.

MS-2 gives that commercial map **time**.

The critical distinction is:

```text
days since email was sent
!=
no reply observed
```

A send timestamp proves contact age. It does not prove silence. `NO_REPLY_OBSERVED` requires an actual inbox-observation interval.

## Constitutional law

```text
contact age is factual
silence is observational
rejection is explicit
engagement is not consent
consent is not send authority
no reply never creates follow-up authority
```

The current once-off permission-safe outreach model therefore remains intact. A silence state may change research priority, but it never authorises another email.

## Coverage model

`market_sensorium/mail_refresh.py` wraps the existing Microsoft Graph inbox delta pull and writes:

`state/microsoft_graph/mail_observation_coverage.json`

A successful initial sync establishes **prospective** continuous coverage from that successful sync onward.

It deliberately records:

```text
historical_complete = false
retroactive_no_reply_claim_allowed = false
```

Therefore an email sent before coverage began may only become:

`NO_REPLY_OBSERVED_SINCE_COVERAGE_START`

It may not become:

`NO_REPLY_OBSERVED_SINCE_SEND`

unless the send itself occurred inside the continuous observation window.

## Temporal truth states

A contacted target can project one of the following states:

```text
REPLY_OBSERVED
OBSERVATION_COVERAGE_INSUFFICIENT
OBSERVATION_WINDOW_NOT_YET_ELAPSED
NO_REPLY_OBSERVED_SINCE_COVERAGE_START
NO_REPLY_OBSERVED_SINCE_SEND
```

The older contextual silence stages remain useful only **inside a proven observation window**:

```text
WAITING
SILENCE_OBSERVED
WEAK_NEGATIVE_SIGNAL
CHANNEL_OFFER_DECAY
DORMANT
```

The penalty clock runs from the beginning of the proven observation window, not blindly from the email send timestamp.

## Reply semantics

MS-2 separates reply engagement from consent.

Examples:

```text
"This looks interesting. Tell me more."
-> REPLIED_POSITIVE
-> consent UNKNOWN

"Yes, please send the proof pack."
-> REPLIED_POSITIVE
-> consent YES

"No thanks, this is not a fit for us."
-> REPLIED_NEGATIVE
-> consent NO for the current route/offer context

"Please remove me and do not contact me again."
-> OPT_OUT
-> consent NO
```

A reply is direct evidence and does not require a continuous no-reply coverage window to be observed.

## Ranking effect

Observed silence may lower a target score only after observation coverage exists. A rejection may apply a stronger contextual penalty. Positive engagement may increase prior-engagement evidence.

Every such change remains:

```text
context-bound
source-bound
authority-free
```

No temporal state creates SEND, DM, JOIN, PUBLISH, SPEND or other external-effect authority.

## Implementation

New components:

- `market_sensorium/mail_time.py`
- `market_sensorium/mail_refresh.py`
- `market_sensorium/temporal_ingest.py`
- `tests/test_market_sensorium_commercial_time.py`

The normal `scripts/run_market_sensorium_cycle.py` entrypoint now:

1. preserves the MS-1.2 strict resolver;
2. uses MS-2 temporal prospect ingestion;
3. extends Graph observation coverage when `--refresh-mail` is requested;
4. emits an explicit `ms2_acceptance` projection.

## MS-2 gate

Possible top-level states:

```text
PENDING_SENT_MAIL_EVIDENCE
REFUSE_UNSUPPORTED_NO_REPLY_INFERENCE
PENDING_MAIL_OBSERVATION_COVERAGE
PENDING_COMPLETE_MAIL_OBSERVATION_COVERAGE
DIO_MARKET_SENSORIUM_COMMERCIAL_TIME_OBSERVATION_ACTIVE
DIO_MARKET_SENSORIUM_COMMERCIAL_TIME_AND_REPLY_TRUTH_VERIFIED
```

The strong verified state requires continuous observation coverage, zero unsupported no-reply inference, and at least one real temporal commercial effect from either an observed reply or an observation-bound silence penalty.

This prevents a freshly-created coverage window from being called a completed temporal proof merely because the plumbing works.

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
  tests/test_market_sensorium_revalidation.py \
  tests/test_market_sensorium_commercial_time.py

PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
scripts/run_market_sensorium_cycle.py \
  --refresh-mail \
  | tee /tmp/dio-ms2-cycle.json

jq '{
  ms1_acceptance,
  ms2_implementation,
  ms2_acceptance,
  ms2_truth,
  mail_ingress_refresh: .summary.mail_ingress_refresh,
  prospects: .summary.prospects,
  rank_movers: .summary.rank_movers[0:20],
  store: .summary.store
}' /tmp/dio-ms2-cycle.json
```

If Graph is not currently configured, the correct result is `PENDING_MAIL_OBSERVATION_COVERAGE`, not a fabricated silence state.

If Graph is configured and this is the first MS-2 coverage-aware pull, the likely result is `DIO_MARKET_SENSORIUM_COMMERCIAL_TIME_OBSERVATION_ACTIVE`. That is correct: the clock has started, but DIO has not yet earned a mature silence claim.
