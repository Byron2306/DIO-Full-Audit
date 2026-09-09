# DIO Slice 3 Capital & Support Atlas Design

## Goal

Build a governed Capital & Support Market Class that allows DIO to proactively discover, classify, map, rank, and prepare outreach for multiple funding/support mechanisms without collapsing them into one generic lead model.

Slice 3 extends the verified Slice 1 cockpit and Slice 2 commercial spine. It does not grant autonomous outreach, investment authority, donation acceptance authority, grant-submission authority, or financial commitment authority.

## Core idea

DIO should learn to map the outside world onto itself.

The shared loop is:

`public discovery surfaces -> Sensorium -> typed Capital & Support Registry -> Atlas strategic fit -> HiveNance rival hypotheses -> GoldenEye prioritisation -> Market Command draft campaign/outreach -> Needs You / Legalis -> Slice 2 case spine after real engagement`

The recursive research loop is:

`find -> classify -> Atlas-map -> generate adjacent search space -> Sensorium search -> hypothesise -> rank -> recommend`

This loop may run proactively on scheduled Sensorium cycles, but it has no contact authority.

## Opportunity classes

The registry must distinguish at least these types:

- `INVESTOR`
- `GRANT`
- `DONOR`
- `SPONSOR`
- `PATRONAGE`
- `ACCELERATOR`
- `PRIZE`

These types share provenance, identity resolution, source freshness, route quality, Atlas mapping, hypothesis, ranking, and outreach-draft interfaces, but they do not share one scoring model.

### Investor

Primary questions: thesis fit, stage fit, geography, cheque size, capital-use fit, proof quality, recent activity, route quality, timing.

### Grant

Primary questions: eligibility, thematic fit, geographic eligibility, deadline, funding purpose, allowable costs, reporting burden, co-funding requirements, evidence requirements.

### Donor / foundation

Primary questions: mission fit, public-benefit fit, impact model, stewardship requirements, evidence credibility, beneficiary alignment, geography, programme fit.

### Sponsor

Primary questions: strategic alignment, audience overlap, visibility or ecosystem value, sponsorship format, brand-safety fit, activation requirements.

### Patronage

Primary questions: repeatable public value, creator/build journey, education/open-resource value, community fit, membership proposition, supporter benefits, platform fit.

Patronage is support revenue, not equity investment and not ordinary product sales.

### Accelerator / prize

Primary questions: programme eligibility, stage, geography, sector focus, application deadline, programme burden, funding/non-dilutive value, strategic network value.

## Entity model

DIO must not confuse a person with an organisation or an opportunity.

Core records:

### Person

- `person_id`
- name
- role/title
- organisation linkage
- public professional/profile URLs
- geography
- publicly available contact route(s)
- route freshness
- source provenance
- confidence

### Organisation

- `organisation_id`
- name
- organisation type
- domains/sectors
- geography
- website/profile URLs
- funding/support mechanisms
- source provenance
- confidence

### Opportunity

- `opportunity_id`
- opportunity type
- organisation linkage
- optional person/decision-maker linkage
- title/programme/fund name
- deadline or timing window
- stated criteria
- amount/cheque/band if publicly stated
- geography
- source URLs
- source freshness
- route quality
- truth class

All records preserve provenance. Discovery evidence never becomes demand evidence merely because it was found.

## Discovery surfaces

Sensorium should federate as many lawful public surfaces as practical, using typed source adapters and provenance receipts rather than one opaque search feed.

Priority classes include:

- public web search and organisation websites
- investor/fund portfolio and team pages
- foundation and donor programme pages
- grant programme and call-for-proposal pages
- accelerator and competition sites
- public professional profiles and directories where access is lawful
- university/research innovation and funding portals
- government and development-agency funding pages
- corporate sponsorship/CSR/ESG programme pages
- startup ecosystem and venture databases that are lawfully accessible
- public creator/patronage platform pages and ecosystem discovery
- newsletters, press releases, public announcements, recent investment/grant news
- DIO's existing source federation and market discovery inputs

Each source adapter must declare:

- source type
- permitted discovery mode
- fields extracted
- last-seen timestamp
- URL/provenance
- confidence
- whether a direct route was actually observed or merely inferred

No adapter may fabricate an email address, private contact route, investor mandate, donor intent, willingness to fund, or relationship.

## Atlas role

Atlas is the strategic cartographer between discovery and hypothesis generation.

Atlas evaluates:

- domain -> product fit
- domain -> proof fit
- target type -> proposition fit
- domain -> funding mechanism fit
- opportunity -> product bundle
- opportunity -> proof bundle
- opportunity -> pitch family
- opportunity -> adjacent search expansion

Atlas outputs `STRATEGIC_FIT_MODEL_OUTPUT`, never `MARKET_DEMAND`.

Example projection:

```yaml
schema: dio.atlas.capital_support_fit.v1
target_type: DONOR
domain: EDUCATION
primary_products:
  - HOMS Learning Studio
  - HOMS Curriculum
  - Sophia Tutor
secondary_products:
  - ImpactProof
  - GrantProof
funding_modes:
  - GRANT
  - DONOR
  - SPONSOR
proof_bundle:
  - Prosper
  - GREAT
  - OER outputs
recommended_pitch_family: EDUCATION_PUBLIC_GOOD
truth_class: STRATEGIC_FIT_MODEL_OUTPUT
authority_created: false
```

Atlas should be able to recommend that DIO lead with a narrow product/proof wedge instead of pitching the entire 68-product organism.

## Recursive search expansion

Atlas may propose adjacent search domains and institution archetypes from a discovered opportunity.

Example:

1. Sensorium finds an African education foundation.
2. Atlas maps it to education, OER, teacher development, digital learning, SDG4, and relevant DIO products/proofs.
3. Atlas emits adjacent search prompts/archetypes.
4. Sensorium discovers more education foundations, SDG4 programmes, edtech philanthropy, teacher-development donors, corporate education sponsors, African innovation funds, and related patrons.
5. New candidates enter the registry with provenance and confidence.

Search expansion does not create outreach authority.

## HiveNance role

HiveNance maintains competing hypotheses explaining why a specific target/opportunity may care and which proposition should be tested.

Examples:

- `GOVERNED_AI_INFRASTRUCTURE`
- `PRODUCT_FACTORY_VENTURE_OS`
- `VERTICAL_SAAS_PORTFOLIO`
- `EVIDENCE_FIRST_TRUST_REGTECH`
- `EDUCATION_OER_PUBLIC_GOOD`
- `EMERGING_MARKET_AI_INFRASTRUCTURE`
- `AFRICAN_EDTECH_IMPACT`
- `OPEN_RESEARCH_AND_PUBLIC_RESOURCE`
- `CREATOR_BUILD_JOURNEY`

Hypothesis status remains bounded, e.g. `TEST`, `REFINE`, `HOLD`, `PROMOTE`, with promotion requiring evidence from real outcomes. HiveNance cannot turn model fit into willingness-to-fund truth.

## GoldenEye role

GoldenEye provides a unified Capital & Support priority field while preserving type-specific scores.

Suggested fields:

- target / opportunity
- opportunity type
- organisation
- decision-maker, if lawfully/publicly resolved
- Atlas strategic-fit score
- type-specific fit score
- timing score
- route quality
- evidence freshness
- current leading hypothesis
- proof-bundle readiness
- next recommended action
- `DRAFT_READY | NEEDS_RESEARCH | HOLD | DO_NOT_CONTACT`
- truth class
- authority-created flag

GoldenEye should show rank movement and why rank moved. A model rank is priority guidance, not proof that the opportunity is best or fundable.

## Market Command role

Market Command converts ranked opportunities into governed campaign recommendations.

For each candidate it may prepare:

- campaign objective
- recommended channel
- draft subject / opening
- tailored draft outreach
- concise pitch angle
- recommended product wedge
- recommended proof bundle
- safe-claim set
- explicit unsupported claims to avoid
- attachments/assets to prepare
- missing research
- operator / Legalis approval state

Market Command may create draft outreach. It may not send automatically in Slice 3.

## Vesper role

Vesper gains read/draft awareness but not new authority.

Representative operator questions:

- "Who should I approach this week?"
- "Find grant opportunities for DIO's education/OER work."
- "Why is this investor ranked above that foundation?"
- "Draft the investor email but do not send it."
- "What proof should I show this donor?"
- "What could we offer Patreon-style supporters?"

Vesper must explain the underlying DIO truth classes and distinguish discovery, strategic fit, hypothesis, draft recommendation, approval, send state, and real response.

## Patreon / patronage lane

Slice 3 should model patronage without assuming Patreon is the only platform.

Potential proposition families include:

- support open educational tools
- support evidence-first/governed AI research
- support the public DIO build journey
- early-access supporter tier
- research/demo supporter
- community lab patron
- sponsor a specific open release or learning resource

The system may research platforms, patron audiences, benefit structures, comparable creator/community models, and draft tier hypotheses. Actual account creation, pricing publication, reward commitments, or external posting remain operator-authorised actions and may depend on later channel/runtime slices.

## Relationship with Slice 2

Discovery candidates do not automatically become customer cases.

A Capital & Support record enters the Slice 2 canonical case spine only after a real engagement begins, for example:

- operator-approved outreach is sent later under an authorised channel
- inbound reply is received
- application/submission enters an active governed workflow
- meeting or diligence process begins

The same canonical-case rules apply: no parallel investor CRM, donor CRM, or grant CRM.

## Legalis and authority boundaries

Legalis remains a prerequisite gate for consequential external actions.

Slice 3 creates no authority to:

- send outreach automatically
- claim investment interest
- claim donor intent
- submit grant applications
- accept grant/donation/investment terms
- issue securities
- create financial commitments
- promise patron benefits not yet approved/configured
- scrape or access private/non-lawful data sources

The scheduled discovery loop is permitted only for lawful public research. All consequential actions remain `NEEDS_YOU` or explicitly refused until their requirements are satisfied.

## Truth classes

At minimum, preserve separate truth states for:

- `PUBLIC_SOURCE_OBSERVATION`
- `IDENTITY_RESOLUTION_CANDIDATE`
- `STRATEGIC_FIT_MODEL_OUTPUT`
- `HYPOTHESIS`
- `RANKED_PRIORITY_MODEL_OUTPUT`
- `DRAFT_RECOMMENDATION`
- `OPERATOR_APPROVED`
- `OUTREACH_SENT`
- `RESPONSE_OBSERVED`
- `APPLICATION_SUBMITTED`
- `TERM_SHEET_OR_AWARD_EVIDENCE`
- `SETTLED_FUNDS_EVIDENCE`

A term sheet, award notice, pledge, or platform signal must not be represented as settled funds unless settlement evidence exists.

## Scheduled discovery

Sensorium may run recurring capital/support discovery cycles with no-contact authority.

A cycle should:

1. refresh existing candidates and source freshness
2. search for new typed opportunities
3. resolve organisations and publicly identifiable decision-makers where possible
4. deduplicate entities/opportunities
5. run Atlas strategic mapping
6. accept Atlas adjacent-search suggestions within bounded budgets
7. run HiveNance hypothesis updates
8. refresh GoldenEye ranking
9. create or update draft-ready recommendations
10. create Needs You items only when a meaningful operator decision is available

It must not create notification spam for low-quality discoveries.

## UI / cockpit projections

### GoldenEye

Add Capital & Support priority tables, rank movement, source freshness, fit decomposition, and draft readiness.

### Market Command

Add typed campaign lanes and draft-outreach bundles.

### Atlas

Expose target -> domain -> product -> proof -> funding-mode fit and adjacent search suggestions.

### Control Deck

Add an operator summary such as:

- opportunities discovered
- high-fit opportunities
- draft-ready opportunities
- Needs You
- investor / grant / donor / sponsor / patronage / accelerator / prize counts
- active engaged cases from Slice 2

No cockpit should imply money raised until settlement evidence exists.

## Acceptance criteria

Slice 3 is complete when tests and live smoke prove that:

1. all seven opportunity types are distinct and validated
2. Sensorium can ingest/federate public-source candidates with provenance
3. person, organisation, and opportunity identities remain separate
4. Atlas maps opportunities to products, proofs, funding modes, and pitch families
5. Atlas produces bounded adjacent search expansion
6. HiveNance generates competing type-aware hypotheses without mutating truth
7. GoldenEye ranks typed opportunities with evidence/timing/route decomposition
8. Market Command produces tailored draft outreach bundles without send authority
9. Vesper can explain and draft from the same state without inventing actions
10. Slice 2 case creation occurs only after real engagement
11. no long-lived credentials or contact authority leak to browser surfaces
12. no discovery/ranking result is labelled as demand, commitment, or settled funding
13. Slice 1 and Slice 2 regression suites remain green

## Deferred from Slice 3

- autonomous outbound sending
- full external channel credential restoration
- Production Studio render-runtime restoration
- Patreon/account creation and public tier publication
- investor deal execution or securities/legal workflows
- automatic grant submission
- automatic donation acceptance
- canonical portfolio-wide pricing mutation

These remain later-slice or explicit operator/professional actions.
