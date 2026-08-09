# Sophia Pedagogy Outcome Calibration Suite

Timestamp: `2026-08-03T20:23:43.757527+00:00`

## Summary

| Metric | Value |
|---|---:|
| Cases | 5 |
| Passed | 5 |
| Failed | 0 |
| Pass rate | 100.00% |

## Case Results

| Case | Result | Key signal |
|---|---:|---|
| `blinded_human_rating_ingestion_recommends_weight_direction` | PASS | recommendations=[{'office': 'source_librarian', 'direction': 'increase', 'rating_mean': 0.94}, {'office': 'writing_coach', 'direction': 'decrease', 'rating_mean': 0.64}] |
| `control_plane_weights_compare_to_outcomes` | PASS | correlation=0.9833 |
| `longer_history_learner_state_decay_visible` | PASS | memory_strength=0.096 band=stale_verify_before_use |
| `adversarial_plagiarism_mutation_routes_integrity` | PASS | office=integrity_auditor integrity_score=0.366 |
| `delayed_transfer_separated_from_immediate_post_gain` | PASS | weights={'post_quality': 0.33, 'learning_gain': 0.29, 'delayed_transfer': 0.38} outcomes={'post_quality': 0.7, 'learning_gain': 0.58, 'delayed_transfer': 1.0} |

## Interpretation

This suite does not claim human learning validation is complete. It proves the measurement plumbing needed for that validation: rater ingestion, control-plane/outcome comparison, learner-memory decay, adversarial office arbitration, and delayed-transfer separation.

Next decisive step: run the blinded learner-production gauntlet, complete the rater CSV with real expert ratings, then rerun this calibrator against those completed rows.
