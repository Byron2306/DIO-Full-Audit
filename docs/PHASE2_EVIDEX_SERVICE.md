# Phase 2: Evidex Service Layer

Status: working.

Phase 2 turns the Evidex adapter from a technical pack generator into a productized service flow.

## Command

```bash
python3 scripts/run_phase1_pipeline.py \
  --input samples/inbox/demo_inbox.json \
  --run runs/phase2_demo \
  --out deliverables/phase2_demo
```

The pipeline now includes:

```text
route intake
-> build review pack
-> run deterministic Evidex engine
-> build Evidex service layer
-> prepare NicheFoundry request
-> prepare HOMS request
-> build operator dashboard
```

## Phase 2 Evidex Outputs

For each Evidex job, the service layer creates:

- `SERVICE_OFFER.md`
- `CLIENT_INTAKE_QUESTIONS.md`
- `PAYMENT_GATE.md`
- `PHASE2_EVIDEX_RECEIPT.json`
- `ZIP_CONTENTS.txt`

The underlying Evidex engine also creates:

- Executive summary DOCX.
- Evidence table CSV/XLSX.
- Narrative justification DOCX.
- Source folder.
- Appendix DOCX.
- Delivery email draft.
- Invoice DOCX.
- Quality report.
- Delivery ZIP.

## Pricing Config

Pricing and service questions are configured in:

```text
config/evidex_service.json
```

Current tiers:

- Pilot Pack.
- NGO Standard Pack.
- Consultant Batch Pack.
- Urgent 48h Pack.

## Gate Rules

The current service gate is intentionally manual:

```text
No automatic email.
No automatic final delivery.
Payment confirmation required before final delivery.
Operator approval required before final delivery.
```

The manual payment marker is:

```text
PAID.txt
```

## Approval

Approval is recorded with:

```bash
python3 scripts/approve_job.py \
  --job runs/phase2_demo/evidex/evidex-120d089d3bce3548e92d.json \
  --state approved \
  --reviewer byron \
  --note "Approved for deterministic service-pack review."
```

This writes:

```text
runs/<run>/evidex/<job_id>.approval.json
```

## Operator Dashboard

Build or refresh:

```bash
python3 scripts/build_operator_dashboard.py
```

Open:

```text
dashboard/index.html
```

## What Is Not Automated Yet

- Real payment provider integration.
- Automatic delivery email sending.
- Client-facing web intake form.
- Final client upload portal.
- LLM-enhanced summaries/narrative.

Those are intentionally deferred until the deterministic service loop is stable.

