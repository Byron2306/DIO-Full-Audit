# Evidex Transaction Loop Proof

Updated: 2026-08-07

## Status

Controlled complete loop passed.

This is not a live client sale. Payment and delivery are simulated/manual markers, deliberately labeled as such. The purpose is to prove that every gate exists and produces an auditable receipt.

## Gate Chain

```text
ad
-> reply
-> Outlook triage
-> AutoRelease job
-> qualified lead approval
-> approved evidence intake
-> Evidex generation
-> human review
-> payment state
-> delivery
-> closeout receipt
-> business telemetry
```

## Closeout

```text
deliverables/evidex_golden_transaction_loop/evidex/evidex-488c40b13ce3498ed076/CLOSEOUT_RECEIPT.json
```

## Golden Case

```text
campaigns/phase3/evidex/golden_case/GOLDEN_EVIDEX_CASE.md
sites/evidex/golden-case/index.html
```

Local page:

```text
http://127.0.0.1:8787/golden-case/
```

## Telemetry

```text
telemetry/business_loop.csv
telemetry/business_loop.jsonl
dashboard/index.html
```

Current controlled row:

```text
prospects: 1
qualified leads: 1
intake started: 1
intake completed: 1
pack started: 1
pack approved: 1
delivery: 1
payment: 1
manual time estimate: 18 minutes
processing time: 1.139 seconds
revisions requested: 0
revenue/job: ZAR 950
effective hourly return: ZAR 3166.67
```

## What This Proves

- The product promise can be shown as a single understandable case.
- Outlook-first intake is sufficient to start a transaction loop.
- Evidex can produce a pack with evidence table, source provenance, QA report, invoice, delivery email, and ZIP.
- Business telemetry can answer whether the loop is worth repeating.

## What It Does Not Prove Yet

- It does not prove a stranger will pay.
- It does not prove the Google Form/Drive trigger is fixed.
- It does not prove payment provider webhooks.
- It does not prove real-world messy data will stay under the same manual-time estimate.

The next meaningful test is one controlled human pilot with a fake/redacted real-world sample and a real payment decision.
