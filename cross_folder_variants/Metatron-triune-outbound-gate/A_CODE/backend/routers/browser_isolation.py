"""
Browser Isolation Router - Secure remote browsing
"""
import asyncio
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from typing import Optional, List
from pydantic import BaseModel

from .dependencies import get_current_user, check_permission
from browser_isolation import browser_isolation_service, BrowserIsolationService

router = APIRouter(prefix="/browser-isolation", tags=["Browser Isolation"])


class CreateSessionRequest(BaseModel):
    url: str
    isolation_mode: str = "full"  # full, cdr, read_only, pixel_push


class AnalyzeURLRequest(BaseModel):
    url: str


class SanitizeHTMLRequest(BaseModel):
    html_content: str


class BlockDomainRequest(BaseModel):
    domain: str


@router.get("/stats")
async def get_isolation_stats(current_user: dict = Depends(get_current_user)):
    """Get browser isolation statistics"""
    return browser_isolation_service.get_stats()


@router.get("/sessions")
async def get_active_sessions(current_user: dict = Depends(get_current_user)):
    """Get active isolated browsing sessions"""
    sessions = browser_isolation_service.get_active_sessions(
        user_id=current_user.get("email")
    )
    return {"sessions": sessions, "count": len(sessions)}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """Get details of a specific session"""
    session = browser_isolation_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/sessions/{session_id}/stream-info")
async def get_session_stream_info(session_id: str, current_user: dict = Depends(get_current_user)):
    """Get stream metadata for a browser isolation session"""
    session = browser_isolation_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session_id,
        "isolation_mode": session.get("isolation_mode"),
        "stream_type": "pixel_websocket",
        "stream_path": f"/api/browser-isolation/ws/stream/{session_id}",
        "fps": 2,
    }


@router.get("/sessions/{session_id}/frame")
async def get_session_stream_frame(session_id: str, current_user: dict = Depends(get_current_user)):
    """Get a single pixel frame (polling fallback transport)."""
    frame = browser_isolation_service.get_stream_frame(session_id)
    if not frame:
        raise HTTPException(status_code=404, detail="Session not found")
    return frame


@router.post("/sessions")
async def create_isolated_session(
    request: CreateSessionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a new isolated browsing session"""
    result = browser_isolation_service.create_session(
        user_id=current_user.get("email", "anonymous"),
        url=request.url,
        isolation_mode=request.isolation_mode
    )
    return result


@router.delete("/sessions/{session_id}")
async def end_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """End an isolated browsing session"""
    success = browser_isolation_service.end_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session ended", "session_id": session_id}


@router.post("/analyze-url")
async def analyze_url(
    request: AnalyzeURLRequest,
    current_user: dict = Depends(get_current_user)
):
    """Analyze a URL for threats before browsing"""
    analysis = browser_isolation_service.analyze_url(request.url)
    return {
        "url": analysis.url,
        "domain": analysis.domain,
        "threat_level": analysis.threat_level.value,
        "category": analysis.category,
        "is_blocked": analysis.is_blocked,
        "reasons": analysis.reasons,
        "safe_url": analysis.safe_url
    }


@router.post("/sanitize")
async def sanitize_html(
    request: SanitizeHTMLRequest,
    current_user: dict = Depends(get_current_user)
):
    """Sanitize HTML content (Content Disarm & Reconstruction)"""
    result = browser_isolation_service.sanitize_html(request.html_content)
    return result


@router.get("/blocked-domains")
async def get_blocked_domains(current_user: dict = Depends(get_current_user)):
    """Get list of blocked domains"""
    domains = browser_isolation_service.get_blocked_domains()
    return {"domains": domains, "count": len(domains)}


@router.post("/blocked-domains")
async def add_blocked_domain(
    request: BlockDomainRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Add a domain to the blocklist"""
    success = browser_isolation_service.add_blocked_domain(request.domain)
    if success:
        return {"message": f"Domain {request.domain} added to blocklist"}
    raise HTTPException(status_code=400, detail="Invalid domain")


@router.delete("/blocked-domains/{domain}")
async def remove_blocked_domain(
    domain: str,
    current_user: dict = Depends(check_permission("write"))
):
    """Remove a domain from the blocklist"""
    success = browser_isolation_service.remove_blocked_domain(domain)
    if success:
        return {"message": f"Domain {domain} removed from blocklist"}
    raise HTTPException(status_code=404, detail="Domain not in blocklist")


@router.get("/modes")
async def get_isolation_modes(current_user: dict = Depends(get_current_user)):
    """Get available isolation modes"""
    return {
        "modes": [
            {
                "id": "full",
                "name": "Full Isolation",
                "description": "Complete remote rendering in isolated VM"
            },
            {
                "id": "cdr",
                "name": "Content Disarm & Reconstruction",
                "description": "Removes active content, reconstructs safe document"
            },
            {
                "id": "read_only",
                "name": "Read-Only Mode",
                "description": "View content without any interaction capability"
            },
            {
                "id": "pixel_push",
                "name": "Pixel Streaming",
                "description": "Stream rendered content as pixels (maximum isolation)"
            }
        ]
    }


@router.websocket("/ws/stream/{session_id}")
async def stream_isolated_session(websocket: WebSocket, session_id: str):
    """Pixel stream transport for browser isolation sessions"""
    await websocket.accept()
    try:
        while True:
            frame = browser_isolation_service.get_stream_frame(session_id)
            if not frame:
                await websocket.send_json({"type": "error", "error": "session_not_found"})
                return

            await websocket.send_json(frame)
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        return
