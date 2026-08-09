# DIO Commercial Operating Plan

Status: approved planning baseline  
Planning horizon: first 90 days  
Primary objective: prove repeatable, profitable, evidence-bearing sales loops for Evidex and HOMS before broad product expansion.

## 1. Executive Decision

DIO will operate as the internal orchestration and intelligence layer. It will not initially replace the customer-facing product brands.

```text
KnowEdge / DIO
  -> HOMS: assessment and marking relief
  -> Evidex: evidence-pack relief
  -> VAMP: performance-evidence relief
  -> Sophia: academic-review relief
  -> Outlook Inbox Desk: controlled customer operations
```

Customers buy a specific outcome. DIO coordinates demand sensing, compliant acquisition, orders, money, fulfilment, delivery and learning behind those outcomes.

The operating loop is:

```text
observe market demand
-> form a product/audience/message/channel hypothesis
-> create a proof-led campaign through NicheFoundry
-> distribute one controlled experiment
-> capture attribution and enquiries
-> qualify through Outlook Triage
-> create an order
-> verify payment or approved commercial terms
-> release product fulfilment
-> require human review
-> deliver
-> issue a commercial receipt
-> evaluate economics
-> promote, revise or kill the experiment
```

## 2. Scope And Priorities

### Immediate commercial priorities

1. **Evidex paid pilot:** strongest complete transaction proof and clearest small-business evidence pain.
2. **HOMS institutional or educator pilot:** strongest visible product proof, with Grade 12 FET papers ready for demonstrations.
3. **DIO Commerce Core:** shared order, payment, fulfilment, delivery and attribution truth.
4. **Prospect Intelligence Registry:** curated organisation intelligence with enforceable POPIA permission state.
5. **DIO Demand Loop:** NicheFoundry market sensing and campaign experimentation with revenue feedback.

### Deliberately deferred

- Broad brand-awareness campaigns.
- Mass cold email or automated direct messaging.
- LinkedIn and Reddit paid advertising.
- Subscriptions, affiliates, dynamic pricing and loyalty systems.
- More than one local and one international payment provider.
- Full accounting-suite integration.
- VAMP and Sophia commerce automation before Evidex and HOMS close paid loops.
- Migrating to distributed infrastructure before SQLite becomes a demonstrated constraint.

## 3. System Ownership Boundaries

| Component | Owns | Does not own |
|---|---|---|
| Prospect Registry | Organisations, public-source provenance, fit, contact routes, permission state | Orders, payment truth or fulfilment |
| NicheFoundry | Opportunity research, campaign hypothesis, creative, metadata, UTM links | Lead qualification or revenue truth |
| Product sites | Offer explanation, proof, CTA and attribution capture | Payment confirmation or fulfilment release |
| Outlook Triage | Enquiry classification, conversation linkage, operator drafts, missing-input requests | Autonomous sending or final sales decisions |
| DIO Commerce Core | Leads, customers, offers, orders, payments, fulfilments, deliveries and event history | Product-specific artifact generation |
| Payment adapters | Provider API calls, signature verification and normalized payment events | Order or delivery policy |
| AutoRelease | Converts approved fulfilment requests into product jobs | Commercial truth or payment verification |
| HOMS/Evidex | Product-specific processing and review artifacts | Marketing attribution or payment state |
| Human operator | Qualification, exceptions, review approval, delivery approval and legal/commercial judgement | Repetitive state synchronization |
| Marketing Console | Funnel, economics and campaign decisions | Editing source-of-truth records directly |

## 4. Canonical Data Model

The Prospect Registry may be built independently, but it must expose stable IDs and the permission contract below. DIO Commerce must reference those IDs rather than copying registry records.

### Required commercial objects

| Object | Required identity | Purpose |
|---|---|---|
| organisation | `organisation_id` | Institution or company researched from a public or supplied source |
| contact | `contact_id` | Named role/contact route linked to an organisation |
| permission | `permission_event_id` | Append-only consent, customer relationship, block or withdrawal evidence |
| campaign | `campaign_id` | Product/audience/message/channel hypothesis |
| creative | `creative_id` | Specific article, video, Short, post, ad or email variant |
| landing page | `landing_page_id` | Destination and conversion contract |
| lead | `lead_id` | A captured enquiry or approved prospecting opportunity |
| customer | `customer_id` | Person or organisation with a commercial relationship |
| offer | `offer_id` | Price, scope, payment policy and fulfilment policy |
| order | `order_id` | Commercial agreement containing one or more order items |
| payment | `payment_id` | Provider-neutral payment record |
| fulfilment | `fulfilment_id` | Work required for an order item; links to one or more AutoRelease jobs |
| delivery | `delivery_id` | Approved release of artifacts to the customer |
| event | `event_id` | Immutable fact in the commercial history |
| receipt | `commercial_receipt_id` | Closeout ancestry from campaign to revenue and delivered work |

### Identity rules

- IDs are immutable and globally unique within the suite.
- Monetary values are integer minor units: `95000` means ZAR 950.00.
- Provider IDs never replace internal IDs.
- Every external event stores its provider, provider event ID, raw receipt location and verification result.
- Every product job stores `order_id`, `order_item_id`, `fulfilment_id`, and attribution IDs when available.
- Personally identifiable data is kept out of marketing analytics projections unless operationally necessary.

## 5. Independent State Machines

No single `status` field may represent the whole transaction.

```text
Lead
captured -> under_review -> qualified -> quote_sent -> accepted -> converted
                                  \-> lost

Order
draft -> awaiting_acceptance -> awaiting_payment -> accepted -> in_fulfilment
      -> review_required -> completed -> delivered -> closed
      \-> cancelled

Payment
not_required -> initiated -> pending -> succeeded
                         \-> failed
succeeded -> partially_refunded -> refunded
succeeded -> disputed

Fulfilment
queued -> blocked_payment -> ready -> processing -> needs_input
       -> needs_review -> approved -> packaged -> delivered
       \-> failed

Delivery
pending -> held_for_review -> held_for_balance -> approved -> sent -> acknowledged
```

Transitions are policy-driven. A payment event does not directly run HOMS or Evidex; it changes payment state, after which the order policy may release fulfilment.

## 6. Commercial Event Ledger

The ledger is append-only. Current state is a projection derived from accepted events.

Minimum event vocabulary:

```text
market.observation.recorded
hypothesis.created
campaign.approved
creative.published
landing.visit.recorded
lead.captured
lead.qualified
consent.requested
consent.granted
consent.withdrawn
order.created
order.accepted
invoice.issued
payment.initiated
payment.pending
payment.succeeded
payment.failed
fulfilment.released
job.created
job.completed
review.approved
delivery.sent
delivery.acknowledged
order.closed
commercial_receipt.issued
campaign.decision.recorded
```

Every event requires:

```text
event_id
event_type
occurred_at
recorded_at
actor_type
actor_id
aggregate_type
aggregate_id
correlation_id
causation_id
idempotency_key
payload
evidence_refs
```

SQLite is the first implementation target. Postgres becomes justified only when concurrent remote operation, hosted webhooks or reporting load requires it.

## 7. POPIA-Aware Prospecting Contract

The registry is an intelligence system, not permission to send marketing.

Canonical permission states:

```text
consented
existing_customer
consent_request_available
consent_request_sent
blocked
withdrawn
unknown
```

Enforcement rules:

1. No electronic marketing is released from `unknown`, `blocked` or `withdrawn`.
2. `consent_request_available` permits one operator-approved consent request, not a sales sequence.
3. A sent request immediately moves to `consent_request_sent` and cannot be repeated without a lawful new basis.
4. Every message includes sender identity and a clear refusal/opt-out route.
5. Refusal or withdrawal creates an append-only permission event and an immediate technical block.
6. Public-source provenance is stored separately from marketing permission.
7. Initial Outlook operation remains draft-only with human approval.
8. Sensitive learner, employee or beneficiary information is excluded from prospecting and campaign datasets.
9. A South African privacy/legal professional must review the production policy and templates before automated outreach is enabled.

## 8. Payment And Fulfilment Policy

### Provider order

1. **PayFast:** first local production adapter.
2. **PayPal:** international option after the PayFast loop is proven.
3. **PayShap through a merchant provider:** later local low-cost option; do not integrate the bank rail directly.
4. **Manual EFT:** operator-confirmed fallback with evidence receipt, never inferred from email text alone.

### Webhook rules

- Browser redirects are never accepted as payment proof.
- Every webhook is authenticated using the provider's required verification method.
- `provider + provider_event_id` is unique.
- Raw webhook payload and verification metadata are retained as payment evidence.
- Duplicate events are acknowledged but do not repeat transitions.
- Amount, currency, merchant identity and order reference must match before `payment.succeeded` is accepted.
- Fulfilment and delivery are released through explicit offer policy.

### Initial offer policies

| Offer | Payment policy | Fulfilment release | Delivery release |
|---|---|---|---|
| Evidex Pilot Pack | prepaid | verified full payment | human review approved |
| Evidex larger project | 50% deposit | verified deposit | review approved and balance paid |
| HOMS individual assessment pack | prepaid | verified full payment | educator review approved |
| HOMS institutional pilot | invoice terms or approved purchase order | operator approval | educator review and terms satisfied |
| Controlled free pilot | waived with recorded reason | operator approval | human review approved |

## 9. Market Sensorium And Campaign Contract

NicheFoundry's research unit must emit structured opportunities rather than generic topic ideas.

Required opportunity fields:

```text
observation_id
observed_at
source
source_url_or_reference
region
product
audience
problem
demand_signal
trend_direction
seasonality
competitive_density
commercial_intent
estimated_customer_value
existing_product_fit
confidence
recommended_experiment
```

Each approved campaign is a falsifiable hypothesis:

```text
For [persona], publishing [proof/message] through [channel]
will produce [target qualified action] within [time/cost boundary].
```

Every creative must carry:

```text
campaign_id
creative_id
offer_id
landing_page_id
utm_source
utm_medium
utm_campaign
utm_content
```

## 10. Channel Plan

### HOMS

Primary: YouTube demonstrations and Shorts, Facebook educator communities, founder LinkedIn, Google Search/SEO, school and educator associations.  
Proof: side-by-side CAPS-aware papers, source quality, cognitive-level switching, memoranda and educator-review controls.  
Initial motion: seek a controlled pilot with 5-10 independent schools or educators rather than mass teacher outreach.

### Evidex

Primary: founder LinkedIn, Google Search/SEO, NGO/M&E/CSI networks, association bulletins, webinars and case studies.  
Proof: messy input to evidence table, mapped claims, provenance, QA and reviewed delivery pack.  
Initial motion: target organisations with visible reporting obligations or donor-funded programmes through compliant routes and partnerships.

### VAMP and Sophia

Keep campaign assets ready, but do not fund acquisition until each product has a controlled fulfilment proof and Evidex/HOMS establish baseline acquisition economics.

### Paid media

- Run one high-intent Google Search experiment at a time.
- Use Meta retargeting only after meaningful site traffic exists.
- Defer LinkedIn and Reddit paid campaigns.
- Every experiment has a written spending cap and stop condition before launch.

## 11. Marketing And Commerce Console

The console is a projection, not a second source of truth.

Required views:

| View | Metrics |
|---|---|
| Acquisition | impressions, views, clicks, landing visits, spend |
| Leads | enquiries, permission state, qualified leads, quotes, conversion rate |
| Commerce | orders, awaiting payment, paid, failed, refunded, revenue, average order value |
| Fulfilment | queued, processing, blocked, needs input, needs review, completed, delivered |
| Economics | CAC, payment fees, ad spend, manual labour, gross contribution, effective hourly return, campaign ROI |
| Governance | blocked outreach, duplicate webhooks, review holds, delivery holds, outstanding consent evidence |

Attribution must follow the entire chain:

```text
campaign_id -> creative_id -> lead_id -> order_id -> payment_id
-> fulfilment_id -> job_id -> delivery_id -> commercial_receipt_id
```

## 12. Ninety-Day Work Programme

### Phase 0: Contract freeze and registry handshake (Days 1-3)

Deliverables:

- Freeze canonical IDs, state names and event envelope.
- Map the in-progress registry fields to `organisation`, `contact` and `permission` contracts.
- Add `campaign_id`, `creative_id`, `lead_id`, `order_id` and `fulfilment_id` to the shared job lineage plan.
- Define Evidex and HOMS initial offers and policies.

Acceptance gate:

- One sample organisation can be traced from registry record to a mock order without duplicated identity.
- Permission rules reject an `unknown` or `blocked` outreach attempt.

### Phase 1: Attribution and site instrumentation (Days 4-10)

Deliverables:

- Shared UTM vocabulary on all current product sites.
- First-party attribution capture at lead submission.
- Search Console and Clarity installation where deployment permits.
- Campaign, creative, offer and landing-page registry records.
- Minimal KnowEdge/DIO umbrella page linking product-specific sites.

Acceptance gate:

- A controlled visit preserves attribution through lead creation and Outlook triage.
- No sensitive form contents are sent into analytics tools.

### Phase 2: Commerce Core dry run (Days 8-18)

Deliverables:

- SQLite commerce database and migrations.
- Append-only `commerce_events` table plus order/payment/fulfilment projections.
- Offer configuration for Evidex and HOMS.
- Order creation, invoice reference and manual payment-evidence path.
- Commercial receipt v1.
- Link an existing Evidex golden job to a controlled order.

Acceptance gate:

- The existing Evidex golden loop can replay from `lead.captured` to `commercial_receipt.issued`.
- Replaying any event does not duplicate an order, job, payment or delivery.

### Phase 3: PayFast sandbox and webhook proof (Days 15-25)

Deliverables:

- Payment-provider interface.
- PayFast payment initiation adapter.
- Verified ITN/webhook endpoint.
- Raw receipt archive, normalization and idempotency.
- Payment mismatch and spoof tests.
- Fulfilment release policy.

Acceptance gate:

- Valid sandbox payment releases exactly one fulfilment.
- Duplicate notification releases nothing additional.
- Invalid signature, wrong amount, wrong currency or unknown order is held and alerted.

### Phase 4: First real Evidex commercial loop (Days 20-35)

Deliverables:

- Select one narrow Evidex offer and landing page.
- Build a 25-organisation research cohort in the registry.
- Identify compliant association, inbound and consent-request opportunities.
- Publish three proof-led pieces per week across LinkedIn/Shorts plus one substantial demonstration.
- Run one capped Google Search experiment only if tracking is proven.
- Close one real paid or explicitly waived controlled pilot.

Acceptance gate:

```text
real lead
-> qualified
-> order
-> verified payment or recorded waiver
-> Evidex job
-> human approval
-> delivery
-> commercial receipt
-> campaign decision
```

### Phase 5: First HOMS commercial loop (Days 30-50)

Deliverables:

- Publish the FET tight-eight proof library through a clear HOMS offer page.
- Build a 25-school/educator pilot cohort from legitimate public and association sources.
- Prepare association bulletin/webinar pitch and school-pilot proposal.
- Close one individual or institutional pilot.
- Route the order into either exam-studio or marking fulfilment explicitly.

Acceptance gate:

- One HOMS order closes with educator approval, delivery evidence, measured manual time and a commercial receipt.

### Phase 6: Demand Loop and weekly experiment gate (Days 35-70)

Deliverables:

- NicheFoundry opportunity schema and weekly sensor run.
- Campaign hypothesis record before creative generation.
- Marketing Console projections.
- Weekly `PROMOTE`, `CONTINUE`, `REVISE` or `KILL` receipt.
- Creative-level revenue attribution.

Acceptance gate:

- The console can identify which creative produced each paid order and show contribution after spend, fees and manual labour.

### Phase 7: Repeatability decision (Days 60-90)

Deliverables:

- PayPal adapter only if international demand exists.
- PayShap provider investigation only if local fee economics justify it.
- Documented Evidex and HOMS unit economics.
- Decision on the next product lane: VAMP, Sophia or deeper HOMS phase coverage.

Acceptance gate:

- At least one product reaches the repeatability threshold below, or a formal evidence-based pivot/stop decision is recorded.

## 13. Evidence Tiers And Campaign Decisions

| Tier | Evidence | Meaning |
|---|---|---|
| Instrumented | visit-to-lead lineage works | System can measure the experiment |
| Interest | at least 3 qualified conversations | Problem/message has credible demand |
| Commercial | at least 1 verified paid order | Someone will pay |
| Repeatable | at least 3 paid orders from at least 2 campaigns or periods | Signal is not a single friendly exception |
| Scalable | positive contribution, acceptable fulfilment load and repeatable conversion | Increase spend or outreach carefully |

Decision rules:

- **PROMOTE:** repeatable paid demand, positive gross contribution and no unresolved governance failure.
- **CONTINUE:** credible lead signal but insufficient commercial sample; continue within a fixed time/cost box.
- **REVISE:** problem signal exists but message, offer, page, qualification or fulfilment economics fail.
- **KILL:** no qualified signal after the predetermined sample, structurally negative contribution, or unacceptable compliance/fulfilment risk.

No campaign is promoted on impressions, likes or click-through rate alone.

## 14. Initial Operating Metrics

North-star metric:

```text
closed paid orders with positive gross contribution and complete evidence lineage
```

Required per-order economics:

```text
revenue
- payment fees
- ad or placement spend attributed to the order
- direct external service/API costs
- manual labour value
= gross contribution
```

Initial operational targets are hypotheses to test, not promises:

- 100% of orders have lineage from lead through delivery.
- 100% of payment success events are verified and idempotent.
- 100% of HOMS/Evidex deliverables require recorded human approval.
- 100% of outreach attempts pass the permission gate.
- Fewer than 5% of accepted jobs require identity or state repair.
- Manual minutes and revisions are recorded for every completed order.
- One paid Evidex and one paid HOMS loop are the first milestone; three paid orders establish early repeatability.

## 15. Weekly Operating Rhythm

### Monday: observe and select

- Ingest market observations.
- Review registry opportunities and seasonal signals.
- Select no more than two active hypotheses: one Evidex and one HOMS.

### Tuesday: build proof

- Generate NicheFoundry creative and landing-page variants.
- Verify claims, proof assets, CTA, UTM lineage and fulfilment readiness.

### Wednesday and Thursday: distribute and operate

- Publish through approved channels.
- Review Outlook drafts and enquiries.
- Qualify leads, issue offers and service active orders.

### Friday: reconcile and decide

- Reconcile events, payments, jobs, deliveries and manual time.
- Review funnel and contribution metrics.
- Issue a `PROMOTE`, `CONTINUE`, `REVISE` or `KILL` decision receipt.
- Feed the outcome back into the market sensorium.

## 16. Definition Of The First Full Business Proof

The architecture is not considered commercially proven until this occurs once with real external demand and real or explicitly contracted payment:

```text
NicheFoundry campaign
-> attributed visitor or permitted prospect
-> Outlook enquiry
-> qualified lead
-> accepted order
-> verified payment or approved institutional terms
-> AutoRelease fulfilment
-> HOMS or Evidex output
-> human approval
-> customer delivery
-> payment and delivery reconciliation
-> commercial receipt
-> campaign ROI decision
```

The business model is not considered repeatable until this closes at least three times without bespoke architectural changes.

## 17. Immediate Next Seven Actions

1. Complete the registry against the organisation/contact/permission contract.
2. Freeze the commercial IDs, event envelope and state machines.
3. Create the two initial offer records: Evidex Pilot Pack and HOMS Assessment Pack Pilot.
4. Instrument one Evidex landing page and one HOMS landing page with the shared attribution contract.
5. Build the SQLite Commerce Core and replay the Evidex golden loop into it.
6. Prove PayFast in sandbox with signature, mismatch, duplicate and retry tests.
7. Launch one constrained Evidex experiment and one HOMS association/pilot approach, then measure actual closed-loop economics.

