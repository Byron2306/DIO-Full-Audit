# DIO Product Platform — Wave 1

Date: 2026-08-11  
Status: architecture seeded, execution deliberately locked

## Executive finding

DIO now has a shared product-platform layer for nine new governed products without pretending that nine independent production systems have suddenly been completed.

The platform separates four truths:

1. **registered** — DIO recognises the product and its evidence, authority, output and risk contracts;
2. **routable** — configured Outlook/intake language can classify a bounded request into the product;
3. **governable** — DIO can materialise a canonical job and governed case with requirements, evidence, gates and human authorities;
4. **executable** — a product-specific runner, validation receipt and release contract exist.

Wave 1 completes the first three for the new portfolio. The fourth remains explicitly locked unless a product already has a proven sibling capability that can later be bound safely.

```text
inbound request
      ↓
DIO route
      ↓
registered product profile
      ↓
raw routed job
      ↓
portfolio reconciler
      ↓
JOB.json + CASE.json
      ↓
requirements + evidence + gates + planned outputs
      ↓
product-specific executor gate: REFUSE (not implemented)
      ↓
future product implementation + human review + release authority
```

## New product registry

Canonical registry:

```text
config/dio_product_portfolio.json
```

Registered products:

| Product | Primary domain | Wave 1 state | Public campaign |
|---|---|---|---|
| DIO Assurance | AI governance and assurance evidence | Architecture seeded; external validation required | Enabled for review-only campaign generation |
| DIO Agent Authority | Governed agent action control | Architecture seeded; generic executor absent | Enabled for review-only campaign generation |
| DIO VendorProof | Third-party/vendor due diligence | Evidence workflow seeded | Enabled for review-only campaign generation |
| DIO Accreditation | Institutional quality and accreditation evidence | High-reuse architecture seeded | Enabled for review-only campaign generation |
| DIO TenderProof | Tender/RFP requirement and evidence governance | Submission locked | Enabled for review-only campaign generation |
| DIO GrantProof | Grant obligation and reporting evidence | High Evidex reuse | Enabled for review-only campaign generation |
| DIO Research Integrity | Claim/source/revision lineage | Sophia snapshot refresh required | Enabled for review-only campaign generation |
| DIO RegOps | Operational prerequisite and compliance readiness | Legalis snapshot refresh required | Enabled for review-only campaign generation |
| DIO CapitalRoom | Internal investor diligence and fundraising evidence | Internal architecture seeded | **Disabled** |

`campaign_enabled` is not publication authority. Existing campaign tooling still produces review candidates that require operator editorial and release approval.

## Canonical governed case

Schema:

```text
schemas/dio_governed_case.schema.json
```

Every generic portfolio job materialises a `CASE.json` beside `JOB.json`.

The case preserves one shared grammar across products:

```text
case identity
→ commercial lineage
→ requirements
→ claims
→ evidence
→ gates
→ human/system decisions
→ planned/reviewed/released outputs
```

This is intentionally broader than a product-specific request schema. Tender requirements, accreditation criteria, grant obligations, AI controls, vendor questionnaire rows and regulatory prerequisites can all enter the same requirement/evidence/gate model while retaining product-specific profiles and authorities.

Initial case gates are conservative:

- `intake_authority`: `ALLOW`, `REFUSE` or `NEEDS_YOU` based on the existing intake decision;
- `generic_executor`: always `REFUSE` in Wave 1 because no generic product executor is implemented;
- `external_release`: `NEEDS_YOU` and remains human-authority bound.

The case object therefore makes the new products governable without turning product registration into execution authority.

## Generic request contract

Schema:

```text
schemas/dio_product_request.schema.json
```

The request envelope captures:

- product ID;
- requester identity and organisation/role;
- bounded scope and objective;
- jurisdiction or framework where relevant;
- deadline and sensitivity;
- evidence references;
- requested outputs;
- processing and service consent.

The contract is suitable for later product-specific forms or adapters, but public edge intake is **not** expanded in this wave. Existing public product allow-lists remain unchanged until each new product has a truthful public offer and validated fulfilment route.

## Routing

`config/routes.json` now includes specific high-priority routes for all nine products.

The new routes deliberately use phrases such as:

- `AI governance` / `ISO 42001`;
- `agent authority` / `capability lease`;
- `vendor due diligence` / `third-party risk`;
- `accreditation evidence` / `programme review`;
- `tender compliance` / `mandatory requirements`;
- `grant agreement` / `donor obligations`;
- `claim lineage` / `research integrity`;
- `regulatory readiness` / `licence renewal`;
- `investor diligence` / `capital raise`.

They are ordered ahead of broad legacy words such as `grant`, `compliance` and `audit` so a specific product request is not swallowed by Evidex merely because one generic keyword also appears.

Routing remains classification, not acceptance or processing authority.

## Generic product runtime

Runtime module:

```text
products/registry.py
```

Useful CLI:

```bash
python3 scripts/plan_product_layer.py --list
python3 scripts/plan_product_layer.py --product dio_assurance
python3 scripts/plan_product_layer.py --source-job runs/<run>/<product>/<job>.json
```

For a registered product, bootstrap creates:

```text
state/product_jobs/<JOB-ID>/JOB.json
state/product_jobs/<JOB-ID>/CASE.json
```

The workflow explicitly records:

```text
classification = registered
planning       = enabled
execution      = not_implemented
external_release = held
commercial_claim = architecture_seeded_not_product_proven
```

`processing.state` remains `not_started`. Registration is stored separately as `processing.profile_state = registered` so the commercial transaction spine cannot mistake profile registration for actual processing.

## Continuous reconciliation

Script:

```text
scripts/reconcile_product_portfolio.py
```

It watches raw routed jobs created under:

```text
runs/mailbox-auto-*/<registered-product>/*.json
```

and idempotently materialises canonical product state under `state/product_jobs/`.

A malformed individual job is isolated and reported rather than stopping reconciliation of every other product.

Systemd unit:

```text
deploy/systemd/dio-product-portfolio-reconciler.service
```

Example installation in the live KnowEdge/DIO checkout:

```bash
cp deploy/systemd/dio-product-portfolio-reconciler.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now dio-product-portfolio-reconciler.service
systemctl --user status dio-product-portfolio-reconciler.service
```

The reconciler performs no sending, charging, publication, product execution, or release action.

## Campaign generation

Script:

```text
scripts/build_portfolio_campaigns.py
```

It reuses the existing Phase 3 NicheFoundry campaign/storyboard builder for the eight customer-facing portfolio candidates:

```bash
python3 scripts/build_portfolio_campaigns.py
```

Default output:

```text
campaigns/product_portfolio_wave1/
```

Each pack inherits the existing controls against fake metrics, fabricated testimonials, private client data and claims that AI replaces professional judgement.

DIO CapitalRoom is excluded by code because it is currently an internal fundraising/diligence layer, not a public product campaign.

## Product-specific activation gates

### DIO Assurance

Highest-value near-term flagship. Before production claims:

1. refresh this Full Audit snapshot with current Sophia production lineage;
2. import and verify current Legalis implementation;
3. define one external assurance framework profile;
4. complete an independent enterprise pilot.

### DIO Agent Authority

The governance pattern exists, but the generic executor does not.

Before execution:

1. define a generic executor interface;
2. define rollback/reversibility receipts;
3. bind current ARDA attestation evidence;
4. prove one non-destructive external action end to end.

### DIO VendorProof

Strong Evidex/Sophia/VAMP reuse. Next implementation work:

1. vendor-questionnaire parser;
2. evidence freshness rules;
3. one public risk/control framework profile;
4. external vendor review pilot.

### DIO Accreditation

Strongest institutional reuse from VAMP + Evidex + HOMS.

Next:

1. select one accreditation framework;
2. create a framework profile;
3. map portable VAMP evidence objects to criteria;
4. run one programme pilot.

### DIO TenderProof

The key boundary is submission authority.

Next:

1. tender/RFP requirement extractor;
2. mandatory/deadline object contract;
3. Legalis evidence binding;
4. locked package proof with **no autonomous submission**.

### DIO GrantProof

Strong Evidex extension from one-off pack to persistent obligation lineage.

Next:

1. grant-agreement parser;
2. reporting-period object;
3. Evidex generator binding;
4. bounded external pilot.

### DIO Research Integrity

The Full Audit must first catch up with the newer Sophia production work.

Next:

1. import Sophia Wave 2 lineage evidence;
2. bind stable claim IDs into governed cases;
3. formalise independent reviewer roles;
4. external research-group pilot.

### DIO RegOps

The product contract reflects Legalis but the current Full Audit snapshot does not yet contain Legalis.

Next:

1. import and verify Legalis Wave 1;
2. deadline/renewal scheduler interface;
3. one real prerequisite profile;
4. professional review of production policy.

### DIO CapitalRoom

Internal-only in Wave 1.

Next:

1. refresh the Full Audit snapshot;
2. define investor/fund target schema;
3. bind DIO claims to supporting evidence and safe wording;
4. keep every outbound investor communication under explicit founder release.

## Truth statement

Wave 1 does **not** mean DIO suddenly has nine production-ready products.

It means DIO now possesses a reusable product constitution:

```text
profile
+ route
+ request contract
+ governed case
+ canonical job
+ evidence requirements
+ authority gates
+ campaign boundary
+ activation gates
```

That reduces the next product implementation from "invent another standalone system" to "bind a validated domain parser/runner into an already governed DIO product slot."

That is the intended convergence win.
