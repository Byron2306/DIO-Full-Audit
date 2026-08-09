# Phased Build Plan

## Phase 0: Clean Foundation

Goal: stop the old crypto research system from consuming disk, CPU, and attention.

Completed:

- Docker images and build cache pruned.
- Hivenance trading databases and event logs removed.
- Running crypto loops stopped.
- New lightweight suite workspace created.

## Phase 1: Intake Spine

Goal: prove one reusable job pipeline.

Required outputs:

- Shared job schema.
- Shared evidence schema.
- Route classifier.
- Outlook/Triage ingestion adapter.
- Evidex adapter.
- NicheFoundry adapter.
- Demo run using fake inbox/email records.
- Deliverable folder with generated review artifacts.

Recommended first route:

```text
Outlook export / triage CSV
-> normalize messages into jobs
-> route grant/compliance requests to Evidex
-> route campaign/content requests to NicheFoundry
-> create review-ready job folders
```

Success criteria:

- A fake or exported email can become a job packet.
- Job packet includes source evidence, route, risk, and next action.
- Evidex route creates an evidence-pack request.
- NicheFoundry route creates a content/campaign request.
- Nothing sends automatically.
- Every generated output is reviewable.

Current status:

- Demo intake route works.
- Evidex adapter calls the real Evidex engine successfully.
- NicheFoundry adapter prepares campaign requests.
- Outlook Triage CSV import works.
- Router false positives were found and fixed through boundary matching and evidence-note exclusion from intent routing.

## Phase 2: Productized Evidex

Goal: make Evidex the first sellable done-for-you offer.

Build:

- Intake form or local intake folder.
- Evidence manifest.
- KPI/proof/source mapping.
- Pack template.
- Delivery ZIP.
- Invoice/payment gate placeholder.
- Delivery email draft.

Current status:

- Evidex engine is called successfully from AutoRelease.
- Deterministic pack ZIP is generated.
- Service offer, client questions, payment gate, and ZIP contents are generated.
- Approval receipts work.
- Dashboard displays job status and approval state.

Demo offer:

```text
Upload grant or reporting evidence and receive a structured evidence pack.
```

## Phase 3: NicheFoundry Growth Engine

Goal: use NicheFoundry internally to market the suite.

Build:

- Product campaign template.
- HOMS/VAMP/Evidex/Sophia lead magnet topics.
- LinkedIn/article/video script generation.
- Human editorial approval gate.
- Publishing checklist.

Primary output:

```text
Weekly campaign pack for one product offer.
```

Current status:

- Product layers are configured.
- Campaign/storyboard packs generated for Evidex, HOMS, Outlook Triage, VAMP, and Sophia.
- Dashboard displays campaign status.
- Full media rendering remains gated behind editorial approval.

## Phase 4: Outlook Triage as Front Door

Goal: make inbox work route into product jobs.

Build:

- Triage CSV/JSON importer.
- Route buttons or config routes.
- Redaction before storage.
- POPIA/privacy notes.
- Daily closeout.
- Job creation from approved message.

Important posture:

```text
Draft-only. No autonomous sending.
```

## Phase 5: Add HOMS, VAMP, Sophia

Goal: attach the strongest vertical modules.

Order:

1. HOMS marking batch route.
2. VAMP performance evidence route.
3. Sophia academic review route.

Each module should receive the same job envelope and produce reviewable deliverables.
