# Production Engine Attachment Audit

Date: 2026-08-16
Receipt: `state/production_engines/ENGINE_AUDIT_RECEIPT.json`
Audit tool: `scripts/audit_product_engines.py`

## Current Verdict

The detached-engine problem has been repaired at the control-layer contract level.

The latest audit now reports:

- Audited engines: **6**
- Attached or partial: **6**
- Detached or CLI-only: **0**
- Average readiness score: **80.3**

The remaining work is no longer “find the missing engines.” The remaining work is **smoke testing, lead-to-job conversion, typed HOMS lanes, and premium NicheFoundry video promotion**.

## Attachment Matrix

| Product | Verdict | Score | Current attachment state | Remaining work |
|---|---:|---:|---|---|
| Evidex | attached | 82 | Generic product workflow calls the real Evidex evidence-pack CLI. VAMP can also call Evidex internally. | Promote Evidex into the richer Sophia/VAMP-style commercial lifecycle. |
| HOMS | attached | 78 | Product workflow now runs HyMark when a complete batch folder exists; incomplete intake is explicitly marked as waiting for source files. | Add typed HOMS commercial lanes for marking, exam studio, and learning studio. |
| Sophia | attached | 84 | Dedicated commercial manager supports create, quote, reconcile, run, approve, delivery. | Add a live controlled smoke-run receipt surfaced in Systems. |
| VAMP | attached with Evidex dependency | 80 | Dedicated commercial manager calls snapshot pipeline and can run Evidex internally. | Add dependency-health card and a generic non-NWU golden demo. |
| Document Studio / Lingua | attached | 82 | New commercial manager and Control Deck route support create, quote, reconcile, run, approve, delivery. Lingua QA remains semantic authority. | Bridge public document-studio leads into typed jobs and run a controlled commercial smoke test. |
| Market Media Factory / NicheFoundry | short-form attached, premium partial | 76 | 24 campaign families have media receipts and short-form reel outputs. | Build premium/long-form episode promotion into full NicheFoundry episode folders. |

## What Changed

### HOMS

The old behavior allowed a HOMS workflow to stop at `prepared_request_only`, which could look like progress while the real assessor had not run.

The workflow now does this:

`approved intake -> complete HyMark input folder? -> run HyMark -> review_ready -> approve output -> delivery`

If the source is incomplete:

`approved intake -> awaiting_source_files -> source upload notification`

That means HOMS no longer pretends a request file is an assessment pack.

### Document Studio / Lingua

Document Studio now has a first-class commercial manager:

`scripts/manage_document_studio_commercial.py`

It supports:

- create
- quote
- reconcile payment
- run
- approve
- prepare delivery
- status

It uses the existing Document Studio engine and keeps Lingua/BEAST approval separate. That is the right split: the product can run and deliver a review pack, while reusable semantic truth still requires proficient review and crystallization.

### Control Deck

The dashboard now includes:

- a Document Studio tab
- Document Studio attention queue items
- Document Studio fulfilment rows
- Document Studio action buttons
- Systems cards for engine attachment

Control route added:

`/api/control/document-studio/action`

### Audit

The audit now checks the attachment contract and records the result into:

`state/production_engines/ENGINE_AUDIT_RECEIPT.json`

This prevents the UI from quietly going green while a product engine is detached underneath.

## Remaining Build Order

1. Run controlled smoke tests for HOMS, Document Studio, Evidex, Sophia, and VAMP.
2. Bridge public leads into typed product jobs instead of only capturing website requests.
3. Promote HOMS into typed service lanes:
   - marking batch
   - exam studio
   - learning material / extra class pack
4. Promote Evidex into a dedicated commercial manager.
5. Build the premium NicheFoundry episode promotion bridge for YouTube-grade videos.

## Operational Rule

A product is production-attached only when this route exists:

`public intake -> qualified lead/order -> quote/payment state -> engine run -> human review -> delivery draft -> approval/send -> closeout receipt`

By this rule, the control layer is now attached for every major engine, but the lead-to-job and smoke-test layers still need to be tightened before live marketing is treated as fully reliable.
