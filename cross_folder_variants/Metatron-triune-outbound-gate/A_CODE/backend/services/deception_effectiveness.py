from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from backend.schemas.deception_models import DeceptionMode
except Exception:
    from schemas.deception_models import DeceptionMode  # type: ignore


def parse_iso_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        normalized = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def summarize_effectiveness_case(
    doc: Dict[str, Any],
    case_events: List[Dict[str, Any]],
    case_serves: List[Dict[str, Any]],
) -> Dict[str, Any]:
    timeline = (((doc.get("execution_notes") or {}).get("timeline")) or [])
    timeline_ts = [parse_iso_ts(step.get("timestamp")) for step in timeline]
    event_ts = [parse_iso_ts(event.get("timestamp")) for event in case_events]
    serve_ts = [parse_iso_ts(serve.get("timestamp")) for serve in case_serves]
    all_ts = [ts for ts in [*timeline_ts, *event_ts, *serve_ts] if ts is not None]

    bytes_burned = 0
    false_path_depth = 0
    lure_touch_count = 0
    containment_handoff = False
    objective_drift_detected = False
    real_target_pivot_suppressed = False
    disengaged = False
    false_positive_engagement_suspected = False

    for serve in case_serves:
        bytes_burned += int(serve.get("payload_size_bytes") or 0)

    last_active_ts: Optional[datetime] = None
    first_active_ts: Optional[datetime] = None
    for event in case_events:
        event_type = str(event.get("event_type") or "")
        details = event.get("details") or {}
        ts = parse_iso_ts(event.get("timestamp"))
        if ts is not None:
            if first_active_ts is None or ts < first_active_ts:
                first_active_ts = ts
            if last_active_ts is None or ts > last_active_ts:
                last_active_ts = ts
        if event_type == "maze_traversal":
            bytes_burned += int(details.get("total_bytes_consumed") or 0)
            false_path_depth = max(false_path_depth, int(details.get("total_probes") or 0))
            if str(details.get("inferred_intent") or "") not in {"unknown", ""}:
                objective_drift_detected = True
        if event_type in {"decoy_interaction", "honey_token_access", "honeypot_interaction"}:
            lure_touch_count += 1
        if event_type in {"decoy_interaction", "honey_token_access", "honeypot_interaction", "maze_traversal"}:
            false_positive_engagement_suspected = bool(
                doc.get("trusted_principal_blocked")
                or str(doc.get("risk_band") or "").lower() == "low"
                or str(doc.get("confidence_band") or "").lower() == "low"
            )

    for step in timeline:
        note = str(step.get("note") or "").lower()
        status = str(step.get("status") or "").lower()
        ts = parse_iso_ts(step.get("timestamp"))
        if ts is not None:
            if first_active_ts is None or ts < first_active_ts:
                first_active_ts = ts
            if last_active_ts is None or ts > last_active_ts:
                last_active_ts = ts
        if "contain" in note:
            containment_handoff = True
        if "downgraded" in note or "blocked" in note or status in {"downgraded", "blocked"}:
            real_target_pivot_suppressed = True

    dwell_time_seconds = 0.0
    dwell_time_extension_seconds = 0.0
    if len(all_ts) >= 2:
        ordered = sorted(all_ts)
        dwell_time_seconds = max(0.0, (ordered[-1] - ordered[0]).total_seconds())
        dwell_time_extension_seconds = max(0.0, dwell_time_seconds - 1.0)

    if last_active_ts is not None:
        updated_at = parse_iso_ts(doc.get("updated_at")) or last_active_ts
        disengaged = (updated_at - last_active_ts).total_seconds() >= 300.0 and doc.get("status") in {
            "served",
            "engaged",
            "captured",
            "ready",
        }

    mode = str(doc.get("deception_mode") or "unknown")
    if doc.get("status") in {"served", "engaged", "captured", "ready"} and not case_events and not case_serves:
        outcome = "creative_unmeasured"
    elif mode == DeceptionMode.DISINFORMATION.value and case_serves:
        outcome = "poisoned_payload_served"
    elif mode == DeceptionMode.MIRROR_WORLD.value and false_path_depth > 0:
        outcome = "false_branch_commitment"
    elif lure_touch_count > 0:
        outcome = "decoy_engaged"
    elif doc.get("status") == "downgraded":
        outcome = "safety_downgraded"
    else:
        outcome = "observed_only"

    mode_success = False
    success_criterion = "no_measurable_success"
    if mode == DeceptionMode.DISINFORMATION.value:
        mode_success = len(case_serves) > 0
        success_criterion = "subject_followed_poisoned_intelligence" if mode_success else "no_poisoned_intelligence_served"
    elif mode == DeceptionMode.MIRROR_WORLD.value:
        mode_success = false_path_depth > 0
        success_criterion = "subject_committed_to_false_branch_expansion" if mode_success else "no_false_branch_commitment"
    elif mode in {DeceptionMode.TRAP_SINK.value, DeceptionMode.HONEYPOT.value}:
        mode_success = dwell_time_extension_seconds >= 5.0 or disengaged
        success_criterion = "subject_slowed_materially" if mode_success else "no_material_slowdown_detected"
    elif lure_touch_count > 0:
        mode_success = True
        success_criterion = "subject_interacted_with_planted_assets"

    return {
        "outcome": outcome,
        "mode_success": mode_success,
        "success_criterion": success_criterion,
        "metrics": {
            "lure_touch_count": lure_touch_count,
            "repeat_lure_touch_rate": round(max(0.0, lure_touch_count - 1) / max(lure_touch_count, 1), 6)
            if lure_touch_count
            else 0.0,
            "false_path_exploration_depth": false_path_depth,
            "dead_end_branch_commitment_rate": round(min(1.0, false_path_depth / 5.0), 6),
            "estimated_context_burn_bytes": bytes_burned,
            "objective_drift_detected": objective_drift_detected,
            "real_target_pivot_suppressed": real_target_pivot_suppressed,
            "containment_handoff": containment_handoff,
            "disengagement_detected": disengaged,
            "dwell_time_seconds": round(dwell_time_seconds, 6),
            "dwell_time_extension_seconds": round(dwell_time_extension_seconds, 6),
            "false_positive_engagement_suspected": false_positive_engagement_suspected,
            "disinformation_serves": len(case_serves),
        },
    }
