"""
Email Protection Router - API endpoints for email security
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from pydantic import BaseModel
from dataclasses import asdict

from .dependencies import get_current_user, check_permission
from email_protection import email_protection_service

router = APIRouter(prefix="/email-protection", tags=["Email Protection"])


# Request/Response Models
class AnalyzeEmailRequest(BaseModel):
    sender: str
    recipient: str
    subject: str
    body: str
    headers: Optional[dict] = None
    attachments: Optional[List[dict]] = None
    sender_ip: str = ""


class AnalyzeURLRequest(BaseModel):
    url: str


class AnalyzeAttachmentRequest(BaseModel):
    filename: str
    content_base64: str
    mime_type: str = ""


class CheckAuthenticationRequest(BaseModel):
    domain: str
    sender_ip: str = ""


class DLPAnalysisRequest(BaseModel):
    subject: str
    body: str


class AddProtectedUserRequest(BaseModel):
    email: str
    name: str = ""
    title: str = ""
    user_type: str = "vip"  # vip or executive


class AddBlockedSenderRequest(BaseModel):
    sender: str


class AddTrustedDomainRequest(BaseModel):
    domain: str


@router.get("/stats")
async def get_email_protection_stats(current_user: dict = Depends(get_current_user)):
    """Get email protection statistics"""
    return email_protection_service.get_stats()


@router.post("/analyze")
async def analyze_email(
    request: AnalyzeEmailRequest,
    current_user: dict = Depends(get_current_user)
):
    """Perform comprehensive email threat assessment"""
    import base64
    
    # Process attachments if provided
    attachments = None
    if request.attachments:
        attachments = []
        for att in request.attachments:
            try:
                content = base64.b64decode(att.get('content_base64', ''))
            except Exception:
                content = b''
            attachments.append({
                'filename': att.get('filename', 'unknown'),
                'content': content,
                'mime_type': att.get('mime_type', '')
            })
    
    assessment = email_protection_service.analyze_email(
        sender=request.sender,
        recipient=request.recipient,
        subject=request.subject,
        body=request.body,
        headers=request.headers,
        attachments=attachments,
        sender_ip=request.sender_ip
    )
    
    # Convert to dict for JSON response
    result = asdict(assessment)
    result['overall_risk'] = assessment.overall_risk.value
    result['threat_types'] = [t.value for t in assessment.threat_types]
    
    if assessment.spf_result:
        result['spf_result']['result'] = assessment.spf_result.result.value
    if assessment.dkim_result:
        result['dkim_result']['result'] = assessment.dkim_result.result.value
    if assessment.dmarc_result:
        result['dmarc_result']['result'] = assessment.dmarc_result.result.value
    
    for att in result.get('attachment_analysis', []):
        att['risk_level'] = att['risk_level'].value if isinstance(att['risk_level'], str) == False else att['risk_level']
    
    for url in result.get('url_analysis', []):
        url['risk_level'] = url['risk_level'].value if isinstance(url['risk_level'], str) == False else url['risk_level']
    
    if result.get('dlp_analysis'):
        result['dlp_analysis']['risk_level'] = assessment.dlp_analysis.risk_level.value
    
    return result


@router.post("/analyze-url")
async def analyze_url(
    request: AnalyzeURLRequest,
    current_user: dict = Depends(get_current_user)
):
    """Analyze a URL for threats"""
    analysis = email_protection_service.analyze_url(request.url)
    return {
        **asdict(analysis),
        "risk_level": analysis.risk_level.value
    }


@router.post("/analyze-attachment")
async def analyze_attachment(
    request: AnalyzeAttachmentRequest,
    current_user: dict = Depends(get_current_user)
):
    """Analyze an attachment for threats"""
    import base64
    
    try:
        content = base64.b64decode(request.content_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 content")
    
    analysis = email_protection_service.analyze_attachment(
        filename=request.filename,
        content=content,
        mime_type=request.mime_type
    )
    
    return {
        **asdict(analysis),
        "risk_level": analysis.risk_level.value
    }


@router.post("/check-authentication")
async def check_email_authentication(
    request: CheckAuthenticationRequest,
    current_user: dict = Depends(get_current_user)
):
    """Check SPF/DKIM/DMARC for a domain"""
    spf = email_protection_service.check_spf(request.domain, request.sender_ip)
    dkim = email_protection_service.check_dkim(request.domain)
    dmarc = email_protection_service.check_dmarc(request.domain)
    
    return {
        "domain": request.domain,
        "spf": {
            **asdict(spf),
            "result": spf.result.value
        },
        "dkim": {
            **asdict(dkim),
            "result": dkim.result.value
        },
        "dmarc": {
            **asdict(dmarc),
            "result": dmarc.result.value
        }
    }


@router.post("/check-dlp")
async def check_dlp(
    request: DLPAnalysisRequest,
    current_user: dict = Depends(get_current_user)
):
    """Check content for sensitive data (DLP)"""
    analysis = email_protection_service.analyze_dlp(request.subject, request.body)
    return {
        **asdict(analysis),
        "risk_level": analysis.risk_level.value
    }


@router.get("/quarantine")
async def get_quarantine(current_user: dict = Depends(get_current_user)):
    """Get all quarantined emails"""
    quarantine = email_protection_service.get_quarantine()
    return {"quarantine": quarantine, "count": len(quarantine)}


@router.post("/quarantine/{assessment_id}/release")
async def release_from_quarantine(
    assessment_id: str,
    current_user: dict = Depends(check_permission("write"))
):
    """Release an email from quarantine"""
    success = email_protection_service.release_from_quarantine(assessment_id)
    if not success:
        raise HTTPException(status_code=404, detail="Assessment not found in quarantine")
    return {"message": "Email released from quarantine", "assessment_id": assessment_id}


@router.get("/protected-users")
async def get_protected_users(current_user: dict = Depends(get_current_user)):
    """Get all protected users (VIPs and executives)"""
    return {
        "executives": [
            {"email": email, **info}
            for email, info in email_protection_service.protected_executives.items()
        ],
        "vip_users": list(email_protection_service.vip_users),
        "total": len(email_protection_service.protected_executives) + len(email_protection_service.vip_users)
    }


@router.post("/protected-users")
async def add_protected_user(
    request: AddProtectedUserRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Add a protected user (VIP or executive)"""
    if request.user_type == "executive":
        success = email_protection_service.add_protected_executive(
            request.email, request.name, request.title
        )
        return {"message": f"Executive {request.email} added to protection", "success": success}
    else:
        success = email_protection_service.add_vip_user(request.email)
        return {"message": f"VIP user {request.email} added to protection", "success": success}


@router.delete("/protected-users/{email}")
async def remove_protected_user(
    email: str,
    current_user: dict = Depends(check_permission("write"))
):
    """Remove a protected user"""
    email_lower = email.lower()
    removed = False
    
    if email_lower in email_protection_service.protected_executives:
        del email_protection_service.protected_executives[email_lower]
        removed = True
    if email_lower in email_protection_service.vip_users:
        email_protection_service.vip_users.discard(email_lower)
        removed = True
    
    if not removed:
        raise HTTPException(status_code=404, detail="User not found in protected list")
    
    return {"message": f"User {email} removed from protection"}


@router.get("/blocked-senders")
async def get_blocked_senders(current_user: dict = Depends(get_current_user)):
    """Get all blocked senders"""
    return {
        "blocked_senders": list(email_protection_service.blocked_senders),
        "count": len(email_protection_service.blocked_senders)
    }


@router.post("/blocked-senders")
async def add_blocked_sender(
    request: AddBlockedSenderRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Block a sender"""
    success = email_protection_service.add_blocked_sender(request.sender)
    return {"message": f"Sender {request.sender} blocked", "success": success}


@router.delete("/blocked-senders/{sender}")
async def remove_blocked_sender(
    sender: str,
    current_user: dict = Depends(check_permission("write"))
):
    """Remove a sender from blocklist"""
    sender_lower = sender.lower()
    if sender_lower in email_protection_service.blocked_senders:
        email_protection_service.blocked_senders.discard(sender_lower)
        return {"message": f"Sender {sender} unblocked"}
    raise HTTPException(status_code=404, detail="Sender not in blocklist")


@router.get("/trusted-domains")
async def get_trusted_domains(current_user: dict = Depends(get_current_user)):
    """Get all trusted domains"""
    return {
        "trusted_domains": list(email_protection_service.trusted_domains),
        "count": len(email_protection_service.trusted_domains)
    }


@router.post("/trusted-domains")
async def add_trusted_domain(
    request: AddTrustedDomainRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Add a trusted domain"""
    success = email_protection_service.add_trusted_domain(request.domain)
    return {"message": f"Domain {request.domain} added to trusted list", "success": success}


@router.delete("/trusted-domains/{domain}")
async def remove_trusted_domain(
    domain: str,
    current_user: dict = Depends(check_permission("write"))
):
    """Remove a domain from trusted list"""
    domain_lower = domain.lower()
    if domain_lower in email_protection_service.trusted_domains:
        email_protection_service.trusted_domains.discard(domain_lower)
        return {"message": f"Domain {domain} removed from trusted list"}
    raise HTTPException(status_code=404, detail="Domain not in trusted list")
