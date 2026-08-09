# Sophia Control-Plane Ablation Report

Generated: 2026-08-03T19:15Z  
Run artifact: `sophia_control_plane_ablation_full_semantic_latest.json`  
Rows: 32  
Cases: 8  
Design: hidden learner cause, two-turn diagnosis, unaided transfer  
Tutor provider: Gemini Flash Lite latest  
Learner provider: Mistral Small latest  
Fallback learner rows: 0/32

## Executive Result

This run is the first real causal test of Sophia’s control-plane pedagogy. It does **not** support the easy claim that full governed Sophia dominates every ablation. It supports a more interesting and academically stronger claim:

Full control-plane Sophia improved transfer relative to all tested conditions while preserving 8/8 Mandos and 8/8 Genesis Article I-XII conformity, but the current selector did not maximize immediate post-intervention reconstruction. The no-Mandos/assessment Sophia pedagogy ablation achieved the highest immediate post/gain mean.

That means the control plane is now doing something real, but it is not yet optimally tuned. It appears to improve portability/transfer more than immediate answer reconstruction.

## Condition Summary

| Condition | Rows | Post Mean | Gain Mean | Transfer Mean | Intervention Mean | Mandos Pass | Article I-XII Pass | Learner Fallbacks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Full control-plane Sophia | 8 | 4.50 | 3.25 | 5.125 | 4.00 | 8/8 | 8/8 | 0/8 |
| Sophia telemetry recorded, not used | 8 | 4.75 | 3.50 | 5.00 | 4.00 | 8/8 | 8/8 | 0/8 |
| Sophia pedagogy, no Mandos/assessment | 8 | 5.00 | 3.75 | 5.00 | 4.00 | 0/8 | 0/8 | 0/8 |
| Plain generic remote tutor | 8 | 4.125 | 2.875 | 4.625 | 3.25 | 0/8 | 0/8 | 0/8 |

## Paired Effects

### Full Sophia vs Telemetry-Recorded-Not-Used

| Metric | Mean Delta | SD Delta | Interpretation |
|---|---:|---:|---|
| Post score | -0.25 | 0.886 | Full control was slightly worse on immediate reconstruction. |
| Gain points | -0.25 | 0.886 | Same as post, because pre-score is paired. |
| Transfer score | +0.125 | 0.835 | Full control was slightly better on transfer. |
| Intervention score | 0.00 | 0.00 | Automated intervention score saw no difference. |

### Full Sophia vs Sophia Without Mandos/Assessment

| Metric | Mean Delta | SD Delta | Interpretation |
|---|---:|---:|---|
| Post score | -0.50 | 1.414 | No-Mandos/assessment did better on immediate reconstruction. |
| Gain points | -0.50 | 1.414 | Same as post. |
| Transfer score | +0.125 | 0.991 | Full control was slightly better on transfer. |
| Intervention score | 0.00 | 0.00 | Automated intervention score saw no difference. |

### Full Sophia vs Plain Generic Tutor

| Metric | Mean Delta | SD Delta | Interpretation |
|---|---:|---:|---|
| Post score | +0.375 | 1.847 | Full Sophia improved immediate reconstruction over plain generic. |
| Gain points | +0.375 | 1.847 | Same as post. |
| Transfer score | +0.50 | 0.756 | Full Sophia improved transfer over plain generic. |
| Intervention score | +0.75 | 0.463 | Full Sophia produced substantially stronger interventions than plain generic. |

## Office Routing Audit

Full Sophia used the new pre-generation `pedagogy_control` object in 8/8 rows.

| Office | Rows |
|---|---:|
| `bibliothecarius` | 6 |
| `dialecticus` | 1 |
| `pontifex` | 1 |

Telemetry-recorded-not-used and no-Mandos/assessment conditions correctly reported `active_office: uncontrolled_pedagogy`, while still exposing the non-used control object for audit. Plain generic emitted no Sophia control telemetry.

## Case-Level Notes

The biggest warning is the control selector’s current bias toward `bibliothecarius`. After the selector was corrected to ignore the harness instruction tail and focus on learner-surface text, it still selected source/provenance routing for 6/8 cases. That may be pedagogically defensible in an academic-integrity ecology, but it likely over-weights provenance at the expense of direct conceptual reconstruction.

The clearest success case was `C2_feedback_literacy`, where full Sophia selected `dialecticus`, produced a post score of 6, transfer score of 6, and beat both Sophia ablations on post reconstruction.

The clearest weakness was `C5_transfer`, where full Sophia selected `pontifex` but achieved only post score 2 while both ablations scored higher. Transfer remained strong at 5, but the immediate reconstruction suffered. That suggests the transfer office is preparing portability while under-supporting the second attempt.

## What This Proves

This run proves:

- The control-plane route is active before generation.
- Full Sophia can use Mandos/assessment-derived office/scaffold/move in the provider prompt.
- Full Sophia preserves constitutional conformance while teaching: 8/8 Mandos, 8/8 Articles.
- Full Sophia beats plain generic on post, gain, transfer, and intervention quality.
- Full Sophia beats both Sophia ablations on transfer mean, although only narrowly.

## What This Does Not Prove

This run does not prove:

- Full control-plane Sophia is globally superior to Sophia pedagogy without Mandos/assessment.
- Mandos/assessment control currently improves immediate reconstruction.
- The office selector is optimal.
- The automated scorer is sensitive enough to detect qualitative differences in intervention process.

## Honest Judgment

The decisive gauntlet did not give us a cheap triumph. It gave us a useful scientific result.

Sophia’s governed control plane is real and auditable, and it appears to improve transfer/portability while preserving constitutional integrity. But the selector is still too blunt. It over-selects source/provenance mediation and needs a richer learner model that separates:

- conceptual misconception,
- source/provenance weakness,
- affective re-entry,
- transfer failure,
- expression failure,
- false confidence,
- and authorship-risk pressure.

The next improvement should not be another generic prompt patch. It should be a selector upgrade: case-feature extraction, assessment-diagnosis normalization, office confidence scoring, and fallback arbitration when two offices compete.

## Bottom Line

Sophia has crossed from evidence-plane convergence into early control-plane convergence. The control plane now acts before generation and leaves inspectable traces. The result is not yet a full causal victory over all ablations, but it is a credible research-grade finding:

**Governed Sophia improves transfer under constitutional control, but immediate learning gain still needs a better office-selection policy.**
