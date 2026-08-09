"""
Policies and Governance Router
===============================
Exposes policy, governance, and order management endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, Dict, Any
from pydantic import BaseModel

from .dependencies import get_current_user, check_permission, get_db

# Optional policy and governance services
try:
    from backend.services.aule import get_aule_service
except ImportError:
    get_aule_service = None

try:
    from backend.services.notation_token import NotationToken
except ImportError:
    NotationToken = None

try:
    from backend.services.polyphonic_governance import PolyphonicGovernance
except ImportError:
    PolyphonicGovernance = None

try:
    from backend.services.governed_dispatch import GovernedDispatchService
except ImportError:
    GovernedDispatchService = None

try:
    from backend.services.order_engine import OrderEngine
except ImportError:
    OrderEngine = None

try:
    from backend.services.lawful_defense import LawfulDefense
except ImportError:
    LawfulDefense = None

router = APIRouter(prefix="/policies", tags=["Policies"])


@router.post("/policy/check")
async def check_policy_compliance(
    action: str,
    context: Dict[str, Any],
    current_user: dict = Depends(check_permission("read")),
):
    """Check if an action complies with current policies."""
    if not get_aule_service:
        raise HTTPException(status_code=501, detail="Policy service not available")
    
    try:
        aule = get_aule_service()
        complies = await aule.check_compliance(action, context)
        return {
            "success": True,
            "action": action,
            "compliant": complies.get("compliant", False),
            "violations": complies.get("violations", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Policy check failed: {str(e)}")


@router.post("/notation/issue")
async def issue_notation_token(
    holder_id: str,
    notation_type: str,
    expiry_hours: int = 24,
    current_user: dict = Depends(check_permission("write")),
):
    """Issue a notation token for access control."""
    if not NotationToken:
        raise HTTPException(status_code=501, detail="Notation token service not available")
    
    try:
        service = NotationToken()
        token = await service.issue(holder_id, notation_type, expiry_hours=expiry_hours)
        return {
            "success": True,
            "token_id": token.get("id"),
            "holder_id": holder_id,
            "notation_type": notation_type,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token issuance failed: {str(e)}")


@router.get("/governance/votes")
async def get_governance_votes(
    current_user: dict = Depends(get_current_user),
):
    """Get current governance votes (polyphonic governance)."""
    if not PolyphonicGovernance:
        raise HTTPException(status_code=501, detail="Polyphonic governance not available")
    
    try:
        governance = PolyphonicGovernance()
        votes = await governance.get_active_votes()
        return {
            "success": True,
            "votes": votes,
            "count": len(votes),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get votes: {str(e)}")


@router.post("/dispatch/governed")
async def governed_dispatch(
    command: str,
    authority: str,
    db=Depends(get_db),
    current_user: dict = Depends(check_permission("write")),
):
    """Dispatch a command with governance checks."""
    if not GovernedDispatchService:
        raise HTTPException(status_code=501, detail="Governed dispatch not available")
    
    try:
        dispatcher = GovernedDispatchService(db)
        result = await dispatcher.dispatch(command, authority)
        return {
            "success": True,
            "command": command,
            "dispatch_result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dispatch failed: {str(e)}")


@router.post("/orders/create")
async def create_order(
    order_type: str,
    content: Dict[str, Any],
    priority: str = "normal",
    current_user: dict = Depends(check_permission("write")),
):
    """Create an order via the order engine."""
    if not OrderEngine:
        raise HTTPException(status_code=501, detail="Order engine not available")
    
    try:
        engine = OrderEngine()
        order = await engine.create_order(order_type, content, priority=priority)
        return {
            "success": True,
            "order_id": order.get("id"),
            "status": order.get("status"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Order creation failed: {str(e)}")


@router.post("/defense/invoke")
async def invoke_lawful_defense(
    threat_indicator: str,
    defense_type: str,
    current_user: dict = Depends(check_permission("write")),
):
    """Invoke lawful defense against a threat."""
    if not LawfulDefense:
        raise HTTPException(status_code=501, detail="Lawful defense not available")
    
    try:
        defense = LawfulDefense()
        response = await defense.invoke(threat_indicator, defense_type)
        return {
            "success": True,
            "threat": threat_indicator,
            "defense_response": response,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Defense invocation failed: {str(e)}")
