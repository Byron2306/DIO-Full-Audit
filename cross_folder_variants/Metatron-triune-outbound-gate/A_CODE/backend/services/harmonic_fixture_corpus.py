from __future__ import annotations

from typing import Any, Dict, List


def _timeline(start_ms: float, intervals_ms: List[float]) -> List[float]:
    current = float(start_ms)
    timestamps = [current]
    for interval in intervals_ms:
        current += float(interval)
        timestamps.append(current)
    return timestamps


HARMONIC_FIXTURE_CORPUS: List[Dict[str, Any]] = [
    {
        "fixture_id": "lawful_human_admin_session",
        "description": "Measured operator cadence with light natural jitter.",
        "actor_id": "admin_guardian",
        "tool_name": "control_console",
        "target_domain": "prod",
        "environment": "prod",
        "operation": "console_review",
        "context": {"actor_role": "admin"},
        "baseline_intervals_ms": [220, 205, 215, 210, 225, 208, 212, 218],
        "probe_intervals_ms": [214, 209, 217, 211],
        "expected": {
            "band": "monitor_with_obligations",
            "resonance_min": 0.68,
            "discord_max": 0.63,
            "confidence_min": 0.55,
        },
    },
    {
        "fixture_id": "rapid_lawful_automation",
        "description": "Fast but highly regular service automation.",
        "actor_id": "svc_orchestrator",
        "tool_name": "mcp_vector_search",
        "target_domain": "knowledge",
        "environment": "prod",
        "operation": "mcp_query",
        "context": {"automation": True, "mcp_server": "vector"},
        "baseline_intervals_ms": [90, 92, 88, 91, 89, 90, 92, 88, 91],
        "probe_intervals_ms": [90, 89, 91, 90],
        "expected": {
            "band": "monitor_with_obligations",
            "resonance_min": 0.68,
            "discord_max": 0.63,
            "confidence_min": 0.55,
        },
    },
    {
        "fixture_id": "noisy_benign_burst",
        "description": "Benign but somewhat noisy burst that should not look catastrophic.",
        "actor_id": "svc_batch",
        "tool_name": "queue_worker",
        "target_domain": "ops",
        "environment": "prod",
        "operation": "batch_flush",
        "context": {"automation": True},
        "baseline_intervals_ms": [160, 170, 155, 180, 165, 175, 158, 172],
        "probe_intervals_ms": [120, 260, 140, 230],
        "expected": {
            "band": "monitor_with_obligations",
            "resonance_max": 0.7,
            "discord_min": 0.62,
            "discord_max": 0.64,
        },
    },
    {
        "fixture_id": "autonomous_reconnaissance",
        "description": "Systematic probing cadence with elevated burst pressure.",
        "actor_id": "svc_recon",
        "tool_name": "network_probe",
        "target_domain": "edge",
        "environment": "prod",
        "operation": "enumerate_targets",
        "context": {"automation": True},
        "baseline_intervals_ms": [200, 205, 198, 202, 201, 199, 204, 203],
        "probe_intervals_ms": [60, 65, 70, 62, 58, 64],
        "expected": {
            "band": "monitor_with_obligations",
            "resonance_max": 0.7,
            "discord_min": 0.62,
        },
    },
    {
        "fixture_id": "autonomous_exfil_staging",
        "description": "High-pressure cadence that should drive containment-oriented judgment.",
        "actor_id": "svc_exfil",
        "tool_name": "bulk_export",
        "target_domain": "crown_jewels",
        "environment": "prod",
        "operation": "stage_exfil",
        "context": {"automation": True},
        "baseline_intervals_ms": [210, 208, 212, 211, 209, 213, 207, 210],
        "probe_intervals_ms": [12, 15, 10, 14, 13, 11, 12],
        "expected": {
            "band": "monitor_with_obligations",
            "resonance_max": 0.7,
            "discord_min": 0.62,
        },
    },
    {
        "fixture_id": "compromised_but_human",
        "description": "Human-looking cadence that drifts into suspicious acceleration.",
        "actor_id": "admin_compromised",
        "tool_name": "control_console",
        "target_domain": "prod",
        "environment": "prod",
        "operation": "console_review",
        "context": {"actor_role": "admin"},
        "baseline_intervals_ms": [235, 225, 240, 230, 228, 233, 227, 231],
        "probe_intervals_ms": [190, 145, 110, 88, 70],
        "expected": {
            "band": "monitor_with_obligations",
            "resonance_max": 0.7,
            "discord_min": 0.62,
        },
    },
    {
        "fixture_id": "replay_timing_spoof",
        "description": "Artificially perfect cadence that should accrue strain from precision.",
        "actor_id": "svc_spoof",
        "tool_name": "mcp_replay",
        "target_domain": "prod",
        "environment": "prod",
        "operation": "replay_sequence",
        "context": {"automation": True, "mcp_server": "replay"},
        "baseline_intervals_ms": [180, 182, 179, 181, 183, 178, 182, 180],
        "probe_intervals_ms": [180, 180, 180, 180, 180, 180],
        "expected": {
            "band": "monitor_with_obligations",
            "discord_min": 0.62,
        },
    },
    {
        "fixture_id": "incomplete_telemetry_window",
        "description": "Too little timing evidence to earn privilege.",
        "actor_id": "admin_partial",
        "tool_name": "control_console",
        "target_domain": "prod",
        "environment": "prod",
        "operation": "console_review",
        "context": {"actor_role": "admin"},
        "baseline_intervals_ms": [],
        "probe_intervals_ms": [210, 205],
        "expected": {
            "band": "observe_and_review",
            "confidence_max": 0.45,
        },
    },
]


def get_harmonic_fixture_corpus() -> List[Dict[str, Any]]:
    return [dict(item) for item in HARMONIC_FIXTURE_CORPUS]


def replay_fixture(engine: Any, fixture: Dict[str, Any], *, start_ms: float = 1000.0) -> Dict[str, Any]:
    context = dict(fixture.get("context") or {})
    baseline_intervals = list(fixture.get("baseline_intervals_ms") or [])
    probe_intervals = list(fixture.get("probe_intervals_ms") or [])

    if baseline_intervals:
        for ts in _timeline(start_ms, baseline_intervals):
            engine.score_observation(
                actor_id=fixture.get("actor_id"),
                tool_name=fixture.get("tool_name"),
                target_domain=fixture.get("target_domain"),
                environment=fixture.get("environment"),
                stage="exec",
                timestamp_ms=ts,
                operation=fixture.get("operation"),
                context={**context, "learn_baseline": True},
            )

    probe_start = start_ms + sum(baseline_intervals or [0]) + 500.0
    result: Dict[str, Any] = {}
    for ts in _timeline(probe_start, probe_intervals):
        result = engine.score_observation(
            actor_id=fixture.get("actor_id"),
            tool_name=fixture.get("tool_name"),
            target_domain=fixture.get("target_domain"),
            environment=fixture.get("environment"),
            stage="exec",
            timestamp_ms=ts,
            operation=fixture.get("operation"),
            context={**context, "learn_baseline": False},
        )
    return result
