# DIO Market Sensorium: Autonomic Discovery, Lead Memory and Competitive Offer Intelligence

Status: DESIGN CONTRACT / M4-adjacent commercial sensing roadmap

## Purpose

DIO now has enough domain and task-morphology knowledge to stop treating the market as a static list of manually supplied prospects.

The next system should continually answer five different questions without collapsing their truth classes:

1. What kinds of work and buyer problems exist?
2. Where do those buyers and problems become observable?
3. Which organisations, communities and buyer units are the strongest current targets?
4. What competing or adjacent offers are already in the market, at what apparent price/positioning/audience?
5. What happened after DIO acted or chose not to act, and how should that evidence change priority?

The loop is observational and adaptive. Learning may change attention, ranking, hypothesis and recommended next action. It must never create authority, consent, customer acceptance, payment truth or market demand merely from similarity or public signals.

## Constitutional laws

- Seed targets teach morphology; they do not remain permanent top targets.
- World signals discover candidates; outcomes reshape priority.
- Silence decays a context-specific hypothesis, never universal product truth.
- A public contact route is not permission to send commercial email.
- A public community is not permission to join, harvest members, post, message or automate a human account.
- Competitive listings are observations, not proof of competitor sales, profitability, quality or demand.
- Price displayed is an observed asking price, not a settled market-clearing price.
- Ad persistence is evidence of advertiser behaviour, not proof of profitable performance.
- News coverage is event evidence, not buyer intent unless separately corroborated.
- Similarity never implies equivalence; taxonomy/domain fit never implies capability.
- Learning may redirect attention, never mint authority.
- External publication, spend, send, join, DM, purchase and deployment remain authority-gated.
- Every external source observation must carry provenance, timestamp, access method, source terms state and freshness.

## Core circulation

```text
PUBLIC WORLD
  news / RSS / YouTube / company sites / tenders / grants / jobs
  Meta Ad Library / public pages / classifieds / directories
  Reddit / Discord discovery / professional communities / forums
        |
        v
MARKET SENSORIUM
  source-bound observations + source policy state
        |
        v
LINGUA
  market vocabulary + entities + problem phrases + offer language
        |
        v
ATLAS
  domain + morphology + work-pattern + primitive projection
        |
        v
TARGET / HABITAT / OFFER DISCOVERY
        |
        v
COMMERCIAL MEMORY
        |
        v
DYNAMIC RANKING
        |
        v
MICHAEL NEXT ACTION
        |
        +--> OBSERVE / RESEARCH
        +--> NEEDS_YOU
        +--> bounded permitted action
        |
        v
M2 SETTLEMENT + BEAST MEMORY
        |
        +------------------------------> next cycle
```

## 1. Seed exemplars per domain

Each material ATLAS domain should have a small curated bootstrap set, preferably about five high-quality examples for each of three categories:

- exemplar buyers / organisations;
- exemplar market habitats / communities;
- exemplar information sources.

Each exemplar must explain why it is useful. The system learns feature morphology rather than memorising names.

Example dimensions:

- domain fit;
- buyer-role fit;
- problem intensity;
- evidence/workflow burden;
- institutional scale;
- repeatability of the work;
- public observability;
- contactability;
- authority compatibility;
- DIO capability/morphology fit.

The proving test is that autonomously discovered targets eventually outrank weak seeds when evidence supports it.

## 2. Market Habitat

Add a universal semantic object: `Market Habitat`.

A Market Habitat is a recurring place where a domain's buyers, problems, offers, opportunities or transactions become observable.

Examples:

- organisation;
- Facebook Page;
- Facebook community/group;
- subreddit;
- Discord server;
- YouTube channel;
- newsletter;
- professional association;
- conference;
- procurement portal;
- funding portal;
- job board;
- classified-ad site;
- commercial directory;
- forum;
- news source;
- LinkedIn community;
- trade publication.

Suggested fields:

```text
habitat_id
platform
canonical_name
url_or_source_ref
domain_ids
morphology_scores
buyer_role_density
problem_signal_clusters
first_seen_at
last_observed_at
observation_count
signal_velocity
access_state
terms_state
operator_membership_state
posting_authority
dm_authority
current_rank
previous_rank
rank_delta
why_rank_changed
next_observation_due
recommended_action
```

Access states should include at least:

`PUBLIC_READ`, `LOGIN_REQUIRED`, `MEMBERSHIP_REQUIRED`, `INVITE_REQUIRED`, `API_PERMISSION_REQUIRED`, `TERMS_REVIEW_REQUIRED`, `OPERATOR_JOINED`, `BOT_INSTALL_REQUIRES_ADMIN`, `REFUSE_AUTOMATION`.

For groups/communities, discovery may result in `NEEDS_YOU: Join this community?`. DIO must not autonomously impersonate the operator, join as a human, harvest member lists, post, DM or bypass access controls.

## 3. Commercial target memory

A buyer target is not a row in a CSV. It is a temporal lineage.

Suggested target memory:

```text
target_id
organisation_id
buyer_unit
product_or_candidate_id
domain_ids
morphology_signature
first_seen_at
last_public_signal_at
first_ranked_at
current_rank
previous_rank
rank_delta
public_route_state
buyer_role_confidence
contact_route_confidence
last_contact_at
days_since_last_contact
reply_state
reply_type
consent_state
conversation_id
email_sent_count
meeting_count
proof_request_count
acceptance_count
payment_count
news_signal_count
youtube_signal_count
ad_signal_count
procurement_signal_count
job_signal_count
community_signal_count
problem_intensity
signal_recency
commercial_fit
capability_fit
authority_penalty
silence_decay
rejection_penalty
next_observation_due
next_recommended_action
why_rank_changed
```

### Silence

Silence must become time-aware evidence. It is not rejection and may not automatically trigger another message.

The engine may classify elapsed non-response into configurable states such as `WAITING`, `SILENCE_OBSERVED`, `WEAK_NEGATIVE_SIGNAL`, `CHANNEL_OFFER_DECAY`, `DORMANT`. Thresholds must be learned/configured per channel and domain rather than frozen as universal constants.

A once-off consent request that receives no reply should normally lower route/offer priority and redirect observation. It must not create authority for a follow-up message.

## 4. Dynamic target ranking

Ranking should operate over `organisation x buyer unit x problem x offer/product x channel/context`, not over organisation name alone.

Candidate features include:

- ATLAS domain fit;
- morphology fit;
- capability coverage;
- buyer-role confidence;
- problem-signal strength;
- signal recency and velocity;
- organisation fit/scale;
- route quality;
- community/habitat density;
- market momentum;
- prior engagement;
- commercial learning;
- competitive whitespace;
- price/offer fit;
- authority/terms/access penalties;
- stale-signal penalty;
- silence decay;
- explicit rejection penalty.

Weights may initially be governed heuristics. BEAST may later learn which features correlate with reply, consent, proof request, meeting, acceptance, payment and repeat purchase, while preserving causal and authority boundaries.

## 5. Continual public discovery

Current live sensing already includes YouTube public discovery plus RSS/news search. Extend this into a source-federated market Sensorium.

Priority source families:

- YouTube public metadata;
- news/RSS and publisher feeds where permitted;
- company newsrooms and public announcements;
- government tender/procurement portals;
- grant/funding notices;
- public job vacancies;
- annual reports and strategy documents;
- professional association news;
- conference programmes;
- Meta Ad Library;
- public business directories;
- public product/service listings;
- public classified ads where permitted;
- permitted public community surfaces;
- operator-authorised memberships/connectors.

A source adapter must state one of:

`OFFICIAL_API`, `PUBLIC_RSS`, `PUBLIC_SEARCH`, `PERMITTED_HTML_READ`, `OPERATOR_IMPORT`, `MANUAL_REVIEW`, `ACCESS_UNVERIFIED`, `TERMS_RESTRICTED`, `REFUSE`.

Prefer official APIs, public feeds and licensed/public search interfaces over HTML crawling.

## 6. Competitive Offer Intelligence

Add a distinct object: `Observed Market Offer`.

This records how similar work is currently being sold or advertised without treating an observed offer as validated demand.

Suggested fields:

```text
offer_observation_id
source_id
source_kind
observed_at
source_url_or_ref
seller_or_advertiser
seller_type
geography
domain_ids
morphology_signature
offer_category
buyer_problem
headline
pitch_angle
value_proposition
proof_claims
cta
price_value
price_currency
price_basis
price_type
audience_hints
delivery_mode
turnaround_claim
included_artifacts
excluded_artifacts
risk_or_guarantee_language
promotion_or_discount
ad_active_state
first_seen_at
last_seen_at
persistence_days
terms_state
provenance_digest
```

### Comparative analysis

DIO should compare offers by morphology, not merely keywords. For a target DIO product/candidate it should estimate:

- observed price range and median where enough comparable observations exist;
- fixed vs hourly vs per-unit vs subscription vs quote-only pricing;
- low/mid/premium positioning clusters;
- dominant pitch angles;
- common promises and proof devices;
- audience language and buyer role;
- scope included/excluded;
- turnaround expectations;
- guarantees/risk reversal;
- channel and creative style;
- geographic concentration;
- offer saturation;
- underserved morphology or evidence gap;
- apparent whitespace DIO may test.

Outputs must use language such as `observed asking prices`, `observed advertised offers`, `observed pitch prevalence`, and `candidate whitespace`. Never infer realised selling price, profitability, revenue or demand from listings alone.

## 7. Classifieds and local ad sites

Classified-ad sites can be useful for low/mid-market price discovery, wording, local audience segmentation and service packaging. They should be treated as noisy observational sources.

Possible signals:

- advertised service name;
- location;
- asking price;
- price basis;
- seller class;
- headline/pitch;
- service scope;
- buyer language;
- frequency of similar listings;
- listing age;
- reappearance/persistence;
- premium/promoted placement;
- adjacent categories.

A site must not be scraped merely because a page is publicly visible. Source terms and technical access rules are part of the evidence contract.

Current design note:

- News24 should not be directly crawled for this purpose without permission; use permitted search/RSS/manual-link observation instead.
- Locanto is potentially useful as a classifieds observation source, but automated access must remain `ACCESS_UNVERIFIED` until its applicable terms/robots/API/permission state is explicitly reviewed. Search-engine discovery or manual/operator import may be used as a bounded interim source where lawful and compliant.
- Meta Ad Library should be treated as a purpose-built public ad-intelligence surface subject to its current API/access requirements.
- Reddit requires a separate terms/approval assessment for commercial data use; do not treat public Reddit content as a free commercial training/scraping corpus.

## 8. News as trigger intelligence

News should generate buyer-event hypotheses rather than generic sentiment.

Examples:

```text
new grant or donor award             -> Evidex / GrantProof up
new assessment programme             -> HOMS up
university research initiative       -> Sophia up
new workforce expansion              -> VAMP up
regulatory change                    -> Assurance / RegOps up
contract award                       -> ContractProof / ProjectProof up
accreditation issue                  -> Accreditation / Evidence up
public audit finding                 -> Evidex / AuditProof up
```

A news event can move a target's rank because its context changed yesterday.

## 9. Job ads as problem sensors

Public job vacancies are high-value signals because organisations often describe the work they cannot currently absorb internally.

Examples:

- `Compliance Evidence Manager` -> evidence/compliance burden;
- `Assessment Coordinator` -> HOMS adjacency;
- `Research Integrity Officer` -> Sophia adjacency;
- `Grant Reporting Officer` -> Evidex/GrantProof adjacency;
- `Performance Management Specialist` -> VAMP adjacency.

A job signal is still not purchasing intent. It raises problem-presence confidence.

## 10. Community intelligence

For Facebook pages/groups, Reddit, Discord, forums and other communities, DIO should learn:

- domain relevance;
- buyer-role density;
- recurring pain clusters;
- vocabulary;
- recent activity/velocity;
- problem emergence/decay;
- product morphology fit;
- access state;
- whether operator action is needed to join/connect;
- whether a bot/app can be legitimately installed;
- what observation/posting/DM authority exists.

The system should be able to surface: `High-value community discovered; membership required; recommend operator join` without taking the joining action itself.

## 11. Query learning

ATLAS should generate discovery queries from:

`domain + morphology + work pattern + buyer problem + artifact + geography + observed vocabulary`.

LINGUA then learns terms from high-yield observations. Successful vocabulary becomes candidate query expansion. Failed/irrelevant vocabulary is down-ranked. Query changes must remain source-bound and inspectable.

## 12. Memory and rank-change receipts

Every material ranking change should be explainable.

Example:

```text
TARGET-RANK-RECEIPT
entity: unknown education network
previous_rank: 187
current_rank: 12
causes:
  + new assessment programme
  + recent assessment-coordinator vacancy
  + HOMS morphology fit 0.94
  + public institutional route discovered
  - no prior engagement evidence
observed_at: ...
authority_created: false
```

The Control Deck must expose `why rank changed`, not only the score.

## 13. Control Deck commercial cockpit

Replace the misleading single `Leads` view with a funnel that distinguishes:

- product opportunities;
- campaign hypotheses;
- buyer-unit targets;
- unique organisations;
- enrichment queue;
- public routes discovered;
- currently validated routes;
- outreach-eligible routes;
- contacted targets;
- mail intents;
- replies/engagement;
- qualified inbound leads;
- promoted opportunities;
- customer acceptance;
- verified payment/WTP;
- repeat commercial evidence.

Add separate media/market panels:

- creative families;
- rendered assets/reels;
- promoted video candidates;
- private upload verified;
- public release state;
- live sensor freshness;
- habitats discovered;
- habitat join requests;
- competitive offers observed;
- price observations by morphology;
- pitch-angle clusters;
- target rank movers;
- stale/silent targets;
- new trigger events.

## 14. Continual cycle

Recommended bounded cadence:

```text
SENSE
  refresh public permitted sources
NORMALISE
  source-bound observations
INTERPRET
  LINGUA + ATLAS morphology
RESOLVE
  organisation / buyer unit / habitat / offer
COMPARE
  competitors / pricing / pitch / whitespace
REMEMBER
  append temporal lineage
RANK
  recompute target + habitat + opportunity priority
RECOMMEND
  Michael next best permitted action
GATE
  Seraph / Legalis / authority
ACT OR HOLD
SETTLE
  M2 commercial truth
LEARN
  BEAST memory + query/rank adaptation
REPEAT
```

The continual loop should be capable of running read-only indefinitely. Any transition into join, post, send, spend, publish, DM, purchase or other consequential external effect must remain separately authorised.

## Acceptance direction

A future milestone should not pass because DIO found many pages. It should pass only if DIO demonstrates that:

- seed examples are no longer required to dominate rankings;
- newly discovered targets can rise based on fresh source-bound evidence;
- stale/silent contexts decay without being converted into universal rejection;
- price/pitch/audience comparisons remain observationally honest;
- habitat discovery can recommend operator joins without autonomously assuming identity;
- all ranking changes are temporally explainable;
- external authority remains unchanged;
- the continual cycle can rerun deterministically from the same observation set and update predictably when the world-state changes.
