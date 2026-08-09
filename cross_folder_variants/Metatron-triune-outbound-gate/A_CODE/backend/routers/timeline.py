"""
Threat Timeline Router
"""
from dataclasses import asdict
import json
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional

from .dependencies import get_current_user, get_db, check_permission

# Import timeline services
from threat_timeline import timeline_builder, ReportType, ThreatTimeline, TimelineEvent

router = APIRouter(prefix="/timeline", tags=["Timeline"])


class ArtifactRegisterRequest(BaseModel):
    artifact_type: str
    name: str
    description: str
    hash_md5: Optional[str] = None
    hash_sha256: Optional[str] = None


class ArtifactCustodyUpdateRequest(BaseModel):
    action: str
    notes: Optional[str] = ""


@router.get("/correlate/all")
async def correlate_all_timelines(
    preload_limit: int = Query(25, ge=2, le=200),
    current_user: dict = Depends(check_permission("read")),
):
    """Correlate incidents across recent timelines."""
    _ = current_user
    db = get_db()

    # Prime correlator with recent incidents so correlation works after restart.
    recent = await db.threats.find({}, {"_id": 0, "id": 1}).sort("created_at", -1).limit(preload_limit).to_list(preload_limit)
    for item in recent:
        tid = item.get("id")
        if tid:
            await timeline_builder.build_timeline(tid, full_analysis=True)

    result = timeline_builder.correlate_all_incidents()
    result["preloaded_timelines"] = len(recent)
    return result


@router.get("/{threat_id}/related-incidents")
async def get_related_incidents(
    threat_id: str,
    current_user: dict = Depends(check_permission("read")),
):
    """Get incidents correlated to the provided threat timeline."""
    _ = current_user
    db = get_db()

    if threat_id.startswith("alert:"):
        return {"threat_id": threat_id, "related_incidents": [], "count": 0}

    threat = await db.threats.find_one({"id": threat_id}, {"_id": 0, "id": 1})
    if not threat:
        raise HTTPException(status_code=404, detail="Threat not found")

    await timeline_builder.build_timeline(threat_id, full_analysis=True)
    related = timeline_builder.find_related_incidents(threat_id)
    return {
        "threat_id": threat_id,
        "related_incidents": related,
        "count": len(related),
    }


@router.get("/{threat_id}/report")
async def get_timeline_report(
    threat_id: str,
    type: str = Query("technical"),
    current_user: dict = Depends(check_permission("read")),
):
    """Generate enterprise incident report for a threat timeline."""
    _ = current_user
    db = get_db()

    if threat_id.startswith("alert:"):
        alert_id = threat_id.split(":", 1)[1].strip()
        alert = await db.alerts.find_one({"id": alert_id}, {"_id": 0})
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        linked = alert.get("threat_id")
        if linked:
            threat_id = linked
        else:
            # Generate a lightweight markdown report for alert-only incidents so
            # the Timeline UI can still produce something actionable.
            ts = alert.get("created_at") or datetime.now(timezone.utc).isoformat()
            sev = str(alert.get("severity") or "medium")
            title = alert.get("title") or f"Alert {alert_id}"
            message = alert.get("message") or ""
            a_type = alert.get("type") or "alert"
            status = alert.get("status") or "new"

            report = "\n".join(
                [
                    f"# Alert Report: {title}",
                    "",
                    f"- Alert ID: `{alert_id}`",
                    f"- Timestamp: `{ts}`",
                    f"- Severity: `{sev}`",
                    f"- Type: `{a_type}`",
                    f"- Status: `{status}`",
                    "",
                    "## Summary",
                    message.strip() or "(no message provided)",
                    "",
                    "## Recommended Actions",
                    "- Validate the signal source and affected systems.",
                    "- Correlate with Threat Dashboard and Command Center for matching incidents.",
                    "- If the alert is confirmed malicious, promote it into a Threat record and re-run the timeline.",
                    "",
                ]
            )
            return {
                "threat_id": f"alert:{alert_id}",
                "report_type": type,
                "report": report,
                "note": "Alert-only report (no linked Threat record).",
            }

    threat = await db.threats.find_one({"id": threat_id}, {"_id": 0, "id": 1})
    if not threat:
        raise HTTPException(status_code=404, detail="Threat not found")

    try:
        report_type = ReportType(type.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Unsupported report type: {type}",
                "supported": [rt.value for rt in ReportType],
            },
        )

    timeline = await timeline_builder.build_timeline(threat_id, full_analysis=True)
    if not timeline:
        raise HTTPException(status_code=404, detail="Could not build timeline")

    report = timeline_builder.generate_report(timeline, report_type=report_type)
    return {
        "threat_id": threat_id,
        "report_type": report_type.value,
        "report": report,
    }


@router.post("/artifacts/register")
async def register_timeline_artifact(
    request: ArtifactRegisterRequest,
    current_user: dict = Depends(check_permission("write")),
):
    """Register a forensic artifact for timeline evidence workflows."""
    actor = current_user.get("email") or current_user.get("name") or "unknown"
    artifact = timeline_builder.register_artifact(
        artifact_type=request.artifact_type,
        name=request.name,
        description=request.description,
        collected_by=actor,
        hash_md5=request.hash_md5,
        hash_sha256=request.hash_sha256,
    )
    return {
        "status": "registered",
        "artifact": asdict(artifact),
    }


@router.post("/artifacts/{artifact_id}/custody")
async def update_artifact_custody(
    artifact_id: str,
    request: ArtifactCustodyUpdateRequest,
    current_user: dict = Depends(check_permission("write")),
):
    """Append chain-of-custody entry for an artifact."""
    actor = current_user.get("email") or current_user.get("name") or "unknown"
    ok = timeline_builder.update_artifact_custody(
        artifact_id=artifact_id,
        action=request.action,
        actor=actor,
        notes=request.notes or "",
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Artifact not found")

    artifact = timeline_builder.get_artifact(artifact_id)
    return {
        "status": "updated",
        "artifact_id": artifact_id,
        "artifact": artifact,
    }


@router.get("/artifacts/{artifact_id}/custody-report")
async def get_artifact_custody_report(
    artifact_id: str,
    current_user: dict = Depends(check_permission("read")),
):
    """Export chain-of-custody report for a forensic artifact."""
    _ = current_user
    report = timeline_builder.export_custody_report(artifact_id)
    if not report:
        raise HTTPException(status_code=404, detail="Artifact not found")

    return {
        "artifact_id": artifact_id,
        "report_markdown": report,
    }

@router.get("/{threat_id}")
async def get_threat_timeline(threat_id: str, current_user: dict = Depends(get_current_user)):
    """Get complete timeline for a threat"""
    db = get_db()

    if threat_id.startswith("alert:"):
        alert_id = threat_id.split(":", 1)[1].strip()
        alert = await db.alerts.find_one({"id": alert_id}, {"_id": 0})
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        linked = alert.get("threat_id")
        if linked:
            # If the alert is linked, return the canonical threat timeline.
            threat_id = linked
        else:
            ts = alert.get("created_at") or datetime.now(timezone.utc).isoformat()
            event = TimelineEvent(
                id=f"alert:{alert_id}",
                timestamp=ts,
                event_type="alert",
                title=alert.get("title") or "Alert",
                description=str(alert.get("message") or ""),
                severity=str(alert.get("severity") or "medium"),
                source="alerts",
                related_alert_id=alert_id,
                details={"type": alert.get("type"), "status": alert.get("status")},
            )
            timeline = ThreatTimeline(
                threat_id=f"alert:{alert_id}",
                threat_name=alert.get("title") or "Alert Incident",
                threat_type=alert.get("type") or "alert",
                severity=alert.get("severity") or "medium",
                status=alert.get("status") or "new",
                first_seen=ts,
                last_updated=ts,
                events=[event],
                summary="Alert-only incident (no linked Threat record yet).",
                recommendations=[],
                metrics={"kind": "alert_only"},
            )
            return asdict(timeline)
    
    # Check if threat exists
    threat = await db.threats.find_one({"id": threat_id}, {"_id": 0})
    if not threat:
        raise HTTPException(status_code=404, detail="Threat not found")
    
    # Build timeline (only takes threat_id)
    timeline = await timeline_builder.build_timeline(threat_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Could not build timeline")
    
    return asdict(timeline)

@router.get("/{threat_id}/export")
async def export_threat_timeline(threat_id: str, format: str = "json", current_user: dict = Depends(get_current_user)):
    """Export timeline in specified format"""
    db = get_db()

    if threat_id.startswith("alert:"):
        # Export the synthetic alert timeline as JSON/Markdown by reusing the normal handler.
        timeline = await get_threat_timeline(threat_id, current_user=current_user)
        if format == "json":
            return timeline
        if format == "markdown":
            return {"markdown": json.dumps(timeline, indent=2)}
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")
    
    threat = await db.threats.find_one({"id": threat_id}, {"_id": 0})
    if not threat:
        raise HTTPException(status_code=404, detail="Threat not found")
    
    timeline = await timeline_builder.build_timeline(threat_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Could not build timeline")
    
    from dataclasses import asdict
    if format == "json":
        return asdict(timeline)
    elif format == "markdown":
        return {"markdown": timeline_builder._to_markdown(timeline)}
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

# Alternative route for listing recent timelines
timelines_router = APIRouter(prefix="/timelines", tags=["Timeline"])

@timelines_router.get("/recent")
async def get_recent_timelines(limit: int = 10, current_user: dict = Depends(get_current_user)):
    """Get recent threat timelines"""
    # Use the class method that handles this properly
    timelines = await timeline_builder.get_recent_timelines(limit)
    return {"timelines": timelines, "count": len(timelines)}
