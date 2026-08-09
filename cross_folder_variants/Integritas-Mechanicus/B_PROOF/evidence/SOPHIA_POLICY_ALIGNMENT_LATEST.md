# Sophia Policy Alignment Report

Timestamp: `2026-08-03T20:37:10.917679+00:00`

## Summary

| Metric | Value |
|---|---:|
| Sources | 6 |
| Extracted sources | 6 |
| Article alignments | 12/12 |
| Assistance categories | 7 |
| Cases passed | 5/5 |

## Article Alignment

| Article | Duty | Status | NWU primary signal | Global/SA signal |
|---|---|---|---:|---:|
| I | human authorship | aligned_signal_present | True | True |
| II | evidence and truth boundaries | aligned_signal_present | True | False |
| III | refusal and repair capacity | aligned_signal_present | True | True |
| IV | office and lane limits | aligned_signal_present | True | True |
| V | semantic judgment | aligned_signal_present | True | True |
| VI | chain integrity | aligned_signal_present | True | True |
| VII | repair transparency | aligned_signal_present | True | True |
| VIII | provenance status | aligned_signal_present | True | True |
| IX | harmonic cadence and learner support | aligned_signal_present | True | True |
| X | custodial accountability | aligned_signal_present | True | True |
| XI | human supremacy and final judgment | aligned_signal_present | True | True |
| XII | honest limitation | aligned_signal_present | True | True |

## Assistance Categories

| Category | Class | Policy Signal | Release Rule |
|---|---|---:|---|
| `allowed_learning_scaffold` | allowed_or_conditional | True | `assist_with_scaffold_and_disclosure` |
| `allowed_source_discovery_and_triage` | allowed_or_conditional | True | `assist_with_scaffold_and_disclosure` |
| `conditional_language_feedback` | allowed_or_conditional | True | `assist_with_scaffold_and_disclosure` |
| `conditional_ai_use_with_disclosure` | allowed_or_conditional | True | `assist_with_scaffold_and_disclosure` |
| `disallowed_ghostwriting_or_final_answer_substitution` | disallowed | True | `refuse_and_offer_lawful_alternative` |
| `disallowed_concealment_or_detector_evasion` | disallowed | True | `refuse_and_offer_lawful_alternative` |
| `disallowed_fabricated_sources_or_false_support` | disallowed | True | `refuse_and_offer_lawful_alternative` |

## Institutional Audit Language

Sophia is designed as an authorship-preserving academic assistant: it may support learning, source triage, feedback, and reflection, but must refuse ghostwriting, concealment, detector evasion, fabricated sources, and unsupported claims.

Minimum audit fields:
- `assistance_category`
- `human_authorship_preserved`
- `source_provenance_visible`
- `disclosure_or_acknowledgement_needed`
- `final_answer_substitution_risk`
- `fabricated_source_risk`
- `release_or_refusal_decision`
- `learner_owned_next_action`

## Truth Boundary

This report is a policy-alignment aid, not legal advice and not an institutional approval. NWU/module-specific instructions, current Senate rules, and formal university guidance remain authoritative.
