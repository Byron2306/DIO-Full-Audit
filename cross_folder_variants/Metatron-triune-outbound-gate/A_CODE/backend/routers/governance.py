from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .dependencies import get_db, check_permission, get_current_user
from backend.services.governance_authority import GovernanceDecisionAuthority
from backend.services.governance_executor import GovernanceExecutorService

# Wire in additional governance services
try:
    from backend.services.constitutional_projection import ConstitutionalProjector
except ImportError:
    ConstitutionalProjector = None

try:
    from backend.services.governance_context import GovernanceContext
except ImportError:
    GovernanceContext = None

try:
    from backend.services.coronation_service import CoronationService
except ImportError:
    CoronationService = None

try:
    from backend.services.coronation_schemas import CovenantState, PrincipalIdentity, CovenantTerms
except ImportError:
    CovenantState = None
    PrincipalIdentity = None
    CovenantTerms = None

router = APIRouter(prefix="/governance", tags=["Governance"])


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DecisionApproveRequest(BaseModel):
    notes: Optional[str] = None
    execute_now: bool = True


class DecisionDenyRequest(BaseModel):
    reason: Optional[str] = None


class ExecutorRunRequest(BaseModel):
    limit: int = 100


@router.get("/decisions/pending")
async def get_pending_decisions(
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    docs = await db.triune_decisions.find(
        {"status": "pending"},
        {"_id": 0},
    ).sort("created_at", 1).limit(max(1, min(limit, 500))).to_list(max(1, min(limit, 500)))
    return {"count": len(docs), "items": docs}


@router.post("/decisions/{decision_id}/approve")
async def approve_decision(
    decision_id: str,
    request: DecisionApproveRequest,
    current_user: dict = Depends(check_permission("write")),
):
    db = get_db()
    decision = await db.triune_decisions.find_one({"decision_id": decision_id}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    actor = current_user.get("email", current_user.get("id", "unknown"))
    authority = GovernanceDecisionAuthority(db)
    await authority.approve_decision(
        decision_id=decision_id,
        actor=actor,
        notes=request.notes,
        execution_status="pending_executor",
        source="governance_router",
    )

    execution_summary: Optional[Dict[str, Any]] = None
    if request.execute_now:
        execution_summary = await GovernanceExecutorService(db).process_approved_decisions(limit=100)

    return {
        "success": True,
        "decision_id": decision_id,
        "status": "approved",
        "execution_summary": execution_summary,
    }


@router.post("/decisions/{decision_id}/deny")
async def deny_decision(
    decision_id: str,
    request: DecisionDenyRequest,
    current_user: dict = Depends(check_permission("write")),
):
    db = get_db()
    decision = await db.triune_decisions.find_one({"decision_id": decision_id}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    actor = current_user.get("email", current_user.get("id", "unknown"))
    authority = GovernanceDecisionAuthority(db)
    await authority.deny_decision(
        decision_id=decision_id,
        actor=actor,
        reason=request.reason,
        source="governance_router",
    )

    await db.agent_commands.update_many(
        {"decision_id": decision_id, "status": {"$in": ["gated_pending_approval", "pending_approval"]}},
        {
            "$set": {"status": "rejected", "updated_at": _iso_now(), "rejected_by": actor, "rejected_reason": request.reason},
            "$inc": {"state_version": 1},
            "$push": {
                "state_transition_log": {
                    "from_status": "gated_pending_approval",
                    "to_status": "rejected",
                    "actor": actor,
                    "reason": "triune decision denied",
                    "timestamp": _iso_now(),
                }
            },
        },
    )

    return {"success": True, "decision_id": decision_id, "status": "denied"}


@router.post("/executor/run-once")
async def run_executor_once(
    request: ExecutorRunRequest,
    current_user: dict = Depends(check_permission("write")),
):
    db = get_db()
    summary = await GovernanceExecutorService(db).process_approved_decisions(
        limit=max(1, min(request.limit, 500))
    )
    return {"success": True, "summary": summary}


@router.get("/context")
async def get_governance_context(
    include_policies: bool = True,
    current_user: dict = Depends(get_current_user),
):
    """Get current governance context and active policies."""
    if not GovernanceContext:
        raise HTTPException(status_code=501, detail="GovernanceContext service not available")
    
    try:
        db = get_db()
        context_service = GovernanceContext(db)
        context = await context_service.get_current_context()
        
        if include_policies:
            policies = await context_service.get_active_policies()
            context["active_policies"] = policies
        
        return {"success": True, "context": context}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve governance context: {str(e)}")


@router.post("/projection/forecast")
async def forecast_constitutional_impact(
    command: str,
    authority_level: str = "normal",
    current_user: dict = Depends(check_permission("read")),
):
    """Project constitutional impact of a proposed command without executing."""
    if not ConstitutionalProjector:
        raise HTTPException(status_code=501, detail="ConstitutionalProjector service not available")
    
    try:
        projector = ConstitutionalProjector()
        forecast = await projector.project_impact(command, authority_level)
        
        return {
            "success": True,
            "command": command,
            "projected_impact": forecast.get("impact", {}),
            "policy_violations": forecast.get("violations", []),
            "recommended_escalation": forecast.get("escalation_level", "none"),
            "confidence": forecast.get("confidence", 0.0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Projection failed: {str(e)}")


@router.get("/coronation/articles")
async def get_coronation_articles(
    article_type: str = "genesis",
    current_user: dict = Depends(get_current_user),
):
    """Get genesis or presence articles for the coronation covenant."""
    if not CoronationService:
        raise HTTPException(status_code=501, detail="CoronationService not available")
    
    try:
        db = get_db()
        service = CoronationService(db)
        
        if article_type.lower() == "presence":
            articles = service.get_presence_articles()
            articles_hash = service.get_presence_articles_hash()
        else:
            articles = service.get_genesis_articles()
            articles_hash = service.get_genesis_hash()
        
        return {
            "success": True,
            "article_type": article_type,
            "articles": articles,
            "hash": articles_hash,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve articles: {str(e)}")


@router.post("/coronation/begin")
async def begin_coronation_ceremony(
    current_user: dict = Depends(check_permission("write")),
):
    """Initiate a machine-human coronation covenant ceremony."""
    if not CoronationService:
        raise HTTPException(status_code=501, detail="CoronationService not available")
    
    try:
        db = get_db()
        service = CoronationService(db)
        result = await service.begin_coronation()
        return {"success": True, "ceremony": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Coronation initiation failed: {str(e)}")


@router.post("/coronation/seal")
async def seal_coronation_covenant(
    current_user: dict = Depends(check_permission("write")),
):
    """Seal and finalize the coronation covenant."""
    if not CoronationService:
        raise HTTPException(status_code=501, detail="CoronationService not available")
    
    try:
        db = get_db()
        service = CoronationService(db)
        result = await service.seal_covenant()
        return {"success": True, "sealed": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Coronation sealing failed: {str(e)}")
