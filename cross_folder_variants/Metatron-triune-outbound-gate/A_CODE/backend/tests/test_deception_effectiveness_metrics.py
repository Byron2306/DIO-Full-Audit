from backend.services.deception_effectiveness import summarize_effectiveness_case


def test_effectiveness_metrics_include_dwell_disengagement_and_false_positive_signals():
    doc = {
        "deception_case_id": "deception-123",
        "deception_mode": "mirror_world",
        "status": "engaged",
        "risk_band": "low",
        "confidence_band": "low",
        "trusted_principal_blocked": False,
        "updated_at": "2026-08-01T12:12:00+00:00",
        "execution_notes": {
            "timeline": [
                {
                    "timestamp": "2026-08-01T12:00:00+00:00",
                    "status": "ready",
                    "note": "mirror-world maze activated",
                },
                {
                    "timestamp": "2026-08-01T12:02:00+00:00",
                    "status": "engaged",
                    "note": "containment handoff initiated after blocked pivot",
                },
            ]
        },
    }
    case_events = [
        {
            "event_type": "maze_traversal",
            "timestamp": "2026-08-01T12:05:00+00:00",
            "details": {
                "total_probes": 4,
                "total_bytes_consumed": 4096,
                "inferred_intent": "exfiltration",
            },
        },
        {
            "event_type": "decoy_interaction",
            "timestamp": "2026-08-01T12:05:30+00:00",
            "details": {},
        },
        {
            "event_type": "decoy_interaction",
            "timestamp": "2026-08-01T12:06:00+00:00",
            "details": {},
        },
    ]
    case_serves = []

    summary = summarize_effectiveness_case(doc, case_events, case_serves)
    metrics = summary["metrics"]

    assert summary["outcome"] == "false_branch_commitment"
    assert metrics["false_path_exploration_depth"] == 4
    assert metrics["estimated_context_burn_bytes"] == 4096
    assert metrics["objective_drift_detected"] is True
    assert metrics["containment_handoff"] is True
    assert metrics["real_target_pivot_suppressed"] is True
    assert metrics["repeat_lure_touch_rate"] == 0.5
    assert metrics["dead_end_branch_commitment_rate"] == 0.8
    assert metrics["dwell_time_seconds"] == 360.0
    assert metrics["dwell_time_extension_seconds"] == 359.0
    assert metrics["disengagement_detected"] is True
    assert metrics["false_positive_engagement_suspected"] is True
