"""
Deception Engine API Router
============================
Endpoints for Seraph's advanced deception system featuring:
- Pebbles (Campaign Tracking)
- Mystique (Adaptive Deception)
- Stonewall (Progressive Escalation)
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from enum import Enum
import logging
import os
from collections import Counter

from deception_engine import deception_engine, RouteDecision, EscalationLevel
from .dependencies import get_current_user, get_db
from backend.services.deception_authority import DeceptionAuthorityService
from backend.services.deception_effectiveness import summarize_effectiveness_case
from backend.services.deception_policy import get_policy_matrix
from backend.schemas.deception_models import DeceptionCase, DeceptionMode

logger = logging.getLogger(__name__)


def _feature_enabled(name: str, default: str = "true") -> bool:
    return os.environ.get(name, default).lower() == "true"

try:
    from backend.services.world_events import emit_world_event
    from backend.services.token_broker import token_broker
except Exception:
    emit_world_event = None
    token_broker = None

try:
    from backend.services.mystique_maze import get_mystique_maze
except Exception:
    get_mystique_maze = None

try:
    from backend.services.aatl import get_aatl_engine
except Exception:
    get_aatl_engine = None

try:
    from backend.services.disinformation_engine import get_disinfo_engine
except Exception:
    get_disinfo_engine = None

router = APIRouter(prefix="/deception", tags=["Deception Engine"])

def _severity_to_risk(severity: str) -> int:
    s = str(severity or "").lower().strip()
    if s == "critical":
        return 95
    if s == "high":
        return 80
    if s == "medium":
        return 60
    if s == "low":
        return 35
    return 50


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class RouteDecisionEnum(str, Enum):
    PASS_THROUGH = "pass_through"
    FRICTION = "friction"
    TRAP_SINK = "trap_sink"
    HONEYPOT = "honeypot"
    DISINFORMATION = "disinformation"


class RiskAssessmentRequest(BaseModel):
    ip: str
    path: str = "/"
    headers: Dict[str, str] = Field(default_factory=dict)
    session_id: Optional[str] = None
    timing_data: Optional[Dict[str, Any]] = None
    behavior_flags: Optional[Dict[str, Any]] = None


class RiskAssessmentResponse(BaseModel):
    score: int
    reasons: List[str]
    route: str
    delay_ms: int
    campaign_id: Optional[str]
    fingerprint_id: Optional[str]
    escalation_level: str
    maze_id: Optional[str] = None
    maze_surface_nodes: Optional[List[Dict[str, Any]]] = None
    disinformation_payload: Optional[Dict[str, Any]] = None
    # AATL timing-enriched fields — returned so the harness can record the
    # router-computed values rather than the caller-supplied floor values.
    machine_plausibility: Optional[float] = None
    aatl_actor_type: Optional[str] = None
    aatl_indicators: List[str] = Field(default_factory=list)
    agenticity_score: Optional[float] = None
    deception_case_id: Optional[str] = None


class DecoyInteractionRequest(BaseModel):
    ip: str
    decoy_type: str
    decoy_id: str
    session_id: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)


class DeployDecoyRequest(BaseModel):
    host_id: str = Field(default="deception-engine")
    decoy_type: str = Field(default="credentials")
    decoys: List[str] = Field(default_factory=lambda: ["svc_backup:Winter2026!", "api_key_trap_01"])
    placement: str = Field(default="standard")


class IPRequest(BaseModel):
    ip: str


class CampaignQueryParams(BaseModel):
    min_events: int = Field(default=5, ge=1, le=1000)
    limit: int = Field(default=50, ge=1, le=500)


class EventQueryParams(BaseModel):
    limit: int = Field(default=100, ge=1, le=1000)
    route_filter: Optional[str] = None
    campaign_id: Optional[str] = None


# =============================================================================
# STATUS & CONFIG
# =============================================================================

@router.get("/status")
async def get_deception_status():
    """Get deception engine status and configuration"""
    status = deception_engine.get_status()

    # Frontend compatibility: DeceptionPage expects top-level engine/status booleans.
    config = status.get("config", {}) if isinstance(status, dict) else {}
    return {
        **status,
        "engine": "Seraph Deception Engine",
        "status": "active",
        "uptime": status.get("uptime", "n/a") if isinstance(status, dict) else "n/a",
        "pebbles_enabled": True,
        "mystique_enabled": bool(config.get("mystique_enabled", True)),
        "stonewall_enabled": bool(config.get("stonewall_enabled", True)),
    }


@router.get("/capabilities")
async def get_capabilities():
    """Get list of deception capabilities"""
    return {
        "engine": "Seraph Deception Engine",
        "capabilities": [
            {
                "name": "Pebbles",
                "description": "Campaign-based attack correlation via behavioral fingerprints",
                "features": ["fingerprint_tracking", "campaign_correlation", "cross_session_linking"]
            },
            {
                "name": "Mystique",
                "description": "Self-adapting deception parameters based on attacker behavior",
                "features": ["adaptive_friction", "adaptive_tarpit", "dynamic_thresholds"]
            },
            {
                "name": "Stonewall",
                "description": "Progressive escalation for persistent attackers",
                "features": ["soft_ban", "hard_ban", "automatic_blocklisting"]
            },
            {
                "name": "Risk Scoring",
                "description": "Weighted behavioral risk assessment",
                "features": ["multi_signal", "weighted_scoring", "categorical_reasons"]
            },
            {
                "name": "Friction",
                "description": "Graduated response delays based on risk",
                "features": ["adaptive_delays", "challenge_mode", "rate_limiting"]
            },
            {
                "name": "Trap Sink",
                "description": "Tarpit + containment for high-risk traffic",
                "features": ["tarpit_delay", "deny_access", "campaign_tracking"]
            },
            {
                "name": "Logic-Budget Exhaustion Controller",
                "description": "Adapts deception routing using CBR/TBCR/CDI and agenticity pressure",
                "features": ["context_burn_rate", "tool_budget_pressure", "confidence_degradation", "forced_sink_routing"]
            }
        ],
        "decisions": [d.value for d in RouteDecision],
        "escalation_levels": [e.value for e in EscalationLevel]
    }


@router.get("/policy/matrix")
async def get_deception_policy_matrix(current_user: dict = Depends(get_current_user)):
    """Return the explicit deception escalation policy matrix."""
    return {"matrix": get_policy_matrix(), "count": len(get_policy_matrix())}


# =============================================================================
# RISK ASSESSMENT
# =============================================================================

@router.post("/assess", response_model=RiskAssessmentResponse)
async def assess_risk(request: RiskAssessmentRequest, db=Depends(get_db)):
    """
    Perform risk assessment on an incoming request.
    Returns routing decision with delay if applicable.
    """
    merged_behavior_flags: Dict[str, Any] = dict(request.behavior_flags or {})

    # Enrich with formal AI metrics when a session is present.
    if request.session_id:
        try:
            from threat_response import AIDefenseEngine

            metrics = AIDefenseEngine.get_session_metrics(request.session_id)
            agenticity = metrics.get("agenticity") or {}
            exhaustion = metrics.get("exhaustion") or {}

            if "agenticity_score" not in merged_behavior_flags:
                merged_behavior_flags["agenticity_score"] = float(agenticity.get("score") or 0.0)
            if "autonomous_confidence" not in merged_behavior_flags:
                merged_behavior_flags["autonomous_confidence"] = float(agenticity.get("score") or 0.0)
            if "cbr" not in merged_behavior_flags:
                merged_behavior_flags["cbr"] = float(exhaustion.get("cbr") or 0.0)
            if "tbcr" not in merged_behavior_flags:
                merged_behavior_flags["tbcr"] = float(exhaustion.get("tbcr") or 0.0)
            if "cdi" not in merged_behavior_flags:
                merged_behavior_flags["cdi"] = float(exhaustion.get("cdi") or 0.0)
        except Exception:
            # Keep assessment resilient when AI defense services are unavailable.
            pass

    # ── AATL machine-tempo enrichment ─────────────────────────────────────────
    # The AATL engine computes machine_plausibility from real timing signals
    # (inter-request cadence, timing variance, request velocity) and from
    # agenticity pressure already in merged_behavior_flags.  We always run this
    # — even without a session — because the timing path is stateless.
    try:
        _aatl = get_aatl_engine() if get_aatl_engine is not None else None
        if _feature_enabled("AATL_TIMING_ENABLED") and _aatl is not None:
            aatl_result = _aatl.score_http_request(
                behavior_flags=merged_behavior_flags,
                timing_data=request.timing_data,
            )
            # Overwrite only when AATL derives a stronger signal than the
            # caller-supplied value (harness sets it = agenticity_score, which
            # is the behavioral-vector score, not a timing-derived score).
            if aatl_result["machine_plausibility"] > float(
                merged_behavior_flags.get("machine_plausibility", 0.0)
            ):
                merged_behavior_flags["machine_plausibility"] = aatl_result["machine_plausibility"]
                merged_behavior_flags["aatl_actor_type"] = aatl_result["actor_type"]
                merged_behavior_flags["aatl_indicators"] = aatl_result["indicators"]
    except Exception:
        pass  # AATL enrichment is best-effort; never break the routing path

    assessment = await deception_engine.process_request(
        ip=request.ip,
        path=request.path,
        headers=request.headers,
        session_id=request.session_id,
        timing_data=request.timing_data,
        behavior_flags=merged_behavior_flags
    )
    soar_enabled = _feature_enabled("SOAR_ENABLED")

    # ── GOVERNANCE / TAMPER-EVIDENT LOG on TRAP_SINK ──────────────────────────
    if assessment.route == RouteDecision.TRAP_SINK and request.session_id:
        logic_budget_force_trap = "logic_budget_pressure" in (assessment.reasons or []) or \
            any("logic_budget" in r for r in (assessment.reasons or []))
        agenticity_classification = merged_behavior_flags.get("agenticity_classification", "")
        agenticity_score = float(merged_behavior_flags.get("agenticity_score") or 0.0)
        cbr = float(merged_behavior_flags.get("cbr") or 0.0)
        tbcr = float(merged_behavior_flags.get("tbcr") or 0.0)

        # Emit action-critical world event (triggers Triune recompute + constitutional veto check)
        if soar_enabled and emit_world_event is not None:
            try:
                import asyncio
                asyncio.ensure_future(emit_world_event(
                    db=None,
                    event_type="ai_logic_budget_trap",
                    entity_refs=[request.session_id, request.ip or "unknown"],
                    payload={
                        "session_id": request.session_id,
                        "ip": request.ip,
                        "score": assessment.score,
                        "reasons": assessment.reasons,
                        "campaign_id": assessment.campaign_id,
                        "agenticity_score": agenticity_score,
                        "agenticity_classification": agenticity_classification,
                        "cbr": cbr,
                        "tbcr": tbcr,
                        "logic_budget_force_trap": logic_budget_force_trap,
                        "impact_level": "critical",
                    },
                    source="deception_engine",
                ))
            except Exception:
                pass

        # Revoke active capability tokens for the AI session principal
        if token_broker is not None and _feature_enabled("TOKEN_BROKER_ENABLED"):
            try:
                token_broker.apply_ai_trust_degradation(
                    session_id=request.session_id,
                    agenticity_score=agenticity_score,
                    agenticity_classification=agenticity_classification or "HIGH",
                    cbr=cbr,
                    tbcr=tbcr,
                    logic_budget_force_trap=logic_budget_force_trap,
                )
            except Exception:
                pass

    # ── DISINFORMATION ─────────────────────────────────────────────────────────
    # When route is DISINFORMATION: generate a poisoned-but-plausible response
    # and emit a world event (STRATEGIC class) for the governance layer.
    disinfo_payload: Optional[Dict[str, Any]] = None
    deception_case_id: Optional[str] = None
    deception_authority = DeceptionAuthorityService(db)
    harmonic_state = merged_behavior_flags.get("harmonic_state")
    if not isinstance(harmonic_state, dict):
        harmonic_state = {}

    if assessment.route == RouteDecision.DISINFORMATION and get_disinfo_engine is not None:
        try:
            case, case_validation = await deception_authority.create_case(
                session_id=request.session_id,
                campaign_id=assessment.campaign_id,
                source_ip=request.ip,
                path=request.path,
                trigger_reason="route_decision:disinformation",
                triggering_signals=list(assessment.reasons or []),
                desired_mode=DeceptionMode.DISINFORMATION,
                risk_score=assessment.score,
                headers=request.headers,
                behavior_flags=merged_behavior_flags,
                harmonic_state=harmonic_state,
            )
            deception_case_id = case.deception_case_id
            if case.deception_mode == DeceptionMode.DISINFORMATION and case_validation.allowed:
                disinfo_svc = get_disinfo_engine()
                disinfo_svc.set_db(db)
                candidate_payload, serve_record = disinfo_svc.generate(
                    path=request.path,
                    session_id=request.session_id,
                    campaign_id=assessment.campaign_id,
                    risk_score=assessment.score,
                    reasons=assessment.reasons,
                    behavior_flags=merged_behavior_flags,
                )
                payload_validation = await deception_authority.authorize_payload(
                    case=case,
                    payload=candidate_payload,
                )
                if payload_validation.allowed:
                    disinfo_payload = candidate_payload
                    await disinfo_svc.persist_serve(
                        record=serve_record,
                        payload=candidate_payload,
                        deception_case_id=case.deception_case_id,
                    )
                    await deception_authority.record_execution_outcome(
                        case=case,
                        status="served",
                        note="synthetic disinformation payload served",
                        output_class="synthetic_payload",
                        extra={
                            "serve_id": serve_record.serve_id,
                            "disinfo_category": serve_record.category,
                            "payload_size_bytes": serve_record.payload_size_bytes,
                        },
                    )
                else:
                    merged_behavior_flags["deception_downgraded"] = True
                    assessment.reasons = list(dict.fromkeys(list(assessment.reasons or []) + payload_validation.reasons))
            else:
                merged_behavior_flags["deception_downgraded"] = True
                assessment.reasons = list(dict.fromkeys(list(assessment.reasons or []) + case_validation.reasons))
            if soar_enabled and emit_world_event is not None:
                import asyncio
                asyncio.ensure_future(emit_world_event(
                    db=None,
                    event_type="ai_adversary_disinformation_served",
                    entity_refs=[request.session_id or "anon", request.ip or "unknown"],
                    payload={
                        "deception_case_id": deception_case_id,
                        "session_id": request.session_id,
                        "ip": request.ip,
                        "path": request.path,
                        "campaign_id": assessment.campaign_id,
                        "risk_score": assessment.score,
                        "disinfo_category": disinfo_payload.get("category"),
                        "reasons": assessment.reasons,
                    },
                    source="disinformation_engine",
                ))
        except Exception as exc:
            logger.warning(f"Disinformation generation failed: {exc}")

    # ── MYSTIQUE MIRROR WORLD MAZE ────────────────────────────────────────────
    # Activate the maze when:
    #   (a) route is HONEYPOT, OR
    #   (b) TRAP_SINK and agenticity is HIGH/VERY_HIGH
    maze_id: Optional[str] = None
    maze_surface: Optional[List[Dict[str, Any]]] = None

    should_activate_maze = (
        _feature_enabled("MIRROR_MAZE_ENABLED")
        and _feature_enabled("MYSTIQUE_ENABLED")
        and (
            assessment.route == RouteDecision.HONEYPOT
            or (
                assessment.route == RouteDecision.TRAP_SINK
                and request.session_id
                and (
                    # Layer 1: AATL timing-based machine plausibility (real tempo signal)
                    merged_behavior_flags.get("machine_plausibility", 0.0) >= 0.6
                    # Layer 2: Agenticity behavioral feature vector (fallback)
                    or merged_behavior_flags.get("agenticity_score", 0.0) >= 0.6
                )
            )
        )
    )

    if should_activate_maze and request.session_id and get_mystique_maze is not None:
        try:
            case, case_validation = await deception_authority.create_case(
                session_id=request.session_id,
                campaign_id=assessment.campaign_id,
                source_ip=request.ip,
                path=request.path,
                trigger_reason="route_decision:mirror_world",
                triggering_signals=list(assessment.reasons or []),
                desired_mode=DeceptionMode.MIRROR_WORLD,
                risk_score=assessment.score,
                headers=request.headers,
                behavior_flags=merged_behavior_flags,
                harmonic_state=harmonic_state,
            )
            deception_case_id = deception_case_id or case.deception_case_id
            if case.deception_mode == DeceptionMode.MIRROR_WORLD and case_validation.allowed:
                maze_svc = get_mystique_maze()
                maze_svc.set_persistence(db)
                maze_state = await maze_svc.get_or_create_maze(
                    session_id=request.session_id,
                    campaign_id=assessment.campaign_id,
                    agenticity_score=float(merged_behavior_flags.get("agenticity_score", 0.0)),
                    agenticity_classification=str(
                        merged_behavior_flags.get("agenticity_classification", "HIGH")
                    ),
                )
                maze_id = maze_state.maze_id
                maze_surface = maze_svc.get_surface_nodes(request.session_id)
                await deception_authority.record_execution_outcome(
                    case=case,
                    status="ready",
                    note="mirror-world maze activated",
                    output_class="synthetic_graph_state",
                    extra={
                        "maze_id": maze_id,
                        "surface_nodes": len(maze_state.root_node_ids),
                        "maze_tier": maze_state.tier.value,
                    },
                )
            else:
                merged_behavior_flags["deception_downgraded"] = True
                assessment.reasons = list(dict.fromkeys(list(assessment.reasons or []) + case_validation.reasons))

            # World-event for maze activation
            if maze_id and soar_enabled and emit_world_event is not None:
                import asyncio
                asyncio.ensure_future(emit_world_event(
                    db=None,
                    event_type="ai_adversary_maze_activated",
                    entity_refs=[request.session_id, assessment.campaign_id or ""],
                    payload={
                        "deception_case_id": deception_case_id,
                        "maze_id": maze_id,
                        "session_id": request.session_id,
                        "campaign_id": assessment.campaign_id,
                        "agenticity_score": float(merged_behavior_flags.get("agenticity_score", 0.0)),
                        "tier": maze_state.tier.value,
                        "surface_nodes": len(maze_state.root_node_ids),
                    },
                    source="mystique_maze",
                ))
        except Exception as exc:
            logger.warning(f"Mystique maze activation failed: {exc}")

    return RiskAssessmentResponse(
        score=assessment.score,
        reasons=assessment.reasons,
        route=assessment.route.value,
        delay_ms=assessment.delay_ms,
        campaign_id=assessment.campaign_id,
        fingerprint_id=assessment.fingerprint_id,
        escalation_level=assessment.escalation_level.value,
        maze_id=maze_id,
        maze_surface_nodes=maze_surface,
        disinformation_payload=disinfo_payload,
        machine_plausibility=float(merged_behavior_flags.get("machine_plausibility", 0.0)) or None,
        aatl_actor_type=merged_behavior_flags.get("aatl_actor_type"),
        aatl_indicators=list(merged_behavior_flags.get("aatl_indicators") or []),
        agenticity_score=float(merged_behavior_flags.get("agenticity_score", 0.0)) or None,
        deception_case_id=deception_case_id,
    )


@router.post("/assess/batch")
async def assess_risk_batch(requests: List[RiskAssessmentRequest]):
    """Batch risk assessment for multiple requests"""
    results = []
    for req in requests[:100]:  # Limit to 100
        assessment = await deception_engine.process_request(
            ip=req.ip,
            path=req.path,
            headers=req.headers,
            session_id=req.session_id,
            timing_data=req.timing_data,
            behavior_flags=req.behavior_flags
        )
        results.append({
            "ip": req.ip,
            "score": assessment.score,
            "route": assessment.route.value,
            "campaign_id": assessment.campaign_id
        })
    
    return {"assessments": results, "count": len(results)}


# =============================================================================
# DECOY INTERACTIONS
# =============================================================================

@router.post("/decoy/interaction")
async def record_decoy_interaction(request: DecoyInteractionRequest, db=Depends(get_db)):
    """
    Record interaction with a decoy/honey token.
    Triggers immediate escalation.
    """
    assessment = await deception_engine.record_decoy_interaction(
        ip=request.ip,
        decoy_type=request.decoy_type,
        decoy_id=request.decoy_id,
        session_id=request.session_id,
        headers=request.headers
    )
    authority = DeceptionAuthorityService(db)
    case, _ = await authority.create_case(
        session_id=request.session_id,
        campaign_id=assessment.campaign_id,
        source_ip=request.ip,
        path=f"/deception/decoy/{request.decoy_type}/{request.decoy_id}",
        trigger_reason="decoy_interaction",
        triggering_signals=["decoy_touched", f"decoy_type:{request.decoy_type}"],
        desired_mode=DeceptionMode.TRAP_SINK,
        risk_score=assessment.score,
        headers=request.headers,
        behavior_flags={
            "decoy_touched": True,
            "machine_plausibility": 0.9,
            "agenticity_score": 0.9,
        },
        evidence_refs=[request.decoy_id],
    )
    event_id = await authority.persist_event(
        deception_case_id=case.deception_case_id,
        event_type="decoy_interaction",
        session_id=request.session_id,
        campaign_id=assessment.campaign_id,
        source_ip=request.ip,
        details={
            "decoy_type": request.decoy_type,
            "decoy_id": request.decoy_id,
            "route": assessment.route.value,
            "escalation_level": assessment.escalation_level.value,
            "risk_score": assessment.score,
        },
    )
    await authority.record_execution_outcome(
        case=case,
        status="engaged",
        note="direct decoy interaction recorded",
        output_class="event_capture",
        extra={
            "event_id": event_id,
            "campaign_id": assessment.campaign_id,
            "escalation_level": assessment.escalation_level.value,
        },
    )
    
    return {
        "recorded": True,
        "score": assessment.score,
        "route": assessment.route.value,
        "campaign_id": assessment.campaign_id,
        "escalation_level": assessment.escalation_level.value,
        "deception_case_id": case.deception_case_id,
        "event_id": event_id,
    }


@router.post("/decoy/deploy")
async def deploy_decoy(request: DeployDecoyRequest, current_user: dict = Depends(get_current_user)):
    """Deploy decoys using the AI defense engine for Deception page quick actions."""
    from threat_response import AIDefenseEngine
    from dataclasses import asdict

    result = await AIDefenseEngine.deploy_decoy(
        host_id=request.host_id,
        decoy_type=request.decoy_type,
        decoys=request.decoys,
        placement=request.placement,
    )

    payload = asdict(result)
    payload["requested_by"] = current_user.get("email", "unknown")
    return payload


# =============================================================================
# CAMPAIGNS
# =============================================================================

@router.get("/campaigns")
async def get_campaigns(min_events: int = 5, limit: int = 50):
    """Get active attack campaigns"""
    def _normalize_campaign(c: Dict[str, Any]) -> Dict[str, Any]:
        details = c.get("details") if isinstance(c, dict) else {}
        details = details if isinstance(details, dict) else {}
        return {
            "id": c.get("id") or c.get("campaign_id") or details.get("campaign_id"),
            "name": c.get("name") or c.get("label") or c.get("campaign_name") or "campaign",
            "first_seen": c.get("first_seen") or c.get("created_at") or c.get("timestamp"),
            "last_seen": c.get("last_seen") or c.get("updated_at") or c.get("timestamp"),
            "event_count": int(c.get("event_count") or c.get("events") or details.get("event_count") or 0),
            "unique_ips": int(c.get("unique_ips") or details.get("unique_ips") or 0),
            "fingerprint_id": c.get("fingerprint_id") or details.get("fingerprint_id"),
            "escalation_level": c.get("escalation_level") or details.get("escalation_level") or "none",
            "routes": c.get("routes") or details.get("routes") or [],
        }

    campaigns_raw = deception_engine.get_campaigns(min_events=min_events, limit=limit)
    campaigns = [_normalize_campaign(c) for c in (campaigns_raw or []) if isinstance(c, dict)]
    campaigns = [c for c in campaigns if c.get("id")]

    # If the engine has no events yet, synthesize campaigns from recent threats so the UI isn't blank.
    if not campaigns:
        db = get_db()
        if db is not None:
            threats = await db.threats.find(
                {"source_ip": {"$exists": True}, "target_system": {"$exists": True}},
                {"_id": 0, "source_ip": 1, "severity": 1, "created_at": 1},
            ).sort("created_at", -1).limit(250).to_list(250)
            by_ip: Dict[str, Dict[str, Any]] = {}
            for t in threats:
                ip = str(t.get("source_ip") or "").strip()
                if not ip:
                    continue
                bucket = by_ip.setdefault(
                    ip,
                    {
                        "id": f"synthetic:{ip}",
                        "name": f"Synthetic Campaign ({ip})",
                        "first_seen": t.get("created_at"),
                        "last_seen": t.get("created_at"),
                        "event_count": 0,
                        "unique_ips": 1,
                        "fingerprint_id": f"fp:{ip}",
                        "routes": [],
                        "escalation_level": "none",
                    },
                )
                bucket["event_count"] += 1
                ts = t.get("created_at")
                if ts:
                    bucket["first_seen"] = min(bucket["first_seen"], ts) if bucket["first_seen"] else ts
                    bucket["last_seen"] = max(bucket["last_seen"], ts) if bucket["last_seen"] else ts
                sev = str(t.get("severity") or "medium").lower()
                if sev == "critical":
                    bucket["escalation_level"] = "hard_ban"
                elif sev == "high" and bucket["escalation_level"] != "hard_ban":
                    bucket["escalation_level"] = "soft_ban"
                route = "trap_sink" if sev in {"critical", "high"} else "friction"
                if route not in bucket["routes"]:
                    bucket["routes"].append(route)
            campaigns = list(by_ip.values())[:limit]

    return {
        "campaigns": campaigns,
        "count": len(campaigns)
    }


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str):
    """Get specific campaign details"""
    campaign = deception_engine.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.get("/campaigns/{campaign_id}/events")
async def get_campaign_events(campaign_id: str, limit: int = 100):
    """Get events for a specific campaign"""
    events = deception_engine.get_events(limit=limit, campaign_id=campaign_id)
    return {"events": events, "count": len(events)}


# =============================================================================
# EVENTS
# =============================================================================

@router.get("/events")
async def get_events(
    limit: int = 100,
    route_filter: Optional[str] = None,
    campaign_id: Optional[str] = None
):
    """Get recent deception events with optional filtering"""
    def _normalize_event(e: Dict[str, Any]) -> Dict[str, Any]:
        details = e.get("details") if isinstance(e, dict) else {}
        details = details if isinstance(details, dict) else {}
        return {
            "id": e.get("id") or e.get("event_id") or details.get("event_id"),
            "ip": e.get("ip") or e.get("source_ip") or details.get("ip"),
            "path": e.get("path") or e.get("request_path") or details.get("path") or "/",
            "score": int(e.get("score") or details.get("score") or 0),
            "route": e.get("route") or e.get("route_decision") or details.get("route") or "pass_through",
            "escalation_level": e.get("escalation_level") or details.get("escalation") or "none",
            "campaign_id": e.get("campaign_id") or details.get("campaign_id"),
            "timestamp": e.get("timestamp") or e.get("created_at") or details.get("timestamp"),
            "decoy_triggered": bool(e.get("decoy_triggered") or details.get("decoy_triggered") or False),
        }

    events_raw = deception_engine.get_events(
        limit=min(limit, 1000),
        route_filter=route_filter,
        campaign_id=campaign_id
    )
    events = [_normalize_event(e) for e in (events_raw or []) if isinstance(e, dict)]
    events = [e for e in events if e.get("id") and e.get("ip")]

    if not events:
        db = get_db()
        if db is not None:
            threats = await db.threats.find(
                {"source_ip": {"$exists": True}, "target_system": {"$exists": True}},
                {"_id": 0, "id": 1, "source_ip": 1, "target_system": 1, "type": 1, "severity": 1, "created_at": 1},
            ).sort("created_at", -1).limit(min(300, int(limit) * 3)).to_list(min(300, int(limit) * 3))
            synthetic = []
            for t in threats:
                ip = str(t.get("source_ip") or "").strip()
                target = str(t.get("target_system") or "").strip()
                if not ip:
                    continue
                sev = str(t.get("severity") or "medium").lower()
                route = "trap_sink" if sev in {"critical", "high"} else "friction"
                escalation = "hard_ban" if sev == "critical" else ("soft_ban" if sev == "high" else "none")
                synthetic.append(
                    {
                        "id": t.get("id") or f"synthetic:{ip}:{target}:{t.get('created_at')}",
                        "ip": ip,
                        "path": f"/threat/{t.get('type') or 'signal'}",
                        "score": 40 + int(_severity_to_risk(sev) / 2),
                        "route": route,
                        "escalation_level": escalation,
                        "campaign_id": f"synthetic:{ip}",
                        "timestamp": t.get("created_at"),
                        "decoy_triggered": False,
                    }
                )
            events = synthetic[: int(limit)]

    return {"events": events, "count": len(events)}


@router.get("/events/summary")
async def get_events_summary():
    """Get summary of recent events by type"""
    events = deception_engine.get_events(limit=1000)
    
    summary = {
        "total": len(events),
        "by_route": {},
        "by_escalation": {},
        "unique_ips": set(),
        "unique_campaigns": set()
    }
    
    for event in events:
        route = event.get("route_decision", "unknown")
        summary["by_route"][route] = summary["by_route"].get(route, 0) + 1
        
        escalation = event.get("details", {}).get("escalation", "none")
        summary["by_escalation"][escalation] = summary["by_escalation"].get(escalation, 0) + 1
        
        summary["unique_ips"].add(event.get("source_ip"))
        if event.get("campaign_id"):
            summary["unique_campaigns"].add(event["campaign_id"])
    
    summary["unique_ips"] = len(summary["unique_ips"])
    summary["unique_campaigns"] = len(summary["unique_campaigns"])
    
    return summary


# =============================================================================
# BLOCKLIST/ALLOWLIST
# =============================================================================

@router.post("/allowlist/add")
async def add_to_allowlist(request: IPRequest):
    """Add IP to allowlist"""
    success = deception_engine.add_to_allowlist(request.ip)
    return {"success": success, "ip": request.ip, "action": "allowlisted"}


@router.post("/blocklist/add")
async def add_to_blocklist(request: IPRequest):
    """Add IP to blocklist"""
    success = deception_engine.add_to_blocklist(request.ip)
    return {"success": success, "ip": request.ip, "action": "blocklisted"}


@router.post("/blocklist/remove")
async def remove_from_blocklist(request: IPRequest):
    """Remove IP from blocklist"""
    success = deception_engine.remove_from_blocklist(request.ip)
    return {"success": success, "ip": request.ip, "action": "unblocked"}


@router.get("/blocklist")
async def get_blocklist():
    """Get current blocklist"""
    return {
        "blocklist": list(deception_engine.blocklist),
        "allowlist": list(deception_engine.allowlist),
        "soft_bans": len(deception_engine.soft_bans)
    }


# =============================================================================
# FINGERPRINTS
# =============================================================================

@router.get("/fingerprints")
async def get_fingerprints(min_events: int = 3, limit: int = 100):
    """Get behavioral fingerprints"""
    fingerprints = [
        fp.to_dict() for fp in deception_engine.fingerprints.values()
        if fp.total_events >= min_events
    ]
    fingerprints.sort(key=lambda x: x["total_events"], reverse=True)
    
    return {
        "fingerprints": fingerprints[:limit],
        "total": len(fingerprints)
    }


@router.get("/fingerprints/{fingerprint_id}")
async def get_fingerprint(fingerprint_id: str):
    """Get specific fingerprint details"""
    if fingerprint_id not in deception_engine.fingerprints:
        raise HTTPException(status_code=404, detail="Fingerprint not found")
    
    fp = deception_engine.fingerprints[fingerprint_id]
    
    # Find campaigns for this fingerprint
    campaigns = [
        c.to_dict() for c in deception_engine.campaigns.values()
        if fingerprint_id in c.fingerprint_ids
    ]
    
    return {
        "fingerprint": fp.to_dict(),
        "campaigns": campaigns
    }


# =============================================================================
# MYSTIQUE TUNING
# =============================================================================

@router.post("/mystique/force-adapt/{campaign_id}")
async def force_mystique_adapt(campaign_id: str):
    """Force Mystique adaptation for a campaign"""
    if campaign_id not in deception_engine.campaigns:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Temporarily increase events to trigger adaptation
    campaign = deception_engine.campaigns[campaign_id]
    original_events = campaign.total_events
    
    # Force adaptation
    campaign.total_events = max(campaign.total_events, 
                                deception_engine.config.campaign_promote_threshold + 1)
    campaign.total_events = (
        (campaign.total_events // deception_engine.config.adapt_every_n_events + 1) 
        * deception_engine.config.adapt_every_n_events
    )
    
    adapted = deception_engine.mystique_adapt(campaign_id)
    
    return {
        "adapted": adapted,
        "campaign_id": campaign_id,
        "friction_multiplier": campaign.friction_multiplier,
        "tarpit_multiplier": campaign.tarpit_multiplier,
        "sink_score_override": campaign.sink_score_override
    }


@router.get("/mystique/config")
async def get_mystique_config():
    """Get Mystique configuration"""
    cfg = deception_engine.config
    return {
        "enabled": cfg.mystique_enabled,
        "adapt_every_n_events": cfg.adapt_every_n_events,
        "campaign_promote_threshold": cfg.campaign_promote_threshold,
        "max_friction_multiplier": cfg.max_friction_multiplier,
        "max_tarpit_multiplier": cfg.max_tarpit_multiplier,
        "min_sink_score_floor": cfg.min_sink_score_floor
    }


# =============================================================================
# STONEWALL CONFIG
# =============================================================================

@router.get("/stonewall/config")
async def get_stonewall_config():
    """Get Stonewall configuration"""
    cfg = deception_engine.config
    return {
        "enabled": cfg.stonewall_enabled,
        "repeat_threshold": cfg.repeat_threshold,
        "ban_seconds_first": cfg.ban_seconds_first,
        "ban_seconds_repeat": cfg.ban_seconds_repeat,
        "trap_hits_to_blocklist": cfg.trap_hits_to_blocklist
    }


# =============================================================================
# ANALYTICS
# =============================================================================

@router.get("/analytics/threat-heatmap")
async def get_threat_heatmap():
    """Get threat data for heatmap visualization"""
    campaigns = deception_engine.get_campaigns(min_events=1, limit=500)
    
    heatmap = []
    for campaign in campaigns:
        for ip in campaign.get("source_ips", []):
            heatmap.append({
                "ip": ip,
                "campaign_id": campaign["campaign_id"],
                "total_events": campaign["total_events"],
                "trap_events": campaign["trap_events"],
                "escalation_level": campaign.get("escalation_level", "none"),
                "risk_indicator": campaign.get("friction_multiplier", 1.0)
            })
    
    return {"data": heatmap, "count": len(heatmap)}


@router.get("/analytics/campaigns-timeline")
async def get_campaigns_timeline(hours: int = 24):
    """Get campaign activity timeline"""
    events = deception_engine.get_events(limit=5000)
    
    # Group by hour
    timeline = {}
    for event in events:
        ts = event.get("timestamp", "")[:13]  # YYYY-MM-DDTHH
        if ts not in timeline:
            timeline[ts] = {"trap_sink": 0, "friction": 0, "pass": 0}
        
        route = event.get("route_decision", "pass_through")
        if route == "trap_sink":
            timeline[ts]["trap_sink"] += 1
        elif route == "friction":
            timeline[ts]["friction"] += 1
        else:
            timeline[ts]["pass"] += 1
    
    # Convert to sorted list
    sorted_timeline = [
        {"hour": k, **v} for k, v in sorted(timeline.items())
    ]
    
    return {"timeline": sorted_timeline[-hours:], "hours": hours}


@router.get("/analytics/effectiveness")
async def get_deception_effectiveness(
    limit: int = 200,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return persisted deception effectiveness metrics and case outcomes."""
    if db is None or not hasattr(db, "deception_cases"):
        return {
            "summary": {
                "total_cases": 0,
                "measured_cases": 0,
                "outcome_counts": {},
                "mode_counts": {},
            },
            "cases": [],
            "note": "Database persistence not available",
        }

    case_docs = await db.deception_cases.find({}, {"_id": 0}).sort("updated_at", -1).limit(limit).to_list(limit)
    serve_docs = []
    event_docs = []
    if hasattr(db, "disinformation_serves"):
        serve_docs = await db.disinformation_serves.find({}, {"_id": 0}).to_list(5000)
    if hasattr(db, "deception_events"):
        event_docs = await db.deception_events.find({}, {"_id": 0}).to_list(10000)

    serves_by_case: Dict[str, List[Dict[str, Any]]] = {}
    for serve in serve_docs:
        case_id = str(serve.get("deception_case_id") or "")
        if case_id:
            serves_by_case.setdefault(case_id, []).append(serve)

    events_by_case: Dict[str, List[Dict[str, Any]]] = {}
    for event in event_docs:
        case_id = str(event.get("deception_case_id") or "")
        if case_id:
            events_by_case.setdefault(case_id, []).append(event)

    case_summaries: List[Dict[str, Any]] = []
    outcome_counts: Counter[str] = Counter()
    mode_counts: Counter[str] = Counter()
    false_positive_cases = 0
    disengaged_cases = 0
    total_dwell_extension_seconds = 0.0
    dwell_extension_cases = 0
    successful_cases = 0
    success_by_mode: Counter[str] = Counter()

    for doc in case_docs:
        case_id = str(doc.get("deception_case_id"))
        mode = str(doc.get("deception_mode") or "unknown")
        mode_counts[mode] += 1
        case_events = events_by_case.get(case_id, [])
        case_serves = serves_by_case.get(case_id, [])
        effectiveness = summarize_effectiveness_case(doc, case_events, case_serves)
        outcome = effectiveness["outcome"]
        mode_success = bool(effectiveness["mode_success"])
        success_criterion = str(effectiveness["success_criterion"])
        metrics = effectiveness["metrics"]

        outcome_counts[outcome] += 1
        if mode_success:
            successful_cases += 1
            success_by_mode[mode] += 1
        if metrics["false_positive_engagement_suspected"]:
            false_positive_cases += 1
        if metrics["disengagement_detected"]:
            disengaged_cases += 1
        if metrics["dwell_time_extension_seconds"] > 0:
            total_dwell_extension_seconds += float(metrics["dwell_time_extension_seconds"])
            dwell_extension_cases += 1

        case_summaries.append(
            {
                "deception_case_id": case_id,
                "mode": mode,
                "status": doc.get("status"),
                "campaign_id": doc.get("campaign_id"),
                "session_id": doc.get("subject_session_id"),
                "risk_band": doc.get("risk_band"),
                "confidence_band": doc.get("confidence_band"),
                "outcome": outcome,
                "mode_success": mode_success,
                "success_criterion": success_criterion,
                "metrics": metrics,
            }
        )

    return {
        "summary": {
            "total_cases": len(case_summaries),
            "measured_cases": sum(1 for case in case_summaries if case["outcome"] != "creative_unmeasured"),
            "outcome_counts": dict(outcome_counts),
            "mode_counts": dict(mode_counts),
            "avg_dwell_time_extension_seconds": round(
                total_dwell_extension_seconds / max(dwell_extension_cases, 1), 6
            )
            if dwell_extension_cases
            else 0.0,
            "disengagement_rate": round(disengaged_cases / max(len(case_summaries), 1), 6)
            if case_summaries
            else 0.0,
            "false_positive_engagement_rate": round(false_positive_cases / max(len(case_summaries), 1), 6)
            if case_summaries
            else 0.0,
            "overall_success_rate": round(successful_cases / max(len(case_summaries), 1), 6)
            if case_summaries
            else 0.0,
            "success_by_mode": dict(success_by_mode),
        },
        "cases": case_summaries,
    }


# =============================================================================
# DISINFORMATION ENGINE
# =============================================================================

@router.get("/disinformation/history")
async def get_disinformation_history(
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
):
    """Return recent DISINFORMATION route activations (poisoned responses served)."""
    if get_disinfo_engine is None:
        return {"error": "Disinformation engine unavailable", "history": []}
    try:
        history = get_disinfo_engine().get_history(limit=limit)
        return {"count": len(history), "history": history}
    except Exception as exc:
        logger.error(f"Failed to retrieve disinformation history: {exc}")
        return {"error": str(exc), "history": []}


@router.get("/disinformation/stats")
async def get_disinformation_stats(current_user: dict = Depends(get_current_user)):
    """Return aggregate statistics for the disinformation engine."""
    if get_disinfo_engine is None:
        return {"error": "Disinformation engine unavailable"}
    try:
        return get_disinfo_engine().get_stats()
    except Exception as exc:
        logger.error(f"Failed to retrieve disinformation stats: {exc}")
        return {"error": str(exc)}


# =============================================================================
# MYSTIQUE MIRROR WORLD MAZE
# =============================================================================

class MazeProbeRequest(BaseModel):
    session_id: str
    node_id: str
    agenticity_score: float = 0.0
    cbr: float = 0.0
    tbcr: float = 0.0


@router.get("/maze/active")
async def list_active_mazes(current_user: dict = Depends(get_current_user)):
    """
    List all currently active mirror-world maze sessions with collected
    adversary intelligence.
    """
    if get_mystique_maze is None:
        raise HTTPException(status_code=503, detail="Maze service unavailable")
    maze_svc = get_mystique_maze()
    return {
        "mazes": maze_svc.list_active_mazes(),
        "total": len(maze_svc.list_active_mazes()),
    }


@router.get("/maze/{session_id}/surface")
async def get_maze_surface(session_id: str, current_user: dict = Depends(get_current_user)):
    """
    Return the surface-level (entry) nodes of a session's mirror world.
    Used by defenders to see what lures are currently presented to an adversary.
    """
    if get_mystique_maze is None:
        raise HTTPException(status_code=503, detail="Maze service unavailable")
    maze_svc = get_mystique_maze()
    telemetry = maze_svc.get_maze_telemetry(session_id)
    if telemetry is None:
        raise HTTPException(status_code=404, detail="No maze for this session")
    return {
        "session_id": session_id,
        "telemetry": telemetry,
        "surface_nodes": maze_svc.get_surface_nodes(session_id),
    }


@router.post("/maze/probe")
async def maze_probe(request: MazeProbeRequest, db=Depends(get_db)):
    """
    Simulate an adversary probing a maze node.
    Returns the fabricated payload + list of newly spawned child nodes.

    In a live deployment this endpoint is called transparently by Seraph when
    an AI adversary session interacts with a resource that has been replaced
    by the mirror world. The adversary sees a realistic response; Seraph
    collects intent telemetry.
    """
    if get_mystique_maze is None:
        raise HTTPException(status_code=503, detail="Maze service unavailable")
    maze_svc = get_mystique_maze()
    maze_svc.set_persistence(db)

    if maze_svc.get_maze_telemetry(request.session_id) is None:
        raise HTTPException(status_code=404, detail="No maze for this session — call /assess first")

    payload, new_node_ids = await maze_svc.probe_node(
        session_id=request.session_id,
        node_id=request.node_id,
        agenticity_score=request.agenticity_score,
        cbr=request.cbr,
        tbcr=request.tbcr,
    )

    # Emit world event for each maze traversal step
    if emit_world_event is not None:
        try:
            import asyncio
            telemetry = maze_svc.get_maze_telemetry(request.session_id) or {}
            asyncio.ensure_future(emit_world_event(
                db=None,
                event_type="ai_adversary_maze_traversal",
                entity_refs=[request.session_id, request.node_id],
                payload={
                    "session_id": request.session_id,
                    "node_id": request.node_id,
                    "new_nodes_spawned": len(new_node_ids),
                    "inferred_intent": telemetry.get("inferred_intent"),
                    "tier": telemetry.get("tier"),
                    "total_probes": telemetry.get("total_probes"),
                    "total_bytes_consumed": telemetry.get("total_bytes_consumed"),
                    "agenticity_score": request.agenticity_score,
                },
                source="mystique_maze",
            ))
        except Exception:
            pass

    authority = DeceptionAuthorityService(db)
    linked_case = None
    if hasattr(db, "deception_cases"):
        linked_cases = await db.deception_cases.find(
            {
                "subject_session_id": request.session_id,
                "deception_mode": DeceptionMode.MIRROR_WORLD.value,
            },
            {"_id": 0},
        ).sort("updated_at", -1).to_list(1)
        linked_case = linked_cases[0] if linked_cases else None
    event_id = None
    if linked_case:
        telemetry_snapshot = maze_svc.get_maze_telemetry(request.session_id) or {}
        event_id = await authority.persist_event(
            deception_case_id=linked_case["deception_case_id"],
            event_type="maze_traversal",
            session_id=request.session_id,
            campaign_id=telemetry_snapshot.get("campaign_id"),
            details={
                "node_id": request.node_id,
                "new_nodes_spawned": len(new_node_ids),
                "agenticity_score": request.agenticity_score,
                "cbr": request.cbr,
                "tbcr": request.tbcr,
                "tier": telemetry_snapshot.get("tier"),
                "inferred_intent": telemetry_snapshot.get("inferred_intent"),
                "total_probes": telemetry_snapshot.get("total_probes"),
                "total_bytes_consumed": telemetry_snapshot.get("total_bytes_consumed"),
            },
        )
        case_model = DeceptionCase(**linked_case)
        await authority.record_execution_outcome(
            case=case_model,
            status="engaged",
            note="maze traversal recorded",
            output_class="synthetic_graph_state",
            extra={"event_id": event_id},
        )

    return {
        "node_id": request.node_id,
        "payload": payload,
        "new_node_ids": new_node_ids,
        "telemetry_snapshot": maze_svc.get_maze_telemetry(request.session_id),
        "event_id": event_id,
    }


@router.get("/maze/{session_id}/telemetry")
async def get_maze_telemetry(session_id: str, current_user: dict = Depends(get_current_user)):
    """
    Return full adversary intelligence collected from a mirror-world maze session.
    Shows inferred intent, observed TTPs, reasoning budget burned, and probe history.
    """
    if get_mystique_maze is None:
        raise HTTPException(status_code=503, detail="Maze service unavailable")
    maze_svc = get_mystique_maze()
    telemetry = maze_svc.get_maze_telemetry(session_id)
    if telemetry is None:
        raise HTTPException(status_code=404, detail="No maze for this session")
    return telemetry


# =============================================================================
# EXPLAINABILITY ENDPOINTS
# =============================================================================

@router.get("/explain/{session_id}")
async def explain_session_decision(session_id: str, db=Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Explain why a session received its route decision.
    
    Returns comprehensive analysis including:
    - Risk assessment breakdown
    - Agenticity score components  
    - Maze telemetry (if applicable)
    - Campaign correlation
    - Decision confidence factors
    """
    try:
        # Get deception engine analysis
        session_analysis = deception_engine.get_session_analysis(session_id)
        if not session_analysis:
            raise HTTPException(status_code=404, detail="Session not found in deception engine")
        
        explanation = {
            "session_id": session_id,
            "decision": session_analysis.get("route_decision"),
            "confidence": session_analysis.get("confidence", 0),
            "timestamp": session_analysis.get("last_updated"),
            "campaign_id": session_analysis.get("campaign_id"),
        }
        
        # Add risk assessment breakdown
        risk_assessment = session_analysis.get("risk_assessment", {})
        explanation["risk_breakdown"] = {
            "score": risk_assessment.get("score", 0),
            "reasons": risk_assessment.get("reasons", []),
            "behavior_flags": risk_assessment.get("behavior_flags", {}),
        }
        
        # Add agenticity analysis if available
        try:
            from backend.services.agenticity import get_agenticity_persistence
            agenticity_persist = get_agenticity_persistence(db)
            if agenticity_persist:
                session_summary = await agenticity_persist.get_session_summary(session_id)
                if session_summary.get("latest_score"):
                    explanation["agenticity"] = {
                        "score": session_summary["latest_score"]["score"],
                        "classification": session_summary["latest_score"]["classification"],
                        "feature_vector": session_summary["latest_score"]["feature_vector"],
                        "weights": session_summary["latest_score"]["weights"],
                        "weighted_components": session_summary["latest_score"]["weighted_components"],
                        "generated_at": session_summary["latest_score"]["generated_at"],
                    }
                if session_summary.get("latest_exhaustion"):
                    explanation["exhaustion_metrics"] = session_summary["latest_exhaustion"]
        except Exception as e:
            explanation["agenticity_error"] = str(e)
        
        # Add maze analysis if applicable
        if get_mystique_maze is not None:
            try:
                maze_svc = get_mystique_maze()
                maze_telemetry = maze_svc.get_maze_telemetry(session_id)
                if maze_telemetry:
                    explanation["maze_analysis"] = {
                        "maze_id": maze_telemetry["maze_id"],
                        "tier": maze_telemetry["tier"],
                        "inferred_intent": maze_telemetry["inferred_intent"],
                        "total_probes": maze_telemetry["total_probes"],
                        "total_bytes_consumed": maze_telemetry["total_bytes_consumed"],
                        "observed_ttps": maze_telemetry["observed_ttps"],
                        "nodes_total": maze_telemetry["nodes_total"],
                        "nodes_accessed": maze_telemetry["nodes_accessed"],
                    }
            except Exception as e:
                explanation["maze_error"] = str(e)
        
        # Add campaign context
        campaign_id = session_analysis.get("campaign_id")
        if campaign_id:
            campaign_stats = deception_engine.get_campaign_stats(campaign_id)
            if campaign_stats:
                explanation["campaign_context"] = {
                    "campaign_id": campaign_id,
                    "total_events": campaign_stats.get("total_events", 0),
                    "unique_sessions": campaign_stats.get("unique_sessions", 0),
                    "risk_trend": campaign_stats.get("risk_trend", []),
                    "last_activity": campaign_stats.get("last_activity"),
                }
        
        # Add decision confidence factors
        explanation["confidence_factors"] = {
            "escalation_level": session_analysis.get("escalation_level"),
            "stonewall_triggers": session_analysis.get("stonewall_triggers", []),
            "mystique_active": session_analysis.get("mystique_active", False),
            "disinformation_eligible": session_analysis.get("disinformation_eligible", False),
        }
        
        return explanation
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Explanation generation failed: {str(e)}")


# =============================================================================
# PERSISTENCE ENDPOINTS
# =============================================================================

@router.get("/maze/sessions")
async def get_maze_sessions(limit: int = 50, db=Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Get list of active maze sessions with persistence."""
    try:
        from backend.services.mystique_maze import get_maze_persistence
        persistence = get_maze_persistence(db)
        if persistence:
            sessions = await persistence.get_maze_sessions(limit)
            return {"sessions": sessions, "count": len(sessions)}
        else:
            return {"sessions": [], "count": 0, "note": "Database persistence not available"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve maze sessions: {str(e)}")


@router.get("/agenticity/sessions/{session_id}")
async def get_agenticity_session_history(session_id: str, limit: int = 10, db=Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Get agenticity score history for a session."""
    try:
        from backend.services.agenticity import get_agenticity_persistence
        persistence = get_agenticity_persistence(db)
        if persistence:
            scores = await persistence.get_score_history(session_id, limit)
            exhaustion = await persistence.get_exhaustion_history(session_id, limit)
            return {
                "session_id": session_id,
                "scores": scores,
                "exhaustion_metrics": exhaustion,
                "score_count": len(scores),
                "exhaustion_count": len(exhaustion),
            }
        else:
            return {"error": "Database persistence not available"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve agenticity history: {str(e)}")


@router.get("/agenticity/sessions/{session_id}/summary")
async def get_agenticity_session_summary(session_id: str, db=Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Get comprehensive agenticity session summary."""
    try:
        from backend.services.agenticity import get_agenticity_persistence
        persistence = get_agenticity_persistence(db)
        if persistence:
            summary = await persistence.get_session_summary(session_id)
            return summary
        else:
            return {"error": "Database persistence not available"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve session summary: {str(e)}")
