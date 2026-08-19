# DIO Market Sensorium × Hivenance Phoenix Hypothesis Engine

Status: DESIGN CONTRACT / companion to `DIO_MARKET_SENSORIUM_AUTONOMIC_DISCOVERY_AND_COMPETITIVE_INTELLIGENCE.md`

## Purpose

Hivenance Phoenix must not be reduced to its historical crypto/trading origins inside DIO. Its reusable value is the hypothesis machinery: independent workers, regime classification, competing hypotheses, adversarial challenge, synthesis, council recommendation, outcome settlement and memory.

The market Sensorium should use Hivenance as the governed hypothesis engine between observation and action recommendation.

## Constitutional role

Hivenance does not create commercial truth, market demand, authority or product capability.

It may:

- generate bounded hypotheses from source-bound observations;
- compete multiple explanations/strategies against the same evidence;
- classify current market regime/context;
- rank testable hypotheses;
- revise or retire hypotheses as new evidence arrives;
- preserve chronology and prior hypothesis state;
- settle hypotheses against observed outcomes;
- feed context-bound learning back into BEAST, LINGUA, ATLAS and target ranking.

It may not:

- publish;
- send or follow up commercially without authority;
- spend;
- join communities as the operator;
- create consent;
- infer WTP or demand from public attention alone;
- convert silence into universal rejection;
- convert competitor activity into proof of competitor success;
- widen a product's authority or capability ceiling.

## The reusable Phoenix pattern

```text
OBSERVATIONS
  ATLAS domain/morphology
  buyer registry
  YouTube
  news/RSS
  Meta/ad observations
  classified/competitive offers
  jobs/tenders/grants
  community/habitat observations
  prior outreach + silence + replies
  measured campaign outcomes
        |
        v
INDEPENDENT WORKERS
        |
        v
MARKET REGIME / CONTEXT ORACLE
        |
        v
COMPETING HYPOTHESES
        |
        v
MICHAEL VALIDATION
+ LOKI CHALLENGE
+ METATRON SYNTHESIS
        |
        v
AINUR / HIVENANCE COUNCIL
        |
        +--> TEST
        +--> REFINE
        +--> HOLD
        +--> OBSERVE MORE
        +--> PIVOT ATTENTION
        |
        v
AUTHORITY GATE
        |
        v
BOUND ACT OR HOLD
        |
        v
M2 SETTLEMENT
        |
        v
OUTCOME MEMORY
        |
        +---------------------> NEXT HYPOTHESIS CYCLE
```

## Hivenance hypothesis classes

The Sensorium should allow Hivenance to generate and compete at least these hypothesis families:

### Buyer hypotheses

- this organisation/buyer unit currently has the problem;
- this buyer class is a better fit than the seed exemplar class;
- the organisation is relevant but the observed route is weak;
- a new event has temporarily increased problem intensity;
- the buyer is morphologically strong but commercially cold.

### Offer hypotheses

- proof-led positioning will outperform generic automation positioning;
- premium evidence/assurance framing is more credible than low-price framing;
- a simpler bounded offer is more appropriate for this buyer;
- current DIO packaging is over-broad or under-specific;
- competitor pitch saturation creates candidate whitespace for a different angle.

### Channel hypotheses

- YouTube/search demand is stronger than direct outreach for this morphology;
- partnership/channel access is more appropriate than cold email;
- a professional community is a higher-value habitat than a static contact list;
- public social attention is high but buyer-role density is low;
- a permission-first route should be preferred over a broad commercial send.

### Pricing hypotheses

- the observed asking-price cluster supports a premium test;
- DIO is positioned above/below comparable advertised offers;
- fixed-fee vs per-unit vs subscription packaging deserves a bounded test;
- price is not yet testable because comparable observations are too heterogeneous.

### Timing hypotheses

- a newly observed grant, contract, policy change, vacancy or programme launch raises current relevance;
- a target should decay because signals are stale;
- silence after a once-off consent request reduces this channel/offer hypothesis;
- a dormant target should revive because a fresh trigger changed context.

### Product/pivot hypotheses

- an ATLAS candidate has enough observed market adjacency to merit investigation;
- a current product should pivot audience, pitch, channel or artifact package;
- a negative M2 outcome should redirect attention to a different ATLAS domain/morphology;
- a candidate should remain HOLD because current evidence is only analogical.

## Memory law

Every Hivenance hypothesis must be versioned and time-bound.

Suggested lineage:

```text
hypothesis_id
hypothesis_family
entity_scope
product_or_candidate_id
domain_ids
morphology_signature
created_at
last_revised_at
source_observation_ids
prior_hypothesis_id
regime
score
confidence_class
admission_state
challenge_state
council_recommendation
operator_decision
settlement_state
outcome_evidence_ids
rank_effect
retirement_reason
```

A revised hypothesis must never overwrite the previous belief. DIO should be able to answer:

- what did Hivenance believe at the time?
- what evidence was available then?
- what changed later?
- why did the rank or recommendation move?
- did the eventual outcome support, weaken or fail to test the hypothesis?

## The "crypto bees" inheritance

The valuable inheritance from Phoenix is not coin selection itself. It is the discipline of competing economic hypotheses under changing regimes and refusing promotion when persistence/evidence is absent.

That same machinery now becomes domain-general:

```text
OLD PHOENIX
market regime
-> competing trading hypotheses
-> adversarial validation
-> shadow/test gate
-> measured outcome
-> promotion/hold

DIO COMMERCIAL PHOENIX
market context
-> competing buyer/offer/channel/product hypotheses
-> adversarial validation
-> bounded market experiment
-> measured response
-> M2 settlement
-> rank/pivot/hold
```

The constitutional invariant remains: hypothesis quality may change what DIO investigates next, but no hypothesis can directly authorize consequential execution.

## Interaction with ATLAS

ATLAS provides the hypothesis search space.

Hivenance provides competition and prioritisation over that search space.

```text
ATLAS
  what could plausibly exist / compose / resemble
        |
        v
MARKET SENSORIUM
  what the world currently exposes
        |
        v
HIVENANCE
  what explanations/tests are worth considering
        |
        v
M2
  what actually happened
        |
        v
BEAST MEMORY
  what should influence the next cycle
```

Hivenance should be able to pull candidate products from the ATLAS derived registry, but an ATLAS candidate remains a hypothesis until separate execution and market evidence exist.

## Interaction with target ranking

A target score must not be a static arithmetic leaderboard. Hivenance should attach an explicit current hypothesis to material rank changes.

Example:

```text
TARGET: organisation X / HOMS / assessment buyer unit
previous_rank: 81
current_rank: 9

Hivenance hypothesis:
  Fresh assessment-coordinator vacancy + new programme announcement
  indicate rising assessment-workflow burden.

support:
  morphology_fit: high
  signal_recency: high
  buyer_role_confidence: medium-high
  public route: verified

challenge:
  no reply history
  no purchase evidence
  no direct demand evidence

recommendation:
  OBSERVE_MORE / PREPARE_PERMISSION_SAFE_TEST

authority_created: false
```

## Interaction with competitive intelligence

Competitive offer observations should create competing strategic hypotheses rather than deterministic prescriptions.

For example:

- `price_low`: commodity pricing appears dominant;
- `price_premium`: specialist/professional pricing appears viable as an advertised position;
- `pitch_gap`: evidence/provenance angle is rare;
- `channel_gap`: comparable providers underuse a channel;
- `saturation`: current pitch is crowded;
- `differentiate`: DIO should test a distinct proof-led angle;
- `hold`: observations are too noisy to justify a change.

Observed competitor prices remain asking prices only. Hivenance may reason over them, but cannot convert them into realised-price or profitability claims.

## Continual operation

The continual Market Sensorium cycle should explicitly include Hivenance:

```text
SENSE
NORMALISE
INTERPRET (LINGUA + ATLAS)
RESOLVE entities / habitats / offers
REMEMBER temporal state
GENERATE HYPOTHESES (Hivenance)
COMPETE + CHALLENGE (Phoenix pattern)
RANK targets / products / habitats / tests
RECOMMEND next bounded action
GATE authority
ACT OR HOLD
SETTLE (M2)
LEARN (BEAST)
REPEAT
```

## Acceptance direction

A future acceptance milestone should prove that Hivenance can:

1. generate multiple competing hypotheses from the same observation set;
2. preserve prior hypotheses and chronology;
3. revise rankings when the world-state changes;
4. distinguish silence, rejection, attention, engagement, acceptance and payment;
5. use ATLAS to propose cross-domain pivots without creating capability or authority;
6. incorporate competitor price/pitch/channel observations without claiming realised commercial success;
7. settle hypotheses against M2 outcomes;
8. reproduce the same recommendations from the same frozen observation set;
9. change recommendations predictably when a controlled new observation is introduced;
10. keep all consequential external effects separately authority-gated.
