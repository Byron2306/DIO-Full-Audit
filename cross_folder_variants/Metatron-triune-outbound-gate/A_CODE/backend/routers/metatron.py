from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List, Dict, Any, Set
import asyncio
from routers.dependencies import get_db
from backend.services.world_model import WorldModelService
from backend.services.governance_epoch import get_governance_epoch_service
try:
    from backend.schemas.triune_models import MetatronState
except Exception:
    MetatronState = None

from backend.services.vns import vns

router = APIRouter()

try:
    from bson import ObjectId  # type: ignore
except Exception:  # pragma: no cover
    ObjectId = None


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if ObjectId is not None and isinstance(value, ObjectId):
        return str(value)
    return value

@router.get("/metatron/hello")
async def hello():
    return {"msg": "Metatron router active"}

@router.get("/metatron/entities/count")
async def entity_count(db=Depends(get_db)):
    """Return number of world-model entities (for smoke test)."""
    wm = WorldModelService(db)
    if not hasattr(wm, "entities") or wm.entities is None:
        # database not configured (e.g. during unit tests)
        return {"entity_count": 0}
    c = await wm.entities.count_documents({})
    return {"entity_count": c}

@router.get("/metatron/summary")
async def summary(db=Depends(get_db)):
    """Return a top-level world view summary (entity counts, campaigns)."""
    wm = WorldModelService(db)
    entity_count = 0
    campaigns = []
    if hasattr(wm, "entities") and wm.entities is not None:
        entity_count = await wm.entities.count_documents({})
    if hasattr(wm, "campaigns") and wm.campaigns is not None:
        cursor = wm.campaigns.find({}, {"_id": 0})
        campaigns = [c async for c in cursor]
    result: dict = {
        "entities": entity_count,
        "total_entities": entity_count,
        "entity_count": entity_count,
        "campaigns": campaigns,
        "active_campaigns": len(campaigns),
    }
    return _json_safe(result)


@router.get(
    "/metatron/state",
    responses={
        200: {
            "description": "Metatron state with triune analysis hints",
            "content": {
                "application/json": {
                    "example": {
                        "header": {"risk_level": "elevated", "active_campaigns": 1, "ml_confidence": 0.82},
                        "narrative": {"campaign_id": "camp-42", "objective": "exfiltrate-data"},
                        "attack_path": {"nodes": [{"id": "host1"}], "edges": [{"source": "host1", "target": "db1"}]},
                        "trust": {"identity": "degraded", "device": "compromised"},
                        "hotspots": [{"id": "host1", "risk": 0.92, "reason": "multiple suspicious processes"}],
                        "actions": [{"suggested": "isolate:host1", "reversibility": "manual"}],
                        "hypotheses": [
                            {"analysis_id": "a1", "candidate": "isolate:host1", "score": 0.92, "components": {"keyword": 0.9, "risk": 0.8, "ai": {"provider": "ollama", "explanation": "Isolation recommended due to high risk signals and active exfiltration indicators."}}}
                        ],
                        "timeline": [{"ts": "2026-03-11T10:00:00Z", "event": "suspicious_process_detected", "entity": "host1"}],
                        "triune_analyses": [
                            {
                                "id": "a1",
                                "created": "2026-03-11T10:01:00Z",
                                "entities": ["host1"],
                                "candidates": ["isolate:host1", "monitor:host1"],
                                "ranked": [
                                    {"candidate": "isolate:host1", "score": 0.92, "components": {"keyword": 0.9, "risk": 0.8, "recency": 0.95, "ai": {"provider": "ollama", "explanation": "Evidence of data exfiltration and high-risk behaviors; isolation minimizes blast radius to critical services."}}},
                                    {"candidate": "monitor:host1", "score": 0.45, "components": {"keyword": 0.2, "risk": 0.3, "ai": {"provider": "ollama", "explanation": "Monitoring preserves evidence but risks ongoing exfiltration."}}}
                                ]
                            }
                        ]
                    }
                }
            },
        }
    },
)
async def state(db=Depends(get_db), lite: bool = True):
    """Return comprehensive metatron world-state for UI consumption."""
    # Lite mode is the default because full world-model computations can be
    # CPU-heavy and block the event loop (making the UI feel "down").
    if lite:
        now_utc = datetime.now(timezone.utc)
        agent_entities: List[Dict[str, Any]] = []
        online_agents = 0
        threat_agents = 0
        relationships: List[Dict[str, Any]] = []
        actions: List[Dict[str, Any]] = []
        hypotheses: List[Dict[str, Any]] = []

        try:
            docs = await asyncio.wait_for(
                db.unified_agents.find(
                    {},
                    {"_id": 0, "agent_id": 1, "hostname": 1, "platform": 1, "status": 1, "last_heartbeat": 1, "threat_count": 1},
                ).limit(200).to_list(200),
                timeout=1.2,
            )
        except Exception:
            docs = []

        for a in docs:
            agent_id = a.get("agent_id") or "unknown"
            last_hb = a.get("last_heartbeat")
            try:
                last_hb_dt = datetime.fromisoformat(str(last_hb).replace("Z", "+00:00")) if last_hb else None
            except Exception:
                last_hb_dt = None
            is_online = bool(last_hb_dt and (now_utc - last_hb_dt) <= timedelta(minutes=5))
            if is_online:
                online_agents += 1
            tc = int(a.get("threat_count") or 0)
            if tc > 0:
                threat_agents += 1
            agent_entities.append(
                {
                    "id": agent_id,
                    "type": "host",
                    "name": a.get("hostname") or agent_id,
                    "attributes": {
                        "hostname": a.get("hostname"),
                        "platform": a.get("platform"),
                        "status": "online" if is_online else "offline",
                        "threat_count": tc,
                        "risk_score": min(1.0, 0.1 + tc * 0.2),
                    },
                }
            )

        # Michael/Loki: derive lightweight recommendations and hypotheses from current threats.
        severity_rank = {"low": 0.2, "medium": 0.45, "high": 0.7, "critical": 0.9}
        try:
            threats = await asyncio.wait_for(
                db.threats.find({}, {"_id": 0, "id": 1, "name": 1, "type": 1, "severity": 1, "status": 1, "source_ip": 1, "target_system": 1, "created_at": 1})
                .sort("created_at", -1)
                .limit(25)
                .to_list(25),
                timeout=1.0,
            )
        except Exception:
            threats = []

        for t in (threats or [])[:10]:
            tid = t.get("id") or t.get("threat_id")
            if not tid:
                continue
            sev = str(t.get("severity") or "medium").lower().strip()
            target = t.get("target_system") or t.get("host") or t.get("hostname")
            source_ip = t.get("source_ip")
            risk = severity_rank.get(sev, 0.4)
            if sev in {"critical", "high"} and (t.get("status") or "").lower() == "active":
                if target:
                    actions.append(
                        {
                            "action": "isolate_host" if sev == "critical" else "investigate_host",
                            "entity_id": str(target),
                            "reason": f"{sev}_threat_active",
                            "score": min(1.0, risk + 0.05),
                            "context": {"threat_id": tid, "threat_name": t.get("name"), "source_ip": source_ip},
                        }
                    )
                if source_ip:
                    actions.append(
                        {
                            "action": "block_ip" if sev == "critical" else "monitor_ip",
                            "entity_id": str(source_ip),
                            "reason": f"{sev}_source_ip",
                            "score": min(1.0, risk),
                            "context": {"threat_id": tid, "threat_name": t.get("name")},
                        }
                    )

            hypotheses.append(
                {
                    "candidate": f"{t.get('type') or 'unknown'} campaign ({sev})",
                    "score": min(1.0, risk),
                    "title": t.get("name") or tid,
                    "context": {"threat_id": tid, "source_ip": source_ip, "target": target},
                }
            )

        # Also incorporate recent alerts so the World View page has Michael/Loki
        # activity even when threats are sparse (common during early onboarding).
        try:
            alerts = await asyncio.wait_for(
                db.alerts.find({}, {"_id": 0, "id": 1, "title": 1, "type": 1, "severity": 1, "status": 1, "message": 1, "created_at": 1})
                .sort("created_at", -1)
                .limit(25)
                .to_list(25),
                timeout=0.9,
            )
        except Exception:
            alerts = []

        for a in (alerts or [])[:10]:
            aid = a.get("id") or a.get("alert_id")
            if not aid:
                continue
            sev = str(a.get("severity") or "medium").lower().strip()
            status = str(a.get("status") or "new").lower().strip()
            risk = severity_rank.get(sev, 0.4)
            entity_id = f"alert:{aid}"

            if sev in {"critical", "high"} and status not in {"resolved", "closed"}:
                actions.append(
                    {
                        "action": "triage_alert" if sev == "high" else "escalate_alert",
                        "entity_id": entity_id,
                        "reason": f"{sev}_alert_{status}",
                        "score": min(1.0, risk + 0.05),
                        "context": {"alert_id": aid, "alert_title": a.get("title"), "alert_type": a.get("type")},
                    }
                )

            hypotheses.append(
                {
                    "candidate": f"{a.get('type') or 'alert'} signal ({sev})",
                    "score": min(1.0, risk),
                    "title": a.get("title") or entity_id,
                    "context": {"alert_id": aid, "status": status},
                }
            )

        # Keep lists small and stable.
        actions.sort(key=lambda a: a.get("score", 0), reverse=True)
        actions = actions[:8]
        hypotheses.sort(key=lambda h: h.get("score", 0), reverse=True)
        hypotheses = hypotheses[:8]

        # If no agents are registered yet, seed the world graph from threats/alerts
        # so the World View page isn't an empty template after a fresh install.
        if not agent_entities:
            try:
                threats = await asyncio.wait_for(
                    db.threats.find({}, {"_id": 0, "id": 1, "name": 1, "type": 1, "severity": 1, "status": 1, "source_ip": 1, "target_system": 1, "created_at": 1})
                    .sort("created_at", -1)
                    .limit(25)
                    .to_list(25),
                    timeout=1.2,
                )
            except Exception:
                threats = []

            threat_entities: List[Dict[str, Any]] = []
            relationship_seed: List[Dict[str, Any]] = []
            for t in threats:
                tid = t.get("id") or t.get("threat_id")
                if not tid:
                    continue
                sev = str(t.get("severity") or "medium").lower().strip()
                threat_entities.append(
                    {
                        "id": f"threat:{tid}",
                        "type": "threat",
                        "name": t.get("name") or tid,
                        "attributes": {
                            "threat_id": tid,
                            "threat_type": t.get("type") or "unknown",
                            "severity": sev,
                            "status": t.get("status") or "active",
                            "risk_score": severity_rank.get(sev, 0.4),
                            "created_at": t.get("created_at"),
                        },
                    }
                )
                target = t.get("target_system")
                if target:
                    host_id = f"host:{target}"
                    relationship_seed.append({"source": f"threat:{tid}", "target": host_id, "relation": "targets", "weight": 1})
                    # Add host entity (lightweight)
                    agent_entities.append(
                        {
                            "id": host_id,
                            "type": "host",
                            "name": target,
                            "attributes": {"hostname": target, "platform": "unknown", "status": "unknown", "threat_count": 1, "risk_score": severity_rank.get(sev, 0.4)},
                        }
                    )
                source_ip = t.get("source_ip")
                if source_ip:
                    ip_id = f"ip:{source_ip}"
                    relationship_seed.append({"source": f"threat:{tid}", "target": ip_id, "relation": "originates_from", "weight": 1})
                    agent_entities.append(
                        {
                            "id": ip_id,
                            "type": "ip",
                            "name": source_ip,
                            "attributes": {"ip": source_ip, "risk_score": severity_rank.get(sev, 0.4)},
                        }
                    )

            # De-duplicate seed entities by id
            seen_ids: Set[str] = set()
            dedup_agents: List[Dict[str, Any]] = []
            for e in agent_entities:
                eid = e.get("id")
                if not eid or eid in seen_ids:
                    continue
                seen_ids.add(eid)
                dedup_agents.append(e)
            agent_entities = dedup_agents

            # Replace agent-derived posture counts with threat-derived ones.
            online_agents = 0
            threat_agents = len(agent_entities)
            docs = []

            # Append threats as nodes.
            agent_entities = [*agent_entities, *threat_entities]
            relationships = relationship_seed

        # Provide a minimal relationship graph so the UI world graph renders links
        # even in lite mode (which intentionally avoids expensive world-model joins).
        fleet_id = "fleet:seraph"
        fleet_entity = {
            "id": fleet_id,
            "type": "fleet",
            "name": "Seraph Fleet",
            "attributes": {
                "status": "online" if online_agents > 0 else "offline",
                "risk_score": 0.2 if threat_agents == 0 else min(1.0, 0.2 + threat_agents * 0.15),
                "online_agents": online_agents,
                "total_agents": len(docs),
            },
        }
        # If relationships were seeded from threats above, preserve them and just
        # attach everything to the fleet root.
        if not relationships:
            relationships = []
        relationships.extend(
            [
                {"source": fleet_id, "target": e.get("id"), "relation": "contains", "weight": 1}
                for e in agent_entities
                if e.get("id")
            ]
        )

        hdr = {
            "risk_level": "moderate" if threat_agents > 0 else "low",
            "active_campaigns": 0,
            "high_risk_identities": 0,
            "critical_hosts": threat_agents,
            "active_containments": 0,
            "deception_interactions": 0,
            "ml_confidence": 0.0,
            "online_agents": online_agents,
            "total_agents": len(docs),
        }

        resp = {
            "header": hdr,
            "narrative": {"campaign_id": None, "stage": None, "objective": None, "origin_host": None, "evidence": [], "confidence": 0.0, "predicted_next": []},
            "attack_path": {"nodes": [fleet_entity, *agent_entities], "edges": relationships},
            "relationships": relationships,
            "trust": {"identity": "stable", "device": "stable", "agent_health": "unknown", "policy_violations": 0, "token_anomalies": 0},
            "hotspots": [],
            "actions": actions,
            "hypotheses": hypotheses,
            "triune_analyses": [],
            "timeline": [],
            "governance_context": {"lite": True},
            "entities": [fleet_entity, *agent_entities],
            "recent_events": [],
            "metatron_summary": (
                f"Seraph monitors {len(agent_entities)} endpoint{'s' if len(agent_entities) != 1 else ''} "
                f"({online_agents} online). Risk posture: {hdr['risk_level']}."
            ),
        }
        return _json_safe(resp)

    wm = WorldModelService(db)
    epoch_service = get_governance_epoch_service(db)
    # This endpoint powers multiple UI pages; keep it fast and fail-open.
    try:
        active_epoch = await asyncio.wait_for(epoch_service.get_active_epoch(scope="global"), timeout=1.5)
    except Exception:
        active_epoch = None

    async def _try(awaitable, default, timeout_s: float = 0.9):
        try:
            return await asyncio.wait_for(awaitable, timeout=timeout_s)
        except Exception:
            return default
    governance_context = wm.get_governance_placeholders() if hasattr(wm, "get_governance_placeholders") else {}
    if active_epoch is not None:
        if not governance_context.get("current_governance_epoch"):
            governance_context["current_governance_epoch"] = active_epoch.epoch_id
        if not governance_context.get("current_score_id"):
            governance_context["current_score_id"] = active_epoch.score_id
        if not governance_context.get("current_genre_mode"):
            governance_context["current_genre_mode"] = active_epoch.genre_mode
        if not governance_context.get("current_world_state_hash"):
            governance_context["current_world_state_hash"] = active_epoch.world_state_hash
        if not governance_context.get("strictness_level"):
            governance_context["strictness_level"] = active_epoch.strictness_level
    if hasattr(vns, "get_domain_pulse_state"):
        governance_context["domain_pulse_global"] = vns.get_domain_pulse_state("global")
    try:
        latest_harmonic = await db.triune_outbound_queue.find_one(
            {
                "$or": [
                    {"harmonic_state_at_executor_end": {"$exists": True}},
                    {"harmonic_state_at_gate": {"$exists": True}},
                ]
            },
            {"_id": 0},
            sort=[("updated_at", -1)],
        )
        if latest_harmonic:
            governance_context["latest_harmonic_state"] = (
                latest_harmonic.get("harmonic_state_at_executor_end")
                or latest_harmonic.get("harmonic_state_at_gate")
            )
            governance_context["latest_harmonic_timeline"] = (
                (latest_harmonic.get("polyphonic_context") or {}).get("harmonic_timeline")
                if isinstance(latest_harmonic.get("polyphonic_context"), dict)
                else None
            )
    except Exception:
        pass
    # header calculations (guard against missing DB). Use timeouts because
    # count_documents on large collections can stall page loads.
    total_entities = total_campaigns = high_risk_identities = critical_hosts = active_containments = deception_interactions = 0
    if hasattr(wm, "entities") and wm.entities is not None:
        async def _safe_count(query: Optional[Dict[str, Any]] = None, timeout_s: float = 0.9) -> int:
            try:
                if not query:
                    # Fast path for rough sizing.
                    return int(await asyncio.wait_for(wm.entities.estimated_document_count(), timeout=timeout_s))
                return int(await asyncio.wait_for(wm.entities.count_documents(query), timeout=timeout_s))
            except Exception:
                return 0

        total_entities, total_campaigns, high_risk_identities, critical_hosts, active_containments, deception_interactions = await asyncio.gather(
            _safe_count(None, timeout_s=0.9),
            _safe_count({"type": "campaign"}, timeout_s=0.9),
            _safe_count({"type": "user", "attributes.risk_score": {"$gte": 0.75}}, timeout_s=0.9),
            _safe_count({"type": "host", "attributes.risk_score": {"$gte": 0.8}}, timeout_s=0.9),
            _safe_count({"attributes.contained": True}, timeout_s=0.9),
            _safe_count({"attributes.deception_hit": True}, timeout_s=0.9),
        )
    hdr = {
        "risk_level": "elevated" if high_risk_identities + critical_hosts > 0 else "low",
        "active_campaigns": total_campaigns,
        "high_risk_identities": high_risk_identities,
        "critical_hosts": critical_hosts,
        "active_containments": active_containments,
        "deception_interactions": deception_interactions,
        "last_state_change": None,
        "newest_narrative": None,
        "trust_drift": "stable",
        "ml_confidence": 0.0,
        "score_id": governance_context.get("current_score_id"),
        "genre_mode": governance_context.get("current_genre_mode"),
        "governance_epoch": governance_context.get("current_governance_epoch"),
        "world_state_hash": governance_context.get("current_world_state_hash"),
        "strictness_level": governance_context.get("strictness_level"),
        "latest_harmonic_state": governance_context.get("latest_harmonic_state"),
        "domain_pulse_global": governance_context.get("domain_pulse_global"),
    }
    # --- Agent enrichment: pull real data from unified_agents ---
    agent_entities: List[Dict] = []
    _online_count = 0
    _threat_agents = 0
    try:
        now_utc = datetime.now(timezone.utc)
        _agent_docs = await db.unified_agents.find(
            {},
            {"_id": 0, "agent_id": 1, "hostname": 1, "platform": 1, "status": 1,
             "last_heartbeat": 1, "threat_count": 1},
        ).to_list(200)
        for _a in _agent_docs:
            _lh = _a.get("last_heartbeat")
            try:
                _lh_dt = datetime.fromisoformat(str(_lh).replace("Z", "+00:00")) if _lh else None
            except Exception:
                _lh_dt = None
            _is_online = bool(_lh_dt and (now_utc - _lh_dt) <= timedelta(minutes=5))
            if _is_online:
                _online_count += 1
            _tc = _a.get("threat_count") or 0
            if _tc > 0:
                _threat_agents += 1
            agent_entities.append({
                "id": _a.get("agent_id", "unknown"),
                "type": "host",
                "name": _a.get("hostname") or _a.get("agent_id", "unknown"),
                "attributes": {
                    "hostname": _a.get("hostname"),
                    "platform": _a.get("platform"),
                    "status": "online" if _is_online else "offline",
                    "threat_count": _tc,
                    "risk_score": min(1.0, 0.1 + _tc * 0.2),
                },
            })
        # Fill zeros with agent-derived values when world model is sparse
        if hdr["critical_hosts"] == 0 and _threat_agents > 0:
            hdr["critical_hosts"] = _threat_agents
        if hdr["risk_level"] == "low" and _threat_agents > 0:
            hdr["risk_level"] = "moderate"
        hdr["online_agents"] = _online_count
        hdr["total_agents"] = len(_agent_docs)
    except Exception:
        hdr.setdefault("online_agents", 0)
        hdr.setdefault("total_agents", 0)

    # Pull world entities for graph (merge with agents)
    _wm_entities: List[Dict] = []
    try:
        if hasattr(wm, "entities") and wm.entities is not None:
            _wm_entities = _json_safe(
                await _try(wm.entities.find({}, {"_id": 0}).limit(100).to_list(100), [], timeout_s=0.9)
            )
    except Exception:
        pass
    all_entities = _wm_entities + agent_entities

    # Pull recent world events
    recent_events: List[Dict] = []
    try:
        if hasattr(db, "world_events"):
            _wevts = await _try(
                db.world_events.find({}, {"_id": 0}).sort("created", -1).limit(40).to_list(40),
                [],
                timeout_s=0.9,
            )
            recent_events = _json_safe(_wevts)
    except Exception:
        pass

    # Build metatron_summary from real counts
    _soar_count = 0
    try:
        _soar_count = int(await _try(db.soar_executions.count_documents({}), 0, timeout_s=0.9))
    except Exception:
        pass
    _parts = []
    if agent_entities:
        _parts.append(
            f"Seraph monitors {len(agent_entities)} endpoint{'s' if len(agent_entities) != 1 else ''} "
            f"({_online_count} online)."
        )
    if _soar_count:
        _parts.append(f"{_soar_count} SOAR execution{'s' if _soar_count != 1 else ''} recorded.")
    if hdr.get("active_campaigns", 0):
        _nc = hdr["active_campaigns"]
        _parts.append(f"{_nc} active campaign{'s' if _nc != 1 else ''} tracked.")
    if not _parts:
        _parts.append("Metatron is collecting telemetry and building situational context.")
    _parts.append(f"Risk posture: {hdr.get('risk_level', 'unknown')}.")
    metatron_summary = " ".join(_parts)

    # threat narrative based on latest campaign
    if hasattr(wm, "campaigns") and wm.campaigns is not None:
        latest = await _try(wm.get_latest_campaign(), None, timeout_s=0.9)
    else:
        latest = None
    if latest:
        narr = {
            "campaign_id": latest.id,
            "stage": latest.attributes.get("stage") if hasattr(latest, "attributes") else None,
            "objective": latest.attributes.get("objective") if hasattr(latest, "attributes") else None,
            "origin_host": latest.attributes.get("origin_host") if hasattr(latest, "attributes") else None,
            "evidence": latest.attributes.get("evidence", []),
            "confidence": latest.confidence,
            "predicted_next": latest.attributes.get("predicted_next", []),
        }
    else:
        narr = {"campaign_id": None, "stage": None, "objective": None, "origin_host": None, "evidence": [], "confidence": 0.0, "predicted_next": []}
    # Heavy world-model computations can block the event loop (CPU-bound).
    # Default to lite mode to keep UI responsive; callers can opt-in to full.
    if lite:
        attack = {"nodes": [], "edges": []}
        trust = {"identity": "stable", "device": "stable", "agent_health": "unknown", "policy_violations": 0, "token_anomalies": 0}
        hotspots = []
        timeline = []
        actions = []
    else:
        # build attack path from world model if DB available
        if hasattr(wm, "entities") and wm.entities is not None:
            attack = await _try(wm.compute_attack_path(), {"nodes": [], "edges": []}, timeout_s=2.5)
        else:
            attack = {"nodes": [], "edges": []}
        # trust state derived
        if hasattr(wm, "entities") and wm.entities is not None:
            trust = await _try(
                wm.compute_trust_metrics(),
                {"identity": "stable", "device": "stable", "agent_health": "unknown", "policy_violations": 0, "token_anomalies": 0},
                timeout_s=2.5,
            )
        else:
            trust = {"identity": "stable", "device": "stable", "agent_health": "unknown", "policy_violations": 0, "token_anomalies": 0}
        # hotspots
        if hasattr(wm, "entities") and wm.entities is not None:
            hs_entities = await _try(wm.list_hotspots(limit=5), [], timeout_s=2.5)
            hotspots = [e.dict() for e in hs_entities] if hs_entities else []
        else:
            hotspots = []
        # timeline, actions, hypotheses
        if hasattr(wm, "entities") and wm.entities is not None:
            timeline = await _try(wm.list_timeline(limit=50), [], timeout_s=2.5)
            actions = await _try(wm.list_actions(limit=10), [], timeout_s=2.5)
        else:
            timeline = []
            actions = []
    hypotheses = []

    # include recent triune analyses (background Michael results) for UI
    triune_analyses = []
    try:
        if hasattr(db, "triune_analysis") and db.triune_analysis is not None:
            cursor = db.triune_analysis.find({}, {"_id": 0}).sort("created", -1).limit(10)
            triune_analyses = [t async for t in cursor]
            # build simple hypotheses list from top-ranked candidate per analysis
            for t in triune_analyses:
                ranked = t.get("ranked") or []
                if ranked:
                    top = ranked[0]
                    # include ai components if present in ranked entries
                    hypotheses.append({
                        "analysis_id": t.get("id"),
                        "candidate": top.get("candidate") if isinstance(top, dict) else top,
                        "score": top.get("score") if isinstance(top, dict) else None,
                        "components": top.get("components") if isinstance(top, dict) else None,
                        "score_id": (
                            ((t.get("context") or {}).get("score_id"))
                            or (((t.get("context") or {}).get("polyphonic_context") or {}).get("score_id")
                                if isinstance((t.get("context") or {}).get("polyphonic_context"), dict) else None)
                            or governance_context.get("current_score_id")
                        ),
                        "genre_mode": (
                            ((t.get("context") or {}).get("genre_mode"))
                            or (((t.get("context") or {}).get("polyphonic_context") or {}).get("genre_mode")
                                if isinstance((t.get("context") or {}).get("polyphonic_context"), dict) else None)
                            or governance_context.get("current_genre_mode")
                        ),
                        "notation_token": (
                            ((t.get("context") or {}).get("notation_token"))
                            or (((t.get("context") or {}).get("polyphonic_context") or {}).get("notation_token")
                                if isinstance((t.get("context") or {}).get("polyphonic_context"), dict) else None)
                        ),
                        "world_state_hash": (
                            ((t.get("context") or {}).get("world_state_hash"))
                            or (((t.get("context") or {}).get("polyphonic_context") or {}).get("world_state_hash")
                                if isinstance((t.get("context") or {}).get("polyphonic_context"), dict) else None)
                            or governance_context.get("current_world_state_hash")
                        ),
                        "voice_role": (
                            ((t.get("context") or {}).get("voice_type"))
                            or ((((t.get("context") or {}).get("polyphonic_context") or {}).get("voice_profile") or {}).get("voice_type")
                                if isinstance((t.get("context") or {}).get("polyphonic_context"), dict) else None)
                        ),
                    })
    except Exception:
        # best-effort: do not fail the entire state response if triune collection is missing
        triune_analyses = []

    resp = {
        "header": hdr,
        "narrative": narr,
        "attack_path": attack,
        "trust": trust,
        "hotspots": hotspots,
        "actions": actions,
        "hypotheses": hypotheses,
        "triune_analyses": triune_analyses,
        "timeline": timeline,
        "governance_context": governance_context,
        "entities": all_entities,
        "recent_events": recent_events,
        "metatron_summary": metatron_summary,
    }
    safe_resp = _json_safe(resp)

    # optionally validate/serialize via Pydantic model if available
    if MetatronState is not None:
        try:
            return MetatronState(**safe_resp)
        except Exception:
            # best-effort: fall back to plain dict
            pass
    return safe_resp

# additional endpoints will be added as architecture evolves


@router.get("/metatron/entity/{entity_id}")
async def get_entity(entity_id: str, db=Depends(get_db)):
    """Return a single world-model entity by id."""
    wm = WorldModelService(db)
    if not hasattr(wm, "entities") or wm.entities is None:
        raise HTTPException(status_code=404, detail="world model not available")
    doc = await wm.entities.find_one({"id": entity_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="entity not found")
    return _json_safe(doc)


@router.get("/metatron/entities")
async def list_entities(type: Optional[str] = None, limit: int = 50, db=Depends(get_db)):
    """List world-model entities, optional filter by `type` and limit."""
    wm = WorldModelService(db)
    if not hasattr(wm, "entities") or wm.entities is None:
        return []
    query = {}
    if type:
        query["type"] = type
    cursor = wm.entities.find(query, {"_id": 0}).limit(limit)
    results = [d async for d in cursor]
    return _json_safe(results)


@router.get("/metatron/metrics")
async def metatron_metrics(db=Depends(get_db)):
    """Return graph metrics computed from the world model."""
    wm = WorldModelService(db)
    if not hasattr(wm, "entities") or wm.entities is None:
        return {"centrality": {}, "avg_path_distance": 0.0, "privilege_escalation_likelihood": 0.0, "blast_radius": 0}
    metrics = await wm.compute_graph_metrics()
    return _json_safe(metrics)


@router.post("/metatron/campaign")
async def create_campaign(payload: Dict[str, Any], db=Depends(get_db)):
    """Create a campaign narrative object.

    Accepts keys: id (optional), name, objective, stage, confidence, entities, techniques, predicted_next, attributes
    """
    wm = WorldModelService(db)
    if not hasattr(wm, "campaigns") or wm.campaigns is None:
        raise HTTPException(status_code=500, detail="campaign storage not configured")
    import uuid
    from datetime import datetime, timezone

    cid = payload.get("id") or f"camp-{uuid.uuid4().hex[:8]}"
    # Build canonical campaign document with explicit fields
    doc = {
        "id": cid,
        "name": payload.get("name"),
        "techniques": payload.get("techniques") or [],
        "confidence": float(payload.get("confidence") or 0.0),
        "entities": payload.get("entities") or [],
        "objective": payload.get("objective"),
        "stage": payload.get("stage"),
        "predicted_next_moves": payload.get("predicted_next") or payload.get("predicted_next_moves") or [],
        "timeline": payload.get("timeline") or [],
        "attributes": payload.get("attributes") or {},
        "first_detected": payload.get("first_detected") or datetime.now(timezone.utc).isoformat(),
    }
    # Ensure attributes reflect key narrative fields for backward compatibility
    doc["attributes"].setdefault("objective", doc.get("objective"))
    doc["attributes"].setdefault("stage", doc.get("stage"))
    doc["attributes"].setdefault("predicted_next", doc.get("predicted_next_moves") or [])
    await wm.campaigns.insert_one(doc)
    # return created doc without _id
    out = {k: v for k, v in doc.items()}
    return _json_safe(out)


@router.get("/metatron/campaigns")
async def list_campaigns(db=Depends(get_db)):
    wm = WorldModelService(db)
    if not hasattr(wm, "campaigns") or wm.campaigns is None:
        return []
    cursor = wm.campaigns.find({}, {"_id": 0}).sort("first_detected", -1)
    return _json_safe([c async for c in cursor])


@router.get("/metatron/campaign/{campaign_id}")
async def get_campaign(campaign_id: str, db=Depends(get_db)):
    wm = WorldModelService(db)
    if not hasattr(wm, "campaigns") or wm.campaigns is None:
        raise HTTPException(status_code=404, detail="campaign storage not configured")
    doc = await wm.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="campaign not found")
    return _json_safe(doc)


@router.put("/metatron/campaign/{campaign_id}")
async def update_campaign(campaign_id: str, payload: Dict[str, Any], db=Depends(get_db)):
    wm = WorldModelService(db)
    if not hasattr(wm, "campaigns") or wm.campaigns is None:
        raise HTTPException(status_code=500, detail="campaign storage not configured")
    # merge provided fields into attributes and top-level
    to_set = {}
    if "name" in payload:
        to_set["name"] = payload["name"]
    if "techniques" in payload:
        to_set["techniques"] = payload["techniques"]
    if "confidence" in payload:
        try:
            to_set["confidence"] = float(payload["confidence"])
        except Exception:
            pass
    # attributes and top-level narrative fields
    attr_updates = payload.get("attributes") or {}
    # allow top-level objective/stage/predicted_next_moves/timeline as convenience
    for k in ("objective", "stage", "predicted_next", "predicted_next_moves", "origin_host", "evidence", "timeline"):
        if k in payload:
            # normalize predicted_next vs predicted_next_moves
            if k == "predicted_next_moves" and "predicted_next" not in attr_updates:
                attr_updates["predicted_next"] = payload[k]
            else:
                attr_updates[k] = payload[k]
    if attr_updates:
        to_set.setdefault("attributes", {})
        to_set["attributes"].update(attr_updates)
    # also allow updating explicit top-level fields
    if "objective" in payload:
        to_set["objective"] = payload["objective"]
    if "stage" in payload:
        to_set["stage"] = payload["stage"]
    if "predicted_next" in payload or "predicted_next_moves" in payload:
        to_set["predicted_next_moves"] = payload.get("predicted_next") or payload.get("predicted_next_moves")
    if "timeline" in payload:
        to_set["timeline"] = payload["timeline"]

    if not to_set:
        return {"updated": False}

    await wm.campaigns.update_one({"id": campaign_id}, {"$set": to_set}, upsert=False)
    doc = await wm.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    return _json_safe(doc or {"updated": True})


@router.delete("/metatron/campaign/{campaign_id}")
async def delete_campaign(campaign_id: str, db=Depends(get_db)):
    wm = WorldModelService(db)
    if not hasattr(wm, "campaigns") or wm.campaigns is None:
        raise HTTPException(status_code=500, detail="campaign storage not configured")
    await wm.campaigns.delete_one({"id": campaign_id})
    return {"deleted": True}
