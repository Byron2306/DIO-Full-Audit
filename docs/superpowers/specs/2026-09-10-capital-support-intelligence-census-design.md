# DIO Capital & Support Intelligence Census — Design

**Date:** 2026-09-10  
**Status:** ARCHITECTURE APPROVED; written spec awaiting user review  
**Parent capability:** Slice 3 Capital & Support Atlas  
**Base branch:** `agent/dio-control-deck-68-productgrade`

## 1. Purpose

DIO needs a global, evidence-bound capital and support discovery system with the same order of magnitude and operational discipline as the historical Prospect Intelligence registries. It must discover investors, grant funders, philanthropic donors, sponsors, patrons, accelerators, prizes and adjacent support mechanisms across domains without reducing the problem to a generic funding directory.

The system must use ATLAS as the semantic steering layer. ATLAS already provides a cross-domain model of economic activities, products and services, occupations, skills, education and research fields, technology, health, agriculture and government functions. Capital discovery therefore begins from DIO's governed capabilities and product evidence, not from a hard-coded industry list.

The central question is:

> Given what DIO can demonstrably do, where does that capability create value, which capital/support ecosystems are attached to those domains, which actors and live opportunities exist inside those ecosystems, and which smallest credible DIO product/proof wedge should lead the approach?

The system is intentionally asymmetric:

- intelligence may be broad and continuously refreshed;
- ranking may be aggressive and adaptive;
- drafting may be autonomous within truth constraints;
- contact, submission, legal representation, financial commitment and acceptance of capital remain human/Legalis-gated.

This preserves the historical DIO principle demonstrated by the large Prospect Intelligence waves: very wide intelligence with very narrow authority.

## 2. Scope and success criteria

### 2.1 In scope

The census covers the following capital/support classes as first-class typed families:

- `INVESTOR`
- `GRANT`
- `DONOR`
- `SPONSOR`
- `PATRONAGE`
- `ACCELERATOR`
- `PRIZE`

Each family may contain archetypes. Examples include:

- investor: VC fund, CVC, angel network, family office, impact investor, DFI, venture studio, strategic investor;
- grant: government programme, research council, multilateral programme, foundation call, challenge fund, innovation grant;
- donor: private foundation, charitable trust, public-benefit funder, institutional philanthropy, high-net-worth philanthropy where public evidence exists;
- sponsor: corporate CSR/ESG programme, ecosystem sponsor, strategic partnership fund, event/programme sponsor;
- patronage: GitHub Sponsors-style support, membership/community patronage, creator/research patronage, public-benefit sponsorship;
- accelerator: accelerator, incubator, founder programme, fellowship, venture builder, innovation hub;
- prize: innovation challenge, competition, award, open challenge, challenge prize.

### 2.2 Global from day one

Discovery is global from inception. Geography is a ranking weight and source-budget allocation factor, not a discovery wall.

Default geographic weighting:

1. South Africa
2. Africa
3. globally relevant opportunities

A strong global fit may outrank a weak local fit. Geography must never suppress a high-value, lawful, evidence-rich opportunity merely because it is not local.

### 2.3 Census scale

The target is at least the same order of magnitude as the historical Prospect Intelligence Wave 4 substrate, which contained thousands of organisations and thousands of organisation-product opportunity relationships.

The capital census is not considered mature if it consists only of a manually curated shortlist. It must support:

- thousands of capital/support organisations;
- many thousands of organisation-domain-product relationships;
- independently tracked live opportunities;
- independently tracked people/roles where publicly identifiable and relevant;
- current and historical source observations;
- verified public routes as a smaller quality layer;
- recurring freshness/reverification cycles;
- Atlas-generated adjacent discovery spaces.

The huge registry is the intelligence substrate. GoldenEye is the prioritisation mechanism that keeps the operator from drowning in it.

### 2.4 Success criteria

The first production-grade release must demonstrate:

1. a global source federation with policy-aware adapters;
2. ATLAS-generated domain and funding search plans;
3. ingestion of real public observations from multiple source families;
4. entity resolution across organisation, person and opportunity records;
5. a census materially larger than a hand-curated shortlist;
6. provenance, freshness and assertion-class tracking on every consequential claim;
7. type-specific funding/support scoring;
8. GoldenEye ranked capital/support priorities;
9. HiveNance competing hypotheses;
10. LINGUA hook/style pivots that preserve meaning and truth;
11. Market Command draft-only outreach bundles;
12. truthful Control Deck, GoldenEye and Market Command projections;
13. zero implicit send, submit, spend, contract, commitment or capital-acceptance authority.

## 3. Architecture

The approved system flow is:

```text
DIO governed capabilities / products / proof
                ↓
              ATLAS
 domain + work pattern + artifact + impact + maturity
                ↓
      capital/support archetype planner
                ↓
       CAPITAL SOURCE FEDERATION
                ↓
            SENSORIUM
 discover organisation / person / opportunity observations
                ↓
       entity resolution + evidence ledger
                ↓
              ATLAS
 exact fit + product wedge + proof bundle + adjacent domains
                ↓
            HIVENANCE
      competing funding/pitch hypotheses
                ↓
            GOLDENEYE
 evidence-weighted typed priority ranking
                ↓
              LINGUA
 hook / tone / framing / channel expression
                ↓
         MARKET COMMAND
       draft-only outreach package
                ↓
     NEEDS YOU / LEGALIS GATE
                ↓
   Slice 2 canonical customer/case spine
       only after real engagement
```

The recursive discovery loop is:

```text
find → classify → Atlas-map → expand adjacent search space → search again
     → hypothesise → rank → draft → observe response/absence → learn
```

ATLAS is not only a post-discovery scorer. It is both:

- a **search-space generator before discovery**, and
- a **strategic-fit mapper after discovery**.

This distinction is essential.

## 4. ATLAS role: domain-agnostic search steering

### 4.1 Inputs

ATLAS consumes DIO's canonical capability/product/proof truth and maps each candidate wedge onto:

- universal domain IDs;
- domain family and subdomain;
- work patterns;
- artifact classes;
- constraint classes;
- professional-authority requirements;
- safety criticality;
- product maturity;
- evidence/proof availability;
- impact themes;
- likely buyer/user/beneficiary groups;
- likely funding/support modes.

ATLAS may use its existing source federation and universal domain registry, but the capital subsystem must not mutate execution truth.

### 4.2 Capital search signature

For each DIO wedge, ATLAS emits a `CAPITAL_SEARCH_SIGNATURE`:

```text
signature_id
canonical_product_ids[]
canonical_proof_assets[]
domain_ids[]
domain_families[]
work_pattern_ids[]
artifact_classes[]
impact_themes[]
beneficiary_archetypes[]
organisation_archetypes[]
capital_types[]
capital_archetypes[]
geography_weights[]
maturity_stage
funding_use_cases[]
constraint_classes[]
professional_authority_required
query_families[]
source_class_preferences[]
truth_class = STRATEGIC_SEARCH_MODEL_OUTPUT
authority_created = false
```

This output means "ATLAS predicts this is a useful search space." It does not mean market demand exists.

### 4.3 Search expansion

ATLAS may generate adjacent search spaces from a validated fit. Examples:

- education/OER → teacher development → assessment → SDG4 → digital inclusion → curriculum transformation → foundation and CSR education programmes;
- governed AI → AI assurance → regtech → compliance → responsible AI → public-sector digital governance → enterprise risk;
- document conversion → accessibility → publishing → government communications → disability inclusion → education publishing;
- evidence automation → research integrity → clinical documentation → quality management → regulated manufacturing;
- open-source/public-benefit tooling → GitHub Sponsors → open-tech foundations → civic-tech sponsors → digital public goods ecosystems.

Expansion must be bounded by per-cycle budgets and preserve the origin signature so DIO can explain why the search expanded.

### 4.4 Pitch-surface selection

ATLAS also recommends which DIO surface should lead a pitch. This is a product/proof selection problem, not a branding problem.

Examples:

- platform/governance investor → DIO organism/product-factory/governance proof;
- education foundation → education/OER/learning/assessment proof;
- regulated-industry funder → Evidex/assurance/compliance proof;
- patron/open-source supporter → public build journey/open tooling/research outputs;
- accelerator → venture readiness, portfolio breadth and proof velocity.

Exact product IDs must always be resolved from the canonical 68-product registry at runtime or compile time. The census must not bake stale product names into permanent rules.

## 5. Capital Source Federation

### 5.1 Source registry

A new capital/support source federation extends, but does not replace, ATLAS's general source federation.

Each source adapter is represented by a `CAPITAL_SOURCE_ADAPTER` record:

```text
source_id
source_name
source_class
custodian
jurisdiction
coverage_geographies[]
coverage_domains[]
coverage_capital_types[]
entity_types[]
access_mode = PUBLIC_WEB | API | BULK_DATA | RSS | MANUAL_IMPORT | INTERNAL
status = READY | NEEDS_CREDENTIALS | SOURCE_UNAVAILABLE | POLICY_BLOCKED
machine_format
canonical_url
adapter_version
scheduled_enabled
on_demand_enabled
route_discovery_allowed
person_discovery_allowed
historical_awards_available
live_opportunities_available
rate_budget
freshness_ttl
reverification_ttl
terms_policy_note
last_success_at
last_error_at
last_error
truth_class = SOURCE_CAPABILITY_OBSERVATION
authority_created = false
```

### 5.2 Source strata

The federation must support at least the following source strata.

#### A. Canonical open funding datasets and APIs

Examples verified during design research include:

- Grants.gov public opportunity search/detail APIs;
- CORDIS Horizon project and participating-organisation open datasets;
- 360Giving / GrantNav downloadable open grant data;
- Crossref Open Funder Registry and funding metadata;
- USAspending award/grant data;
- ProPublica Nonprofit Explorer public API and filings.

Additional adapters may include equivalent authoritative national or multilateral datasets.

These sources are valuable for identity, historical-award evidence, funding archetypes, domain relationships and live opportunity discovery where provided.

#### B. Government and development-finance programmes

Examples include:

- national innovation and commercialisation programmes;
- development finance institutions;
- research councils;
- national industrial incentives;
- export/development programmes;
- multilateral funding programmes;
- regional development programmes.

South African examples should include the Technology Innovation Agency, dtic incentive/programme surfaces and IDC sector funding surfaces, subject to current public evidence.

#### C. Investor ecosystems

Adapters/search recipes must cover:

- venture capital funds;
- corporate venture capital;
- angel networks;
- family offices where publicly discoverable;
- impact investors;
- development finance institutions;
- strategic investors;
- venture studios;
- sector-specific investment firms;
- Africa and South Africa investor associations/directories and fund reports;
- public fund thesis, portfolio, team and announcement pages.

Commercial databases such as PitchBook/Crunchbase/Dealroom may be added only through lawful licensed access. Their absence must not make the census non-functional.

#### D. Philanthropy and donor ecosystems

Adapters/search recipes must cover:

- foundations;
- charitable trusts;
- research and education funders;
- public-benefit grantmakers;
- corporate foundations;
- multilateral philanthropy;
- issue-specific funds;
- climate/education/health/digital-inclusion/governance funders;
- historical grant-award datasets;
- current programme pages.

#### E. Sponsorship / CSR / ESG / strategic partnership

Adapters/search recipes must cover:

- CSR programmes;
- ESG/impact programmes;
- corporate foundations;
- innovation partnership pages;
- education/community sponsorship programmes;
- strategic ecosystem programmes;
- public partnership calls;
- programme/event sponsorship routes where relevant.

#### F. Accelerators, incubators, fellowships and prizes

Adapters/search recipes must cover:

- accelerators;
- incubators;
- venture builders;
- innovation hubs;
- fellowships;
- challenge funds;
- innovation competitions;
- prizes;
- founder programmes;
- university and research commercialisation programmes.

Hybrid programmes must be typed by their actual mechanisms rather than forced into a single label.

#### G. Patronage and community support

Adapters/search recipes must cover:

- GitHub Sponsors-style open-source sponsorship;
- Patreon-style membership/patronage;
- open-source foundations;
- civic/open-tech sponsorship;
- research/public-benefit patronage;
- public membership/support programmes;
- community-supported labs/projects.

Patronage is not investment. No equity or repayment implication may be inferred.

#### H. First-party organisation and programme sites

These are high-value evidence sources because they expose:

- investment thesis;
- grant guidelines;
- eligibility;
- exclusions;
- application dates;
- portfolio/award history;
- fund/team biographies;
- programme officer roles;
- public application/contact routes;
- new fund/programme launches;
- recent announcements.

#### I. News, events and ecosystem signals

Public signal sources may include:

- press releases;
- fund close announcements;
- new programme launches;
- funding announcements;
- conference/speaker lists;
- public ecosystem directories;
- newsletters/RSS;
- public professional/social surfaces where terms permit;
- public institutional news.

Signals may improve timing/freshness scores but must not override primary-source contradiction.

#### J. DIO internal evidence

The census may reuse:

- historical Prospect Intelligence registry evidence;
- Sensorium market observations;
- customer/case evidence;
- product maturity/proof receipts;
- BEAST market crystals;
- historical campaign outcomes;
- Atlas mappings.

Internal evidence must remain distinguishable from external-world observations.

### 5.3 Source budgets

Scheduled discovery uses bounded adaptive budgets, not exhaustive sweeps.

Each cycle allocates budget across source classes based on:

- Atlas search signatures;
- current opportunity density;
- source freshness;
- source success/error rate;
- geographic weighting;
- funding type coverage gaps;
- upcoming deadlines;
- recent rank movement;
- under-explored domains;
- operator priorities.

A source may never be hammered merely because it produced good results previously.

## 6. Data model

### 6.1 Separate identity classes

The census must never collapse these entities:

- `ORGANISATION`
- `PERSON`
- `OPPORTUNITY`

A foundation is an organisation. A programme officer is a person. A call for proposals is an opportunity. They may be linked but never represented as the same object.

### 6.2 Organisation record

Core fields:

```text
organisation_id
canonical_name
aliases[]
canonical_domain
country
regions[]
organisation_type
capital_archetypes[]
mission_or_thesis_observations[]
domain_signatures[]
portfolio_or_award_signatures[]
public_routes[]
source_identifiers[]
entity_resolution_state
first_observed_at
last_observed_at
freshness_state
do_not_contact
operator_notes
```

### 6.3 Person record

Only publicly identifiable professional-role information may be stored.

```text
person_id
name
organisation_id
public_role
public_profile_urls[]
public_contact_routes[]
role_relevance[]
source_observations[]
first_observed_at
last_observed_at
route_state
do_not_contact
```

No private or inferred personal contact data may be created.

### 6.4 Opportunity record

```text
opportunity_id
organisation_id
opportunity_type
opportunity_archetype
title
summary
status
open_date
deadline
rolling
jurisdiction
eligible_geographies[]
eligible_entity_types[]
sector_or_theme_requirements[]
stage_requirements[]
funding_range
funding_currency
funding_instrument
funding_use_restrictions[]
reporting_burden
application_route
public_contact_route
source_observations[]
atlas_search_signature_ids[]
first_observed_at
last_verified_at
freshness_state
```

### 6.5 Relationship records

The census supports many-to-many relationships:

```text
organisation ↔ domain
organisation ↔ capital_archetype
organisation ↔ historical_award
organisation ↔ person
organisation ↔ opportunity
opportunity ↔ domain
opportunity ↔ DIO product
opportunity ↔ DIO proof
opportunity ↔ hypothesis
opportunity ↔ draft
opportunity ↔ customer_case
```

The relationship layer is where the system can reach thousands of organisation-product-domain combinations without duplicating entities.

## 7. Evidence ledger and truth model

### 7.1 Assertion-level provenance

Every consequential assertion must preserve:

```text
assertion_id
subject_entity_id
predicate
value
assertion_class = OBSERVED | DERIVED | INFERRED | MODEL_OUTPUT
source_id
source_url_or_reference
source_record_id
observed_at
retrieved_at
valid_from
valid_to
freshness_state
confidence
conflict_group_id
supersedes_assertion_id
```

One generic confidence score is insufficient. Provenance and assertion class must remain visible.

### 7.2 Truth classes

Key truth classes include:

- `PUBLIC_SOURCE_OBSERVATION`
- `HISTORICAL_AWARD_OBSERVATION`
- `ENTITY_RESOLUTION_DERIVATION`
- `STRATEGIC_SEARCH_MODEL_OUTPUT`
- `STRATEGIC_FIT_MODEL_OUTPUT`
- `HYPOTHESIS_MODEL_OUTPUT`
- `RANKED_PRIORITY_MODEL_OUTPUT`
- `DRAFT_RECOMMENDATION`
- `OPERATOR_APPROVED_ACTION`
- `EXTERNAL_RESPONSE_OBSERVED`
- `SETTLED_FINANCIAL_EVIDENCE`

The following must never be inferred from ranking or fit:

- market demand;
- willingness to fund;
- grant eligibility certainty;
- donor intent;
- investment commitment;
- customer intent;
- secured funding;
- revenue.

### 7.3 Conflicts

Conflicting observations are preserved, not silently overwritten.

A canonical current fact may be selected only when source/freshness rules allow it. Otherwise the entity carries an explicit conflict state and GoldenEye may reduce confidence/priority accordingly.

## 8. Entity resolution

### 8.1 Organisation resolution

Preferred keys:

1. stable source identifier;
2. official domain;
3. registry identifier where public;
4. normalized canonical name + jurisdiction;
5. verified parent/subsidiary relationship.

Fuzzy name matching alone may propose a merge but may not finalize one.

### 8.2 Person resolution

Person identity must use public role context and organisation linkage. Name-only matching is insufficient.

### 8.3 Opportunity resolution

Prefer source-native opportunity/call IDs. When none exist, use organisation + canonical URL + title + open/deadline window.

### 8.4 Aliases and lineage

All merged aliases and source IDs remain queryable. Resolution receipts must explain why two records were linked.

## 9. Discovery engine

### 9.1 Search plan

Before each cycle, ATLAS produces a `CAPITAL_DISCOVERY_PLAN` containing:

```text
cycle_id
search_signature_ids[]
query_families[]
source_allocations[]
capital_type_targets[]
geography_weights[]
domain_coverage_targets[]
novelty_budget
reverification_budget
live_opportunity_budget
historical_award_budget
route_enrichment_budget
person_role_budget
```

### 9.2 Query families

A single signature may generate multiple query families:

- funder thesis queries;
- current call/opportunity queries;
- historical award queries;
- portfolio similarity queries;
- programme/eligibility queries;
- organisation discovery queries;
- public route queries;
- role/person discovery queries;
- recent signal queries;
- adjacent-domain queries.

### 9.3 Scheduled cycles

Recommended default cadence:

- daily bounded discovery cycle;
- higher-frequency deadline/timing watch only where necessary;
- weekly broad census-expansion cycle;
- monthly deep stale-record reverification;
- on-demand operator/Vesper searches at any time.

The exact schedule belongs in deployment configuration, not hard-coded business logic.

### 9.4 Adaptive exploration vs exploitation

Discovery budget is split between:

- exploitation: search known high-fit domains/sources;
- exploration: test adjacent Atlas spaces and under-represented source classes.

The system must never converge so aggressively that it stops discovering new funding archetypes or domains.

## 10. Type-specific scoring

There is no single generic "money fit" score.

### 10.1 Investor

Recommended base dimensions:

- thesis fit 25%
- proof fit 20%
- capital-use fit 20%
- stage fit 15%
- cheque-size fit 10%
- geography fit 10%

Timing dimensions:

- general timing 35%
- recent signal 30%
- fund deployment state 20%
- route freshness 15%

`APPROACH_NOW` requires at minimum:

- fit >= 70;
- timing >= 75;
- usable public route;
- no do-not-contact block;
- no policy/Legalis block.

### 10.2 Grant

Dimensions include:

- eligibility;
- thematic fit;
- geographic fit;
- maturity/stage fit;
- funding-use fit;
- deadline urgency;
- reporting burden;
- evidence readiness.

### 10.3 Donor/philanthropy

Dimensions include:

- mission resonance;
- public-benefit fit;
- beneficiary fit;
- credible impact evidence;
- governance/trust fit;
- stewardship fit;
- route quality;
- timing.

### 10.4 Sponsorship

Dimensions include:

- strategic alignment;
- audience/ecosystem overlap;
- measurable activation value;
- brand/reputation safety;
- programme fit;
- geographic fit;
- route quality.

### 10.5 Patronage

Dimensions include:

- public value;
- community resonance;
- repeatability;
- supporter benefit;
- open-source/public-build relevance;
- platform fit;
- authenticity/trust evidence.

Patronage must not be scored as equity investment.

### 10.6 Accelerator and prize

These use separate eligibility, stage, sector/theme, geography, deadline, network/non-cash value, burden and evidence-readiness models.

### 10.7 GoldenEye output

GoldenEye exposes:

```text
rank
target/opportunity
capital_type
capital_archetype
priority_score
fit_score
timing_score
route_quality
freshness
leading_hypothesis
atlas_product_wedge
atlas_proof_bundle
lingua_approach
draft_state
next_action = DRAFT_READY | NEEDS_RESEARCH | HOLD | DO_NOT_CONTACT
rank_movement
movement_explanation
truth_class = RANKED_PRIORITY_MODEL_OUTPUT
```

## 11. HiveNance hypothesis layer

HiveNance creates competing explanations for why a target/opportunity may fit.

Examples:

- governed-AI infrastructure investment thesis;
- education/OER impact-funder thesis;
- African AI ecosystem sponsorship thesis;
- regulatory/compliance innovation thesis;
- public-benefit open-tool patronage thesis;
- accelerator venture-readiness thesis.

Hypothesis status remains bounded:

- `TEST`
- `REFINE`
- `HOLD`
- `PROMOTE`

Promotion requires evidence. It does not create authority.

The system should learn separately from:

- no response;
- rejection;
- clarification request;
- positive reply;
- meeting invitation;
- application invitation;
- application submission;
- award/term-sheet evidence;
- settlement.

Silence is evidence about a hypothesis/channel only within its context; it is not universal market rejection.

## 12. LINGUA role

LINGUA owns expression, not strategic truth.

The fixed rule is:

> same meaning, different lawful skin

Mutable fields include:

- hook style;
- tone;
- pacing;
- story arc;
- CTA expression;
- channel phrasing;
- audience archetype language.

Default approach families may include:

- investor → thesis-first;
- grant → mandate-first;
- donor → mission-first;
- sponsor → activation-first;
- patronage → community-first;
- accelerator → programme-fit-first;
- prize → eligibility/proof-first.

Alternative approaches may include:

- proof-first;
- wedge-first;
- problem-first;
- impact-first;
- founder/build-journey-first where appropriate.

LINGUA may test which expression performs better after real response evidence accumulates, but it may never mutate safe claims, evidence state or authority state.

## 13. Market Command draft layer

For a ranked opportunity, Market Command may produce a `CAPITAL_OUTREACH_BUNDLE` containing:

```text
opportunity_id
organisation_id
person_id optional
capital_type
capital_archetype
selected_hypothesis
atlas_product_wedge[]
atlas_proof_bundle[]
lingua_projection
recommended_channel
draft_subject
draft_opening
draft_body
safe_claims[]
claims_to_avoid[]
missing_research[]
missing_proofs[]
required_approvals[]
truth_class = DRAFT_RECOMMENDATION
send_authority = false
authority_created = false
external_effects = false
```

A draft may exist even when contact is not permitted. In that case the UI must show the block explicitly and prevent draft-to-send progression.

## 14. Public routes and contact boundaries

### 14.1 Route states

```text
PUBLIC_ROUTE_VERIFIED
APPLICATION_ROUTE_VERIFIED
PARTNERSHIP_ROUTE_VERIFIED
PUBLIC_PERSON_ROLE_VERIFIED
NO_PUBLIC_ROUTE
STALE_ROUTE
POLICY_BLOCKED
NEEDS_REVIEW
```

### 14.2 Route rules

Allowed route evidence may include:

- public programme application URL;
- public grants portal;
- public organisation contact form;
- public organisation email;
- public professional contact/profile route where permitted;
- public partnership/inquiry route.

Forbidden behaviour includes:

- inventing `firstname.lastname@company.com` addresses;
- scraping hidden/private contact information;
- treating an unverified inferred route as contactable;
- bypassing platform terms or access controls.

`DO_NOT_CONTACT` is sticky and operator-controlled. It blocks progression to send even if later sources expose a route.

## 15. Legalis and authority

The census itself creates no external authority.

Autonomous/bounded actions allowed:

- public discovery;
- ingestion;
- source classification;
- entity resolution proposals;
- Atlas mapping;
- ranking;
- hypothesis generation;
- draft generation;
- freshness checks;
- scheduled research cycles.

Human/Legalis-gated actions:

- external message send;
- submission/application;
- publication of consequential claims;
- spending;
- paid subscription purchase;
- acceptance of investment/grant/donation terms;
- term negotiation;
- legal/entity representations;
- banking/payment action;
- signature/contract action.

An opportunity becoming `DRAFT_READY` never implies send authority.

## 16. Slice 2 handoff

Capital/support discovery does not create a parallel CRM.

Before real engagement, records live in the Capital & Support census.

A canonical Slice 2 customer/case record may be created only when evidence of actual engagement exists, for example:

- external response observed;
- application process entered with operator approval;
- meeting scheduled;
- partnership conversation opened;
- sponsor inquiry accepted;
- other configured engagement event.

The bridge preserves:

- original opportunity ID;
- organisation/person IDs;
- source evidence;
- Atlas fit;
- selected hypothesis;
- outreach lineage;
- response evidence.

`DISCOVERED`, `RANKED`, and `DRAFT_READY` alone must never create customer cases.

## 17. Operator surfaces

### 17.1 Control Deck

The Capital & Support panel should evolve from the current zero-state view into a census cockpit showing:

- total organisations;
- total live opportunities;
- total historical award relationships;
- counts by capital type;
- geography distribution;
- Atlas domain distribution;
- high-fit count;
- draft-ready count;
- deadlines soon;
- stale/reverification queue;
- route-verification queue;
- engaged cases;
- source health;
- discovery-cycle health;
- top ranked opportunities.

### 17.2 GoldenEye

GoldenEye remains the primary priority surface:

- ranked target/opportunity field;
- type filters;
- domain filters;
- geography filters;
- source/freshness filters;
- rank movement;
- movement explanation;
- fit/timing/route/evidence components;
- Atlas wedge;
- HiveNance leading hypothesis;
- LINGUA approach;
- next action.

### 17.3 Market Command

Market Command shows:

- ranked opportunity list;
- current draft;
- alternate LINGUA hooks;
- selected hypothesis;
- product/proof wedge;
- safe claims;
- claims to avoid;
- missing research;
- route state;
- approval state;
- explicit `send_authority=false` until governed action.

### 17.4 Atlas

Atlas should expose for each opportunity:

- matched domains;
- domain path;
- product mapping;
- proof mapping;
- capital archetype mapping;
- fit explanation;
- adjacent search suggestions;
- search-signature lineage.

This ensures Atlas is visibly part of the organism rather than a hidden scoring helper.

### 17.5 Vesper

Vesper may answer questions such as:

- "Who should I approach for DIO?"
- "Find grants relevant to education/OER."
- "Which African investors are the best fit and why?"
- "Show me donor opportunities around digital inclusion."
- "Draft a message for this foundation but do not send it."
- "What patronage propositions make sense for open DIO builds?"
- "Why did GoldenEye move this fund from rank 12 to rank 3?"

Vesper inherits the same authority wall.

## 18. Storage and registry lineage

The census should use versioned, append-aware registry storage with explicit import/run receipts.

Recommended state families:

```text
state/market_capital/
  organisations/
  people/
  opportunities/
  observations/
  assertions/
  relationships/
  fits/
  hypotheses/
  rankings/
  drafts/
  routes/
  source_health/
  search_plans/
  discovery_cycles/
  receipts/
```

For large census snapshots, a SQLite-backed registry is recommended with exportable CSV/JSON census artifacts, mirroring the historical Prospect Intelligence pattern. JSON files may continue to serve as durable receipts and UI projections.

Each census generation carries:

- census version;
- generated timestamp;
- source-adapter versions;
- record counts;
- source coverage counts;
- hashes where appropriate;
- previous census lineage;
- explicit authority state.

Historical census versions are preserved for rank/change analysis.

## 19. Failure modes and truthful degradation

The system must degrade visibly.

Examples:

- API unavailable → `SOURCE_UNAVAILABLE`;
- credentials absent → `NEEDS_CREDENTIALS`;
- source terms block automation → `POLICY_BLOCKED`;
- stale route → `STALE_ROUTE`;
- failed entity merge → keep separate records / `NEEDS_REVIEW`;
- source disagreement → preserve conflict;
- Atlas lacks confidence → `NEEDS_RESEARCH`;
- no public route → discovery/ranking allowed, send path blocked;
- no opportunities → truthful empty cockpit;
- a commercial data provider is unavailable → other source classes continue.

The system must never replace a failed source with fabricated data.

## 20. Research findings informing the source design

The architecture is grounded in currently available public/open sources rather than assuming a single proprietary provider.

Design research verified:

- Grants.gov exposes public opportunity-search/detail API functionality;
- CORDIS provides searchable projects plus downloadable Horizon Europe/Horizon 2020 participating-organisation data;
- 360Giving GrantNav offers downloadable open grant data updated from its datastore;
- Crossref Open Funder Registry provides open funder identities and funder metadata through downloadable files/API pathways;
- USAspending provides public API access to US government award and grant data;
- ProPublica Nonprofit Explorer provides public nonprofit search/filing API access;
- South African public funding ecosystems include technology innovation, industrial incentive and development-finance surfaces that can be modeled as first-party source adapters;
- African investment research demonstrates that the investor universe spans multiple archetypes rather than one generic VC category;
- GitHub Sponsors demonstrates a materially different public patronage/support mechanism that should not be conflated with investment capital.

The design intentionally avoids dependence on commercial databases. Licensed sources may enrich the census later but are not the foundation of viability.

## 21. Implementation decomposition

This design is too broad to implement safely as one undifferentiated coding task. The implementation plan should decompose it into ordered workstreams while preserving one integrated acceptance path.

Recommended workstreams:

1. **Census schema + SQLite registry + lineage**
2. **Capital source federation and adapter registry**
3. **ATLAS capital search signature compiler**
4. **Initial authoritative/open adapters**
5. **Investor/philanthropy/accelerator/patronage web adapters**
6. **Entity resolution and evidence ledger**
7. **Scheduled adaptive discovery planner**
8. **Atlas recursive expansion loop**
9. **HiveNance/GoldenEye/LINGUA/Market Command integration hardening**
10. **Control Deck / Atlas / GoldenEye / Market Command census UI expansion**
11. **Vesper read/draft query surface**
12. **large-scale census build, validation and live deployment**

Each workstream must use TDD and preserve Slice 1, Slice 2 and current Slice 3 regression coverage.

## 22. Acceptance gates

The complete census release must not be stamped merely because APIs return 200.

Required gates include:

### Registry gates

- census contains real public records from multiple source classes;
- counts and lineage are reproducible;
- source adapter health is visible;
- duplicate/entity-resolution rate is measured;
- all seven capital types are supported even if a given cycle has zero live opportunities for one type.

### ATLAS gates

- at least several materially different DIO products generate different domain/search signatures;
- search signatures produce different source/query allocations;
- adjacent search expansion is bounded and explainable;
- output remains `STRATEGIC_SEARCH_MODEL_OUTPUT` / `STRATEGIC_FIT_MODEL_OUTPUT`, never demand.

### Evidence gates

- consequential assertions carry source/provenance/freshness;
- conflicts are preserved;
- no invented email/contact route exists;
- stale routes degrade correctly.

### GoldenEye gates

- type-specific rankings differ meaningfully;
- rank movement explanations are reproducible;
- no rank implies funding intent;
- `DO_NOT_CONTACT` blocks progression.

### LINGUA/Market gates

- hook/style pivots preserve safe claims;
- draft bundles expose proof and prohibited claims;
- send authority remains false without explicit governed action.

### Scale gate

A production census must be demonstrably larger than a hand-curated shortlist and must prove that DIO can federate across domains. The target is thousands of organisations/relationships over time, not dozens.

### Live gate

After merge and deployment:

- services active;
- discovery cycle consumes real source observations;
- census counts non-zero;
- Atlas mappings visible;
- GoldenEye populated;
- Market Command drafts inspectable;
- Control Deck census metrics visible;
- authority states remain false;
- no external contacts, submissions or financial actions occur during verification.

## 23. Final design principles

1. **ATLAS decides where to look; Sensorium does the looking.**
2. **The census is global; geography is a weight, not a wall.**
3. **The registry should be huge; the operator shortlist should be small.**
4. **Organisation, person and opportunity are separate identities.**
5. **Historical funding is evidence about fit, not proof of future intent.**
6. **Investor, grant, donor, sponsor, patronage, accelerator and prize are different economic relationships.**
7. **Provenance is first-class; confidence alone is insufficient.**
8. **No source failure may be hidden by synthetic/fallback prospects.**
9. **LINGUA changes expression, never truth.**
10. **Ranking creates priority, never permission.**
11. **The system may research aggressively and act conservatively.**
12. **Real engagement enters the canonical Slice 2 case spine; no parallel CRM is created.**
13. **The historical Prospect Intelligence standard remains the benchmark: very wide intelligence, very narrow authority.**
