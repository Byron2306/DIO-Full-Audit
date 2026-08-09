"""
Dashboard Router
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from datetime import datetime, timezone, timedelta
from typing import List, Dict
import uuid

from .dependencies import (
    DashboardStats, ThreatResponse, AlertResponse, get_current_user, get_db
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# Collection names must match the unified_agent router
_EDM_HITS_COLLECTION = "agent_edm_telemetry"
_DLP_TELEMETRY_COLLECTION = "agent_monitor_telemetry"

def _time_window_dual(hour_start: datetime, hour_end: datetime, field: str = "created_at") -> Dict:
    """
    Mongo range query that matches both datetime and ISO-8601 string timestamps.

    Several collections in this repo store timestamps as ISO strings, while others
    store native BSON datetimes. This helper keeps dashboard charts non-empty.
    """
    window_dt = {field: {"$gte": hour_start, "$lt": hour_end}}
    window_iso = {field: {"$gte": hour_start.isoformat(), "$lt": hour_end.isoformat()}}
    return {"$or": [window_dt, window_iso]}


@router.get("/edm-dlp/aggregated-stats")
async def get_edm_dlp_aggregated_stats(current_user: dict = Depends(get_current_user)):
    """Return aggregated EDM hit + DLP scan statistics for the frontend dashboard."""
    db = get_db()
    now = datetime.now(timezone.utc)

    # ── EDM Hits ──────────────────────────────────────────────────────────────
    edm_hits = await db[_EDM_HITS_COLLECTION].count_documents({})

    # EDM hits by dataset (pie chart: [{dataset, value}])
    dataset_results = await db[_EDM_HITS_COLLECTION].aggregate([
        {"$group": {"_id": "$dataset_id", "value": {"$sum": 1}}},
        {"$sort": {"value": -1}},
        {"$limit": 10},
    ]).to_list(10)
    edm_hits_by_dataset = [
        {"dataset": r["_id"] or "unknown", "value": r["value"]}
        for r in dataset_results
    ]

    # EDM timeline: last 24 h, one bucket per hour (ISO-string range query)
    edm_hits_timeline = []
    for i in range(23, -1, -1):
        hour_start = (now - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)
        count = await db[_EDM_HITS_COLLECTION].count_documents(_time_window_dual(hour_start, hour_end, field="ingested_at"))
        edm_hits_timeline.append({"time": hour_start.strftime("%H:00"), "hits": count})

    # ── DLP Scans ─────────────────────────────────────────────────────────────
    dlp_scans = await db[_DLP_TELEMETRY_COLLECTION].count_documents(
        {"dlp": {"$exists": True}}
    )

    # DLP timeline: last 24 h
    dlp_scans_timeline = []
    for i in range(23, -1, -1):
        hour_start = (now - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)
        count = await db[_DLP_TELEMETRY_COLLECTION].count_documents({
            "dlp": {"$exists": True},
            **_time_window_dual(hour_start, hour_end, field="timestamp"),
        })
        dlp_scans_timeline.append({"time": hour_start.strftime("%H:00"), "scans": count})

    # DLP policy violations by alert category (clipboard / file / network)
    dlp_agg = await db[_DLP_TELEMETRY_COLLECTION].aggregate([
        {"$match": {"dlp": {"$exists": True}}},
        {"$group": {
            "_id": None,
            "clipboard": {"$sum": "$dlp.clipboard_alerts"},
            "file": {"$sum": "$dlp.file_alerts"},
            "network": {"$sum": "$dlp.network_alerts"},
        }},
    ]).to_list(1)
    if dlp_agg:
        row = dlp_agg[0]
        dlp_policy_violations = [
            {"policy": "Clipboard", "value": int(row.get("clipboard", 0))},
            {"policy": "File", "value": int(row.get("file", 0))},
            {"policy": "Network", "value": int(row.get("network", 0))},
        ]
        dlp_policy_violations = [p for p in dlp_policy_violations if p["value"] > 0]
    else:
        dlp_policy_violations = []
    total_policy_violations = sum(p["value"] for p in dlp_policy_violations)

    # Suppression events: total DLP alert_details entries across all records
    supp_agg = await db[_DLP_TELEMETRY_COLLECTION].aggregate([
        {"$match": {"dlp": {"$exists": True}}},
        {"$project": {"count": {"$size": {"$ifNull": ["$dlp.alert_details", []]}}}},
        {"$group": {"_id": None, "total": {"$sum": "$count"}}},
    ]).to_list(1)
    suppression_events = int(supp_agg[0]["total"]) if supp_agg else 0

    # ── Event Timeline ────────────────────────────────────────────────────────
    event_timeline = []

    edm_events = await db[_EDM_HITS_COLLECTION].find(
        {}, {"_id": 0, "ingested_at": 1, "dataset_id": 1, "source": 1}
    ).sort("ingested_at", -1).to_list(10)
    for e in edm_events:
        ts = e.get("ingested_at")
        if ts:
            event_timeline.append({
                "type": "EDM Hit",
                "description": f"Dataset: {e.get('dataset_id', 'unknown')}, Source: {e.get('source', 'unknown')}",
                "timestamp": ts,
            })

    dlp_events = await db[_DLP_TELEMETRY_COLLECTION].find(
        {"dlp": {"$exists": True}},
        {"_id": 0, "timestamp": 1, "dlp": 1, "agent_id": 1},
    ).sort("timestamp", -1).to_list(10)
    for d in dlp_events:
        ts = d.get("timestamp")
        if ts:
            dlp = d.get("dlp") or {}
            total_alerts = (
                int(dlp.get("clipboard_alerts", 0))
                + int(dlp.get("file_alerts", 0))
                + int(dlp.get("network_alerts", 0))
            )
            event_timeline.append({
                "type": "DLP Scan",
                "description": f"Agent: {d.get('agent_id', 'unknown')}, Alerts: {total_alerts}",
                "timestamp": ts,
            })

    event_timeline.sort(key=lambda x: x["timestamp"], reverse=True)
    event_timeline = event_timeline[:20]

    return JSONResponse({
        "total_edm_hits": edm_hits,
        "edm_hits_timeline": edm_hits_timeline,
        "edm_hits_by_dataset": edm_hits_by_dataset,
        "total_dlp_scans": dlp_scans,
        "dlp_scans_timeline": dlp_scans_timeline,
        "dlp_policy_violations": dlp_policy_violations,
        "total_policy_violations": total_policy_violations,
        "total_suppression_events": suppression_events,
        "event_timeline": event_timeline,
    })

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    db = get_db()
    
    # Get threat counts
    total_threats = await db.threats.count_documents({})
    active_threats = await db.threats.count_documents({"status": "active"})
    contained_threats = await db.threats.count_documents({"status": "contained"})
    resolved_threats = await db.threats.count_documents({"status": "resolved"})
    
    # Get critical alerts
    critical_alerts = await db.alerts.count_documents({"severity": "critical", "status": {"$ne": "resolved"}})
    
    # Threats by type aggregation
    type_pipeline = [{"$group": {"_id": "$type", "count": {"$sum": 1}}}]
    type_results = await db.threats.aggregate(type_pipeline).to_list(20)
    threats_by_type = {r["_id"]: r["count"] for r in type_results if r["_id"]}
    
    # Threats by severity
    severity_pipeline = [{"$group": {"_id": "$severity", "count": {"$sum": 1}}}]
    severity_results = await db.threats.aggregate(severity_pipeline).to_list(10)
    threats_by_severity = {r["_id"]: r["count"] for r in severity_results if r["_id"]}
    
    # Recent threats
    recent_threats_data = await db.threats.find({}, {"_id": 0}).sort("created_at", -1).to_list(5)
    recent_threats = [ThreatResponse(**t) for t in recent_threats_data]
    
    # Recent alerts
    recent_alerts_data = await db.alerts.find({}, {"_id": 0}).sort("created_at", -1).to_list(5)
    recent_alerts = [AlertResponse(**a) for a in recent_alerts_data]
    
    # AI scans today
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    scan_stat = await db.scan_stats.find_one({"date": today}, {"_id": 0})
    ai_scans_today = scan_stat["count"] if scan_stat else 0
    
    # System health
    system_health = 100.0
    if total_threats > 0:
        system_health = ((contained_threats + resolved_threats) / total_threats) * 100
        system_health = min(100, max(0, system_health))
    
    return DashboardStats(
        total_threats=total_threats,
        active_threats=active_threats,
        contained_threats=contained_threats,
        resolved_threats=resolved_threats,
        critical_alerts=critical_alerts,
        threats_by_type=threats_by_type,
        threats_by_severity=threats_by_severity,
        recent_threats=recent_threats,
        recent_alerts=recent_alerts,
        ai_scans_today=ai_scans_today,
        system_health=system_health
    )


@router.get("/timeline")
async def get_threat_timeline(current_user: dict = Depends(get_current_user)):
    """Return a 24-hour threat timeline for the dashboard chart."""
    db = get_db()
    now = datetime.now(timezone.utc)

    def _coerce_dt(value):
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except Exception:
                return None
        return None

    # If there have been no events in the last 24h, anchor the window at the
    # most recent threat/alert timestamp so the chart isn't a flatline while
    # the stats panel shows lots of historical activity.
    anchor = None
    try:
        latest_threat = await db.threats.find(
            {"created_at": {"$exists": True}}, {"_id": 0, "created_at": 1}
        ).sort("created_at", -1).limit(1).to_list(1)
        latest_alert = await db.alerts.find(
            {"created_at": {"$exists": True}}, {"_id": 0, "created_at": 1}
        ).sort("created_at", -1).limit(1).to_list(1)
        candidates = []
        if latest_threat:
            candidates.append(_coerce_dt(latest_threat[0].get("created_at")))
        if latest_alert:
            candidates.append(_coerce_dt(latest_alert[0].get("created_at")))
        candidates = [c for c in candidates if c is not None]
        if candidates:
            anchor = max(candidates)
    except Exception:
        anchor = None

    if anchor is not None and (now - anchor) > timedelta(hours=24):
        now = anchor

    series = []
    for i in range(23, -1, -1):
        hour_start = (now - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)

        threats = await db.threats.count_documents(_time_window_dual(hour_start, hour_end, field="created_at"))
        alerts = await db.alerts.count_documents(_time_window_dual(hour_start, hour_end, field="created_at"))
        blocked = await db.threats.count_documents(
            {**_time_window_dual(hour_start, hour_end, field="created_at"), "status": {"$in": ["contained", "resolved"]}}
        )
        series.append({"time": hour_start.strftime("%H:00"), "threats": threats + alerts, "blocked": blocked})

    return {
        "series": series,
        "source": "db.threats+db.alerts",
        "anchor": now.isoformat(),
        "window_hours": 24,
    }


@router.post("/seed")
async def seed_data():
    """Seed initial demo data"""
    from datetime import timedelta
    db = get_db()
    
    # Check if data already exists
    existing = await db.threats.count_documents({})
    if existing > 0:
        return {"message": "Data already seeded"}
    
    # Sample threats
    sample_threats = [
        {
            "id": str(uuid.uuid4()),
            "name": "GPT-4 Autonomous Agent Attack",
            "type": "ai_agent",
            "severity": "critical",
            "status": "active",
            "source_ip": "192.168.1.105",
            "target_system": "Production API Server",
            "description": "Detected autonomous AI agent attempting to exploit API endpoints with adaptive attack patterns",
            "indicators": ["Superhuman request rate", "Adaptive payload modification", "Non-human timing patterns"],
            "ai_analysis": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Polymorphic Ransomware Variant",
            "type": "malware",
            "severity": "critical",
            "status": "contained",
            "source_ip": "10.0.0.45",
            "target_system": "File Server FS-01",
            "description": "AI-generated polymorphic ransomware detected, code mutations every 30 seconds",
            "indicators": ["Self-modifying bytecode", "Encrypted C2 communication", "Anti-sandbox techniques"],
            "ai_analysis": None,
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Adversarial ML Attack",
            "type": "ai_agent",
            "severity": "high",
            "status": "active",
            "source_ip": "172.16.0.88",
            "target_system": "ML Pipeline",
            "description": "Adversarial inputs detected attempting to poison training data in ML pipeline",
            "indicators": ["Gradient-based perturbations", "Training data injection", "Model inversion attempts"],
            "ai_analysis": None,
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Botnet Command Server",
            "type": "botnet",
            "severity": "high",
            "status": "active",
            "source_ip": "45.33.32.156",
            "target_system": "Network Edge",
            "description": "AI-coordinated botnet C2 server discovered communicating with internal hosts",
            "indicators": ["Encrypted beacon traffic", "Domain generation algorithm", "P2P mesh topology"],
            "ai_analysis": None,
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Deepfake Phishing Campaign",
            "type": "phishing",
            "severity": "medium",
            "status": "resolved",
            "source_ip": "unknown",
            "target_system": "Email Gateway",
            "description": "AI-generated deepfake video phishing attempt targeting executives",
            "indicators": ["Synthetic voice patterns", "Facial manipulation artifacts", "Social engineering vectors"],
            "ai_analysis": None,
            "created_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
    ]
    
    # Sample alerts
    sample_alerts = [
        {
            "id": str(uuid.uuid4()),
            "title": "Critical: AI Agent Behavior Detected",
            "type": "ai_detected",
            "severity": "critical",
            "message": "Behavioral analysis flagged non-human interaction patterns on API endpoint /api/data",
            "status": "new",
            "created_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "title": "Anomaly: Unusual Traffic Spike",
            "type": "anomaly",
            "severity": "high",
            "message": "300% increase in API calls from single source with perfect timing distribution",
            "status": "acknowledged",
            "created_at": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "title": "Signature Match: Known Malware Family",
            "type": "signature",
            "severity": "high",
            "message": "File hash matches AI-generated malware variant LockAI.B",
            "status": "new",
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "title": "Behavioral: Model Probing Detected",
            "type": "behavioral",
            "severity": "medium",
            "message": "Sequential queries suggest systematic probing of ML model decision boundaries",
            "status": "acknowledged",
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        }
    ]
    
    await db.threats.insert_many(sample_threats)
    await db.alerts.insert_many(sample_alerts)
    
    return {"message": "Demo data seeded successfully", "threats": len(sample_threats), "alerts": len(sample_alerts)}
