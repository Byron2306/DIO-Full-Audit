"""
Audit Logging Router
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from dataclasses import asdict

from .dependencies import get_current_user, check_permission

# Import audit logging services
from audit_logging import audit, AuditCategory, AuditSeverity

# Optional compliance and audit services
try:
    from services.cce_worker import CCEWorker
except ImportError:
    CCEWorker = None

try:
    from services.accountability_ledger import AccountabilityLedger
except ImportError:
    AccountabilityLedger = None

try:
    from services.scrutiny_engine import ScrutinyEngine
except ImportError:
    ScrutinyEngine = None

try:
    from services.kernel_audit_tailer import get_kernel_audit_tailer
except ImportError:
    get_kernel_audit_tailer = None

router = APIRouter(prefix="/audit", tags=["Audit"])

@router.get("/logs")
async def get_audit_logs(
    category: Optional[str] = None,
    severity: Optional[str] = None,
    actor: Optional[str] = None,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """Get audit logs with filtering"""
    # Convert string to enum value if provided
    category_val = category if category else None
    severity_val = severity if severity else None
    
    # Use search method which returns List[Dict]
    logs = await audit.search(
        category=category_val,
        severity=severity_val,
        actor=actor,
        limit=limit
    )
    # search already returns dicts, no conversion needed
    return {"logs": logs, "count": len(logs)}

@router.get("/stats")
async def get_audit_stats(current_user: dict = Depends(get_current_user)):
    """Get audit log statistics"""
    stats = await audit.get_stats()
    return stats

@router.get("/recent")
async def get_recent_audit(limit: int = 20, current_user: dict = Depends(get_current_user)):
    """Get recent audit entries"""
    logs = await audit.get_recent(limit=limit)
    # Convert AuditEntry dataclasses to dicts
    return [asdict(log) for log in logs]


@router.post("/compliance/check")
async def run_compliance_check(
    scope: str = "system",
    current_user: dict = Depends(check_permission("read")),
):
    """Run compliance check engine (CCE) scan."""
    if not CCEWorker:
        raise HTTPException(status_code=501, detail="Compliance check engine not available")
    
    try:
        cce = CCEWorker()
        results = await cce.run_scan(scope=scope)
        return {
            "success": True,
            "scope": scope,
            "compliance_findings": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compliance check failed: {str(e)}")


@router.post("/accountability/record")
async def record_accountability_entry(
    action: str,
    principal: str,
    evidence: dict,
    current_user: dict = Depends(check_permission("write")),
):
    """Record tamper-proof accountability entry."""
    if not AccountabilityLedger:
        raise HTTPException(status_code=501, detail="Accountability ledger not available")
    
    try:
        ledger = AccountabilityLedger()
        entry = await ledger.record(
            action=action,
            principal=principal,
            evidence=evidence,
        )
        return {"success": True, "entry_id": entry.get("id")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record accountability: {str(e)}")


@router.get("/kernel/audit")
async def get_kernel_audit_log(
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
):
    """Get kernel audit trail (LSM/BPF events)."""
    if not get_kernel_audit_tailer:
        raise HTTPException(status_code=501, detail="Kernel audit tailer not available")
    
    try:
        tailer = get_kernel_audit_tailer()
        events = await tailer.get_recent_events(limit=limit)
        return {
            "success": True,
            "events": events,
            "count": len(events),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve kernel audit: {str(e)}")


@router.post("/scrutiny/analyze")
async def analyze_with_scrutiny(
    target_id: str,
    analysis_type: str = "comprehensive",
    current_user: dict = Depends(check_permission("read")),
):
    """Analyze target with scrutiny engine."""
    if not ScrutinyEngine:
        raise HTTPException(status_code=501, detail="Scrutiny engine not available")
    
    try:
        engine = ScrutinyEngine()
        analysis = await engine.analyze(target_id, analysis_type=analysis_type)
        return {
            "success": True,
            "target_id": target_id,
            "analysis": analysis,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scrutiny analysis failed: {str(e)}")

@router.post("/cleanup")
async def cleanup_audit_logs(days: int = 90, current_user: dict = Depends(check_permission("manage_users"))):
    """Clean up old audit logs"""
    result = await audit.cleanup_old_entries(days)
    return {"deleted_count": result}
