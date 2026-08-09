"""
Email Gateway Router - API endpoints for SMTP gateway management
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from pydantic import BaseModel
from dataclasses import asdict
import base64

from .dependencies import get_current_user, check_permission
from email_gateway import smtp_gateway, GatewayAction, GatewayMode

router = APIRouter(prefix="/email-gateway", tags=["Email Gateway"])


class ProcessEmailRequest(BaseModel):
    raw_email_base64: Optional[str] = None
    envelope_from: str = ""
    envelope_to: List[str] = []
    subject: str = ""
    body: str = ""
    headers: Optional[dict] = None
    client_ip: str = ""


class UpdatePolicyRequest(BaseModel):
    policy_name: str
    settings: dict


class BlocklistRequest(BaseModel):
    value: str
    list_type: str  # sender, domain, ip


@router.get("/stats")
async def get_gateway_stats(current_user: dict = Depends(get_current_user)):
    """Get email gateway statistics"""
    return smtp_gateway.get_stats()


@router.post("/process")
async def process_email(
    request: ProcessEmailRequest,
    current_user: dict = Depends(get_current_user)
):
    """Process an email through the gateway"""
    try:
        if request.raw_email_base64:
            # Parse raw email
            raw_data = base64.b64decode(request.raw_email_base64)
            message = smtp_gateway.parse_email(raw_data, request.client_ip)
        else:
            # Create message from fields
            from email_gateway import EmailMessage
            import uuid
            from datetime import datetime, timezone
            
            message = EmailMessage(
                message_id=f"api_{uuid.uuid4().hex[:12]}",
                envelope_from=request.envelope_from,
                envelope_to=request.envelope_to,
                subject=request.subject,
                headers=request.headers or {},
                body_text=request.body,
                body_html="",
                attachments=[],
                raw_size=len(request.body),
                received_at=datetime.now(timezone.utc).isoformat(),
                client_ip=request.client_ip
            )
        
        decision = smtp_gateway.process_message(message)
        
        return {
            **asdict(decision),
            "action": decision.action.value
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/quarantine")
async def get_gateway_quarantine(current_user: dict = Depends(get_current_user)):
    """Get quarantined messages"""
    quarantine = smtp_gateway.get_quarantine()
    return {"quarantine": quarantine, "count": len(quarantine)}


@router.post("/quarantine/{quarantine_id}/release")
async def release_from_gateway_quarantine(
    quarantine_id: str,
    current_user: dict = Depends(check_permission("write"))
):
    """Release message from gateway quarantine"""
    success = smtp_gateway.release_from_quarantine(quarantine_id)
    if not success:
        raise HTTPException(status_code=404, detail="Quarantine entry not found")
    return {"message": "Message released", "quarantine_id": quarantine_id}


@router.delete("/quarantine/{quarantine_id}")
async def delete_from_gateway_quarantine(
    quarantine_id: str,
    current_user: dict = Depends(check_permission("write"))
):
    """Delete message from gateway quarantine"""
    success = smtp_gateway.delete_from_quarantine(quarantine_id)
    if not success:
        raise HTTPException(status_code=404, detail="Quarantine entry not found")
    return {"message": "Message deleted", "quarantine_id": quarantine_id}


@router.get("/policies")
async def get_gateway_policies(current_user: dict = Depends(get_current_user)):
    """Get gateway policies"""
    return {"policies": smtp_gateway.get_policies()}


@router.put("/policies/{policy_name}")
async def update_gateway_policy(
    policy_name: str,
    request: UpdatePolicyRequest,
    current_user: dict = Depends(check_permission("admin"))
):
    """Update gateway policy"""
    smtp_gateway.update_policy(policy_name, request.settings)
    return {"message": f"Policy {policy_name} updated"}


@router.post("/blocklist")
async def add_to_blocklist(
    request: BlocklistRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Add to blocklist (sender, domain, or IP)"""
    if request.list_type == "sender":
        smtp_gateway.add_sender_blocklist(request.value)
    elif request.list_type == "domain":
        smtp_gateway.add_domain_blocklist(request.value)
    elif request.list_type == "ip":
        smtp_gateway.add_ip_blocklist(request.value)
    else:
        raise HTTPException(status_code=400, detail="Invalid list_type")
    
    return {"message": f"Added {request.value} to {request.list_type} blocklist"}


@router.delete("/blocklist")
async def remove_from_blocklist(
    value: str,
    list_type: str,
    current_user: dict = Depends(check_permission("write"))
):
    """Remove from blocklist"""
    if list_type == "sender":
        smtp_gateway.sender_blocklist.discard(value.lower())
    elif list_type == "domain":
        smtp_gateway.domain_blocklist.discard(value.lower())
    elif list_type == "ip":
        smtp_gateway.ip_blocklist.discard(value)
    else:
        raise HTTPException(status_code=400, detail="Invalid list_type")
    
    return {"message": f"Removed {value} from {list_type} blocklist"}


@router.post("/allowlist")
async def add_to_allowlist(
    request: BlocklistRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Add to allowlist (sender, domain, or IP)"""
    if request.list_type == "sender":
        smtp_gateway.add_sender_allowlist(request.value)
    elif request.list_type == "domain":
        smtp_gateway.add_domain_allowlist(request.value)
    elif request.list_type == "ip":
        smtp_gateway.add_ip_allowlist(request.value)
    else:
        raise HTTPException(status_code=400, detail="Invalid list_type")
    
    return {"message": f"Added {request.value} to {request.list_type} allowlist"}


@router.get("/blocklist")
async def get_blocklists(current_user: dict = Depends(get_current_user)):
    """Get all blocklists"""
    return {
        "sender_blocklist": list(smtp_gateway.sender_blocklist),
        "domain_blocklist": list(smtp_gateway.domain_blocklist),
        "ip_blocklist": list(smtp_gateway.ip_blocklist)
    }


@router.get("/allowlist")
async def get_allowlists(current_user: dict = Depends(get_current_user)):
    """Get all allowlists"""
    return {
        "sender_allowlist": list(smtp_gateway.sender_allowlist),
        "domain_allowlist": list(smtp_gateway.domain_allowlist),
        "ip_allowlist": list(smtp_gateway.ip_allowlist)
    }
