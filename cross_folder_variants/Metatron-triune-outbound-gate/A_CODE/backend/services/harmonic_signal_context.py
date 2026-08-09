from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from backend.services.aatl import get_aatl_engine
except Exception:
    from services.aatl import get_aatl_engine  # type: ignore

try:
    from backend.services.vns import vns
except Exception:
    from services.vns import vns  # type: ignore


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _find_world_entity(db: Any, entity_id: Optional[str]) -> Dict[str, Any]:
    if not db or not entity_id:
        return {}
    entities = getattr(db, "world_entities", None)
    docs = getattr(entities, "docs", None)
    if not isinstance(docs, list):
        return {}
    for doc in docs:
        if str(doc.get("id")) == str(entity_id):
            return dict(doc)
    return {}


def _find_deception_events(
    db: Any,
    *,
    session_id: Optional[str],
    campaign_id: Optional[str],
) -> list[Dict[str, Any]]:
    if not db:
        return []
    coll = getattr(db, "deception_events", None)
    docs = getattr(coll, "docs", None)
    if not isinstance(docs, list):
        return []
    results = []
    for doc in docs:
        if session_id and str(doc.get("session_id") or "") == str(session_id):
            results.append(dict(doc))
            continue
        if campaign_id and str(doc.get("campaign_id") or "") == str(campaign_id):
            results.append(dict(doc))
    return results


def _graph_pressure_from_world(db: Any, actor_id: Optional[str], context: Dict[str, Any]) -> Dict[str, Any]:
    entity_id = context.get("world_entity_id") or actor_id
    entity = _find_world_entity(db, entity_id)
    attrs = dict(entity.get("attributes") or {})
    risk_score = _clamp(_safe_float(context.get("world_risk_score", attrs.get("risk_score", 0.0))))
    centrality = _clamp(_safe_float(context.get("graph_centrality", attrs.get("graph_centrality", 0.0))))
    privilege_pressure = _clamp(_safe_float(context.get("privilege_escalation_likelihood", attrs.get("privilege_escalation_likelihood", 0.0))))
    trust_state = str(context.get("trust_state") or attrs.get("trust_state") or "unknown").lower()
    trust_penalty = {
        "stable": 0.0,
        "unknown": 0.0,
        "degraded": 0.18,
        "strained": 0.25,
        "fallen": 0.35,
        "dissonant": 0.35,
    }.get(trust_state, 0.0)
    pressure = _clamp((0.45 * risk_score) + (0.20 * centrality) + (0.20 * privilege_pressure) + trust_penalty)
    return {
        "world_entity_id": entity_id,
        "world_risk_score": round(risk_score, 6),
        "graph_centrality": round(centrality, 6),
        "privilege_escalation_likelihood": round(privilege_pressure, 6),
        "trust_state": trust_state,
        "world_graph_pressure": round(pressure, 6),
    }


def _aatl_pressure_from_context(context: Dict[str, Any]) -> Dict[str, Any]:
    aatl = dict(context.get("aatl_assessment") or {})
    behavior_flags = dict(context.get("behavior_flags") or {})
    timing_data = dict(context.get("aatl_timing") or {})
    if not aatl and (behavior_flags or timing_data):
        try:
            aatl = get_aatl_engine().score_http_request(behavior_flags=behavior_flags, timing_data=timing_data)
        except Exception:
            aatl = {}
    machine_plausibility = _clamp(
        _safe_float(
            aatl.get("machine_plausibility", aatl.get("actor_confidence", 0.0))
        )
    )
    threat_score = _clamp(_safe_float(aatl.get("threat_score", 0.0)) / 100.0)
    goal_convergence = _clamp(
        _safe_float((aatl.get("intent_accumulation") or {}).get("goal_convergence_score", 0.0))
    )
    pressure = _clamp(max(machine_plausibility, threat_score, goal_convergence))
    return {
        "aatl_actor_type": str(aatl.get("actor_type") or "unknown").lower(),
        "aatl_machine_plausibility": round(machine_plausibility, 6),
        "aatl_threat_score": round(threat_score, 6),
        "aatl_goal_convergence": round(goal_convergence, 6),
        "aatl_lifecycle_stage": str(aatl.get("lifecycle_stage") or "unknown").lower(),
        "aatl_pressure": round(pressure, 6),
    }


def _vns_pressure_from_context(context: Dict[str, Any]) -> Dict[str, Any]:
    if "vns_assessment" in context:
        assessment = dict(context.get("vns_assessment") or {})
        suspicious_flows = int(assessment.get("suspicious_flows", 0) or 0)
        total_flows = max(1, int(assessment.get("total_flows", 0) or 0))
        beacon_confidence = _clamp(_safe_float(assessment.get("beacon_confidence", 0.0)))
        suspicious_ratio = suspicious_flows / total_flows
    else:
        endpoint_ip = context.get("endpoint_ip")
        flows = vns.get_flows(src_ip=endpoint_ip, limit=200) if endpoint_ip else []
        suspicious_flows = sum(1 for flow in flows if str(flow.get("status") or "").lower() == "suspicious")
        total_flows = max(1, len(flows))
        suspicious_ratio = suspicious_flows / total_flows
        beacons = vns.get_beacon_detections(limit=50)
        beacon_confidence = 0.0
        if endpoint_ip:
            for beacon in beacons:
                if str(beacon.get("src_ip")) == str(endpoint_ip):
                    beacon_confidence = max(beacon_confidence, _safe_float(beacon.get("confidence", 0.0)))
    pressure = _clamp(max(suspicious_ratio, beacon_confidence))
    return {
        "vns_suspicious_flow_ratio": round(suspicious_ratio, 6),
        "vns_beacon_confidence": round(beacon_confidence, 6),
        "vns_pressure": round(pressure, 6),
    }


def _deception_pressure_from_context(db: Any, context: Dict[str, Any]) -> Dict[str, Any]:
    if "deception_assessment" in context:
        assessment = dict(context.get("deception_assessment") or {})
        decoy_touches = int(assessment.get("decoy_touches", 0) or 0)
        branch_persistence = _clamp(_safe_float(assessment.get("branch_persistence", 0.0)))
        false_branch_commitment = _clamp(_safe_float(assessment.get("false_branch_commitment", 0.0)))
        contradiction_pressure = _clamp(_safe_float(assessment.get("contradiction_pressure", 0.0)))
        context_burn_tolerance = _clamp(_safe_float(assessment.get("context_burn_tolerance", 0.0)))
    else:
        events = _find_deception_events(
            db,
            session_id=context.get("session_id"),
            campaign_id=context.get("campaign_id"),
        )
        decoy_touches = 0
        maze_traversals = 0
        contradiction_hits = 0
        burn_hits = 0
        for event in events:
            event_type = str(event.get("event_type") or "").lower()
            details = dict(event.get("details") or {})
            if event_type in {"decoy_interaction", "honey_token_access", "honeypot_interaction"}:
                decoy_touches += 1
            if event_type == "maze_traversal":
                maze_traversals += 1
                if bool(details.get("false_branch_commitment")) or bool(details.get("dead_end_commit")):
                    contradiction_hits += 0
            if event_type in {"contradiction_probe", "logic_budget_probe"}:
                contradiction_hits += 1
            if event_type in {"context_burn", "repeat_after_burn", "burn_resistant_probe"}:
                burn_hits += 1
        branch_persistence = _clamp(maze_traversals / 4.0)
        false_branch_commitment = _clamp(
            _safe_float(
                max(
                    context.get("false_branch_commitment", 0.0),
                    min(1.0, maze_traversals / 5.0),
                )
            )
        )
        contradiction_pressure = _clamp(max(_safe_float(context.get("contradiction_pressure", 0.0)), contradiction_hits / 3.0))
        context_burn_tolerance = _clamp(max(_safe_float(context.get("context_burn_tolerance", 0.0)), burn_hits / 3.0))
    decoy_touch_pressure = _clamp(decoy_touches / 3.0)
    pressure = _clamp(
        (0.25 * decoy_touch_pressure)
        + (0.25 * branch_persistence)
        + (0.20 * false_branch_commitment)
        + (0.15 * contradiction_pressure)
        + (0.15 * context_burn_tolerance)
    )
    return {
        "deception_decoy_touches": decoy_touches,
        "deception_branch_persistence": round(branch_persistence, 6),
        "deception_false_branch_commitment": round(false_branch_commitment, 6),
        "deception_contradiction_pressure": round(contradiction_pressure, 6),
        "deception_context_burn_tolerance": round(context_burn_tolerance, 6),
        "deception_pressure": round(pressure, 6),
    }


def build_harmonic_signal_context(
    *,
    db: Any,
    actor_id: Optional[str],
    tool_name: Optional[str],
    target_domain: Optional[str],
    environment: Optional[str],
    operation: Optional[str],
    context: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    resolved = dict(context or {})
    world = _graph_pressure_from_world(db, actor_id, resolved)
    aatl = _aatl_pressure_from_context(resolved)
    vns_ctx = _vns_pressure_from_context(resolved)
    deception = _deception_pressure_from_context(db, resolved)
    pressure = _clamp(
        (0.40 * world["world_graph_pressure"])
        + (0.25 * aatl["aatl_pressure"])
        + (0.15 * vns_ctx["vns_pressure"])
        + (0.20 * deception["deception_pressure"])
    )
    return {
        "actor_id": actor_id,
        "tool_name": tool_name,
        "target_domain": target_domain,
        "environment": environment,
        "operation": operation,
        **world,
        **aatl,
        **vns_ctx,
        **deception,
        "composite_context_pressure": round(pressure, 6),
    }
