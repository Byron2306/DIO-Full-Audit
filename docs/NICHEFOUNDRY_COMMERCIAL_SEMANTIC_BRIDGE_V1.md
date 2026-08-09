# NicheFoundry -> DIO Commercial Semantic Bridge v1

## Purpose

C2 preserves NicheFoundry's opportunity and audience semantics when they enter DIO commercial orchestration.

The bridge exists to prevent two distinct failures:

1. rich NicheFoundry audience/opportunity reasoning being flattened into a thin campaign row; and
2. numeric priors, heuristics or model scores being mistaken for observed market facts.

The governing rule is:

> A score is not an observation. A persona is not a customer. A hypothesis is not a fact.

## Flow

```text
DIO campaign / Hivenance hypothesis
        |
        v
foundry_opportunity.json
        |
        v
signal sanitizer
        |
        +-- unproven supplied number -> removed
        |
        +-- evidence-bearing supplied number -> retained
        v
NicheFoundry opportunity scorer
        |
        +-- normalized signals + provenance
        +-- opportunity score + decision
        v
NicheFoundry audience-fit engine
        |
        +-- persona
        +-- viewer job
        +-- content pillar
        +-- value proposition
        +-- desired reward
        +-- likely next action
        v
COMMERCIAL_SEMANTIC_OBJECT.json
```

## Market signal authority

DIO uses three signal states.

### `observed`

An observed signal requires all of the following:

- a numeric value;
- one or more source references;
- an explicit measurement identity; and
- an observation timestamp.

Example:

```json
{
  "value": 0.66,
  "state": "observed",
  "source_refs": ["market_observation:LIVE-OBS-1"],
  "provenance": "youtube_public_connector",
  "measurement": "normalized_relevant_public_video_demand_sample",
  "observed_at": "2026-08-09T20:00:00+00:00"
}
```

### `derived`

A derived signal requires provenance and a derivation method. This includes:

- NicheFoundry `documented_proxy_heuristic` values;
- studio-fit engine scores;
- operator/provider values whose measurement authority has not been resolved; and
- combined opportunity scores, confidence, benefit and risk indices.

### `unknown`

Unknown carries no numeric placeholder. Its value is `null`.

## Sanitization boundary

`scripts/score_nichefoundry_opportunity.js` rejects supplied numeric signals that do not carry a matching `signal_evidence` record.

Accepted observed evidence:

```json
{
  "signals": {
    "audience_demand": 0.66
  },
  "signal_evidence": {
    "audience_demand": {
      "state": "observed",
      "value": 0.66,
      "measurement": "normalized_relevant_public_video_demand_sample",
      "observed_at": "2026-08-09T20:00:00+00:00",
      "source_refs": ["market_observation:LIVE-OBS-1"]
    }
  }
}
```

Accepted derived evidence:

```json
{
  "signals": {
    "series_potential": 0.72
  },
  "signal_evidence": {
    "series_potential": {
      "state": "derived",
      "value": 0.72,
      "provenance": "operator_prior",
      "method": "declared_campaign_prior_v1",
      "source_refs": ["campaign:CMP-123"]
    }
  }
}
```

A naked number is removed before scoring. The sanitized `foundry_opportunity.json` is written back to disk so the campaign artifact itself no longer carries unsupported precision. NicheFoundry may then calculate a missing value using its documented proxy heuristic, but DIO projects that value as `derived`, never `observed`.

## Audience semantics

The bridge preserves NicheFoundry audience-fit fields under `market_context.audience`:

- public segment;
- primary persona;
- viewer job;
- content pillar;
- desired reward; and
- likely next action.

A target persona remains `inferred` strategy. It does not establish the identity, role, organisation, pain, scope, consent or budget of a real customer.

## Pre-lead CSOs

C2 permits a Commercial Semantic Object to exist before a lead exists. Pre-lead lineage may be anchored by:

- `campaign_id`;
- `hypothesis_id`; or
- `opportunity_id`.

A pre-lead CSO deliberately leaves customer identity and customer-specific commercial facts unknown.

## Output

After NicheFoundry scoring, DIO automatically projects:

```text
COMMERCIAL_SEMANTIC_OBJECT.json
```

into the campaign directory. Existing marketing and phase receipts are updated with:

- CSO filename;
- CSO ID;
- authority state; and
- counts of observed, derived and unknown market signals.

## C2 gate

C2 is satisfied when:

1. unsupported fixed market scores cannot survive the scoring boundary as supplied evidence;
2. the sanitized opportunity artifact no longer contains unsupported numeric priors;
3. NicheFoundry proxy/engine values are labelled derived;
4. only explicit measurements can become observed;
5. persona, viewer job, pillar, reward and next action survive the handoff;
6. audience strategy cannot become verified buyer identity or customer pain; and
7. the resulting object validates against `dio.commercial_semantic_object.v1`.

C2 does not yet choose final rhetoric or replace the outbound writer. That is C3.
