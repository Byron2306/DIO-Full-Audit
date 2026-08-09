"""
Threat Hunting Router
=====================
API endpoints for MITRE ATT&CK-based automated threat hunting.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timezone

from .dependencies import get_current_user, check_permission, get_db

router = APIRouter(prefix="/hunting", tags=["Threat Hunting"])


class HuntRequest(BaseModel):
    telemetry: Dict[str, Any]


class RuleToggleRequest(BaseModel):
    enabled: bool


class HypothesisGenerateRequest(BaseModel):
    focus: Optional[str] = None
    recent_matches: List[Dict[str, Any]] = []
    telemetry: Optional[Dict[str, Any]] = None


@router.get("/status")
async def get_hunting_status(current_user: dict = Depends(get_current_user)):
    """Get threat hunting engine status"""
    from backend.services.threat_hunting import threat_hunting_engine
    
    return {
        "status": "operational",
        **threat_hunting_engine.get_stats()
    }


@router.get("/rules")
async def get_hunting_rules(
    tactic: Optional[str] = None,
    technique: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all hunting rules"""
    from backend.services.threat_hunting import threat_hunting_engine
    
    if tactic:
        rules = threat_hunting_engine.get_rules_by_tactic(tactic)
    elif technique:
        rules = threat_hunting_engine.get_rules_by_technique(technique)
    else:
        rules = list(threat_hunting_engine.rules.values())
    
    return {
        "rules": [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "description": r.description,
                "mitre_technique": r.mitre_technique,
                "mitre_tactic": r.mitre_tactic,
                "severity": r.severity,
                "enabled": r.enabled,
                "data_sources": r.data_sources,
                "response_actions": r.response_actions
            }
            for r in rules
        ],
        "total": len(rules)
    }


@router.get("/rules/{rule_id}")
async def get_hunting_rule(
    rule_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific hunting rule"""
    from backend.services.threat_hunting import threat_hunting_engine
    from dataclasses import asdict
    
    rule = threat_hunting_engine.rules.get(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return asdict(rule)


@router.put("/rules/{rule_id}/toggle")
async def toggle_rule(
    rule_id: str,
    request: RuleToggleRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Enable or disable a hunting rule"""
    from backend.services.threat_hunting import threat_hunting_engine
    
    rule = threat_hunting_engine.rules.get(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    rule.enabled = request.enabled
    
    return {"rule_id": rule_id, "enabled": rule.enabled}


@router.post("/hunt")
async def execute_hunt(
    request: HuntRequest,
    current_user: dict = Depends(get_current_user)
):
    """Execute threat hunting on provided telemetry"""
    from backend.services.threat_hunting import threat_hunting_engine
    from dataclasses import asdict

    telemetry = dict(request.telemetry or {})
    behavior_context: Dict[str, Any] = dict(telemetry.get("behavior_context") or {})
    session_id = telemetry.get("session_id")

    # Auto-enrich behavior context from AI defense + CCE session summaries.
    if session_id:
        try:
            from threat_response import AIDefenseEngine

            metrics = AIDefenseEngine.get_session_metrics(str(session_id))
            agenticity = metrics.get("agenticity") or {}
            exhaustion = metrics.get("exhaustion") or {}
            feature_vector = agenticity.get("feature_vector") or {}

            behavior_context.setdefault("agenticity_score", float(agenticity.get("score") or 0.0))
            behavior_context.setdefault("command_velocity", float(feature_vector.get("command_velocity") or 0.0))
            behavior_context.setdefault("cbr", float(exhaustion.get("cbr") or 0.0))
            behavior_context.setdefault("tbcr", float(exhaustion.get("tbcr") or 0.0))
            behavior_context.setdefault("cdi", float(exhaustion.get("cdi") or 0.0))
        except Exception:
            pass

        db = get_db()
        if db is not None:
            try:
                summary = await db.cli_session_summaries.find_one(
                    {"session_id": str(session_id)},
                    sort=[("window_end", -1)]
                )
                if summary:
                    behavior_context.setdefault("machine_likelihood", float(summary.get("machine_likelihood") or 0.0))
                    behavior_context.setdefault("tool_switch_latency_ms", float(summary.get("tool_switch_latency_ms") or 0.0))
                    behavior_context.setdefault("goal_persistence", float(summary.get("goal_persistence") or 0.0))
            except Exception:
                pass

    # Add ML prediction context for the provided telemetry (best effort).
    try:
        from ml_threat_prediction import ml_predictor

        net_rows = telemetry.get("connections") or []
        if net_rows:
            sample = net_rows[0]
            ml_payload = {
                "source_ip": sample.get("remote_ip") or sample.get("source_ip") or "unknown",
                "bytes_in": int(sample.get("bytes_in") or 0),
                "bytes_out": int(sample.get("bytes_out") or 0),
                "packets_in": int(sample.get("packets_in") or 0),
                "packets_out": int(sample.get("packets_out") or 0),
                "unique_destinations": int(sample.get("unique_destinations") or 0),
                "unique_ports": int(sample.get("unique_ports") or 0),
                "dns_queries": int(sample.get("dns_queries") or 0),
                "failed_connections": int(sample.get("failed_connections") or 0),
                "encrypted_ratio": float(sample.get("encrypted_ratio") or 0.0),
                "avg_packet_size": float(sample.get("avg_packet_size") or 0.0),
                "connection_duration": float(sample.get("connection_duration") or 0.0),
                "port_scan_score": float(sample.get("port_scan_score") or 0.0),
            }
            ml_prediction = await ml_predictor.predict_network_threat(ml_payload)
            behavior_context.setdefault("ml_threat_score", float(getattr(ml_prediction, "threat_score", 0.0)) / 100.0)
            behavior_context.setdefault("ml_confidence", float(getattr(ml_prediction, "confidence", 0.0)))
            behavior_context.setdefault("ml_category", str(getattr(ml_prediction, "predicted_category", "")))
    except Exception:
        pass

    # Add Triune/Cognition fused context (best effort).
    try:
        db = get_db()
        if db is not None:
            from backend.services.cognition_fabric import CognitionFabricService

            fabric = CognitionFabricService(db)
            world_snapshot = {
                "entities": [{"id": str(session_id or "hunt"), "type": "session"}],
                "attack_path_graph": {"nodes": [], "edges": []},
                "trust_state": {},
                "recent_world_events": [],
            }
            cognition = await fabric.build_cognition_snapshot(
                world_snapshot=world_snapshot,
                event_type="threat_hunt",
                entity_ids=[str(session_id)] if session_id else [],
                context={
                    "behavior": {
                        "command_velocity": float(behavior_context.get("command_velocity") or 0.0),
                        "tool_switch_latency": float(behavior_context.get("tool_switch_latency_ms") or 0.0),
                    }
                },
            )
            fused = (cognition or {}).get("fused_signal") or {}
            behavior_context.setdefault("cognitive_pressure", float(fused.get("cognitive_pressure") or 0.0))
            behavior_context.setdefault("autonomous_confidence", float(fused.get("autonomous_confidence") or 0.0))
            behavior_context.setdefault("triune_policy_tier", fused.get("recommended_policy_tier"))
            behavior_context.setdefault("triune_recommended_actions", fused.get("recommended_actions") or [])
    except Exception:
        pass

    if "cognitive_pressure" not in behavior_context:
        behavior_context["cognitive_pressure"] = (
            (float(behavior_context.get("cbr") or 0.0) * 0.4)
            + (float(behavior_context.get("tbcr") or 0.0) * 0.35)
            + (float(behavior_context.get("cdi") or 0.0) * 0.25)
        )

    telemetry["behavior_context"] = behavior_context

    matches = threat_hunting_engine.hunt_all(telemetry)
    
    # Store matches in MongoDB
    db = get_db()
    if matches and db is not None:
        await db.hunting_matches.insert_many([asdict(m) for m in matches])
    
    return {
        "matches": [asdict(m) for m in matches],
        "total_matches": len(matches),
        "high_severity": len([m for m in matches if m.severity in ['critical', 'high']]),
        "behavior_context": behavior_context,
    }


@router.get("/matches")
async def get_recent_matches(
    severity: Optional[str] = None,
    technique: Optional[str] = None,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """Get recent hunting matches"""
    from backend.services.threat_hunting import threat_hunting_engine
    from dataclasses import asdict
    
    # Get from in-memory first
    matches = threat_hunting_engine.matches[-limit:]
    
    if severity:
        matches = [m for m in matches if m.severity == severity]
    
    if technique:
        matches = [m for m in matches if m.mitre_technique == technique]
    
    return {
        "matches": [asdict(m) for m in matches],
        "total": len(matches)
    }


@router.get("/matches/high-severity")
async def get_high_severity_matches(
    current_user: dict = Depends(get_current_user)
):
    """Get critical and high severity matches"""
    from backend.services.threat_hunting import threat_hunting_engine
    from dataclasses import asdict
    
    matches = threat_hunting_engine.get_high_severity_matches()
    
    return {
        "matches": [asdict(m) for m in matches[-50:]],
        "total": len(matches)
    }


@router.get("/tactics")
async def get_mitre_tactics(current_user: dict = Depends(get_current_user)):
    """Get covered MITRE ATT&CK tactics"""
    from backend.services.threat_hunting import threat_hunting_engine
    
    tactics = {}
    for rule in threat_hunting_engine.rules.values():
        tactic = rule.mitre_tactic
        if tactic not in tactics:
            tactics[tactic] = {"tactic_id": tactic, "techniques": [], "rule_count": 0}
        tactics[tactic]["techniques"].append(rule.mitre_technique)
        tactics[tactic]["rule_count"] += 1
    
    # Deduplicate techniques
    for t in tactics.values():
        t["techniques"] = list(set(t["techniques"]))
    
    return {"tactics": list(tactics.values())}


@router.get("/techniques")
async def get_mitre_techniques(current_user: dict = Depends(get_current_user)):
    """Get all covered MITRE ATT&CK techniques"""
    from backend.services.threat_hunting import threat_hunting_engine
    
    techniques = {}
    for rule in threat_hunting_engine.rules.values():
        tech = rule.mitre_technique
        if tech not in techniques:
            techniques[tech] = {
                "technique_id": tech,
                "name": rule.name,
                "tactic": rule.mitre_tactic,
                "severity": rule.severity,
                "rules": []
            }
        techniques[tech]["rules"].append(rule.rule_id)
    
    return {"techniques": list(techniques.values())}


@router.post("/hypotheses/generate")
async def generate_hunting_hypotheses(
    request: HypothesisGenerateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Generate threat hunting hypotheses using Ollama when available, with safe fallback."""
    from backend.services.ai_reasoning import ai_reasoning
    from backend.services.threat_hunting import threat_hunting_engine

    focus = request.focus or "general threat hunting"
    recent_matches = request.recent_matches or []
    in_memory_matches = threat_hunting_engine.matches[-20:]

    if not recent_matches and in_memory_matches:
        recent_matches = [
            {
                "rule_id": m.rule_id,
                "severity": m.severity,
                "mitre_tactic": m.mitre_tactic,
                "mitre_technique": m.mitre_technique,
                "description": m.rule_name
            }
            for m in in_memory_matches
        ]

    system_prompt = (
        "You are a SOC threat hunter. Return concise, actionable hunting hypotheses. "
        "Output as plain text bullet points, one hypothesis per line, max 8 lines."
    )
    prompt = (
        f"Generate hunting hypotheses for focus: {focus}.\n"
        f"Recent matches: {recent_matches[:10]}\n"
        f"Telemetry context: {request.telemetry or {}}\n"
        "Include MITRE-aligned clues and what to validate next."
    )

    method = "fallback"
    hypotheses: List[str] = []
    ollama_result = await ai_reasoning.ollama_generate(prompt=prompt, system_prompt=system_prompt)

    if "error" not in ollama_result:
        method = "ollama"
        text = (ollama_result.get("response") or "").strip()
        for line in text.splitlines():
            cleaned = line.strip().lstrip("-•0123456789. ").strip()
            if cleaned:
                hypotheses.append(cleaned)

    if not hypotheses:
        method = "rule_based"
        top_tactics = {}
        for item in recent_matches[:15]:
            tactic = item.get("mitre_tactic") or "unknown"
            top_tactics[tactic] = top_tactics.get(tactic, 0) + 1

        if top_tactics:
            ordered = sorted(top_tactics.items(), key=lambda kv: kv[1], reverse=True)
            hypotheses = [
                f"Investigate repeated activity under tactic {tactic} (seen {count} times) for hidden lateral movement or persistence."
                for tactic, count in ordered[:5]
            ]
        else:
            enabled_rules = [r for r in threat_hunting_engine.rules.values() if r.enabled]
            tactic_to_techs: Dict[str, set] = {}
            for r in enabled_rules:
                tactic_to_techs.setdefault(r.mitre_tactic, set()).add(r.mitre_technique)

            ordered_tactics = sorted(
                tactic_to_techs.items(),
                key=lambda kv: len(kv[1]),
                reverse=True,
            )

            focus_l = focus.lower()
            focus_hints = []
            if "credential" in focus_l or "identity" in focus_l:
                focus_hints.append("Prioritize credential-access and authentication anomaly hunts across privileged accounts.")
            if "lateral" in focus_l or "movement" in focus_l:
                focus_hints.append("Pivot on lateral-movement indicators: remote service creation, SMB admin shares, and unusual east-west flows.")
            if "exfil" in focus_l or "egress" in focus_l:
                focus_hints.append("Validate exfiltration staging by correlating archive activity with outbound destination rarity.")

            hypotheses = focus_hints[:]
            for tactic, techniques in ordered_tactics[:5]:
                sample_techs = ", ".join(sorted(list(techniques))[:3])
                hypotheses.append(
                    f"Hunt {tactic} activity by validating technique traces ({sample_techs}) against recent endpoint and network telemetry."
                )

            if not hypotheses:
                hypotheses = [
                    "Validate suspicious process chains against MITRE ATT&CK execution and persistence techniques.",
                    "Hunt for beaconing patterns and rare outbound connections from high-value hosts.",
                    "Check credential access signals tied to abnormal authentication timing and source diversity.",
                ]

    return {
        "focus": focus,
        "hypotheses": hypotheses[:8],
        "count": len(hypotheses[:8]),
        "method": method
    }
