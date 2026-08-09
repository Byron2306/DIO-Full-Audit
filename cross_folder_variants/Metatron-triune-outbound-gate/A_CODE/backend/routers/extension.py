"""
Browser Extension API Router
Handles communication with the Seraph AI Browser Defender extension
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import logging
import os
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/extension", tags=["Browser Extension"])

# Known malicious domains (in production, this would be a database)
MALICIOUS_DOMAINS = {
    "malware-site.com": "Known malware distribution",
    "phishing-example.tk": "Phishing site",
    "cryptominer.ml": "Cryptojacking site",
    "c2-server.onion": "Command and control server",
}

# Suspicious domain patterns
SUSPICIOUS_PATTERNS = [
    ".onion",
    ".bit",
    "dyndns.",
    "no-ip.",
    ".tk",
    ".ml",
    ".ga",
    ".cf",
    "ngrok.io",
]

# In-memory alert storage (in production, use MongoDB)
extension_alerts: List[Dict[str, Any]] = []
blocked_domains: Dict[str, int] = {}


class DomainCheckRequest(BaseModel):
    domain: str


class DomainCheckResponse(BaseModel):
    domain: str
    is_malicious: bool
    reason: Optional[str] = None
    risk_score: int = 0


class AlertReport(BaseModel):
    alerts: List[Dict[str, Any]]


class AlertReportResponse(BaseModel):
    received: int
    processed: int


@router.post("/check-domain", response_model=DomainCheckResponse)
async def check_domain(request: DomainCheckRequest):
    """Check if a domain is known to be malicious"""
    domain = request.domain.lower().strip()
    
    # Check against known malicious domains
    if domain in MALICIOUS_DOMAINS:
        return DomainCheckResponse(
            domain=domain,
            is_malicious=True,
            reason=MALICIOUS_DOMAINS[domain],
            risk_score=100
        )
    
    # Check against suspicious patterns
    for pattern in SUSPICIOUS_PATTERNS:
        if pattern in domain:
            return DomainCheckResponse(
                domain=domain,
                is_malicious=True,
                reason=f"Suspicious domain pattern: {pattern}",
                risk_score=80
            )
    
    # Domain appears safe
    return DomainCheckResponse(
        domain=domain,
        is_malicious=False,
        reason=None,
        risk_score=0
    )


@router.post("/report-alerts", response_model=AlertReportResponse)
async def report_alerts(report: AlertReport):
    """Receive alert reports from browser extensions"""
    global extension_alerts
    
    processed = 0
    for alert in report.alerts:
        alert["received_at"] = datetime.now(timezone.utc).isoformat()
        alert["source"] = "browser_extension"
        extension_alerts.append(alert)
        processed += 1
        
        # Track blocked domains
        if alert.get("type") == "blocked_navigation":
            domain = alert.get("domain", "unknown")
            blocked_domains[domain] = blocked_domains.get(domain, 0) + 1
    
    # Keep only last 10000 alerts
    if len(extension_alerts) > 10000:
        extension_alerts = extension_alerts[-10000:]
    
    logger.info(f"Received {processed} alerts from browser extension")
    
    return AlertReportResponse(
        received=len(report.alerts),
        processed=processed
    )


@router.get("/alerts")
async def get_extension_alerts(limit: int = 100):
    """Get recent alerts from browser extensions"""
    return {
        "alerts": extension_alerts[-limit:],
        "total": len(extension_alerts),
        "blocked_domains": blocked_domains
    }


@router.get("/stats")
async def get_extension_stats():
    """Get browser extension statistics"""
    return {
        "total_alerts": len(extension_alerts),
        "blocked_domains_count": len(blocked_domains),
        "top_blocked_domains": sorted(
            blocked_domains.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10],
        "alert_types": _count_alert_types()
    }


def _count_alert_types():
    """Count alerts by type"""
    type_counts = {}
    for alert in extension_alerts:
        alert_type = alert.get("type", "unknown")
        type_counts[alert_type] = type_counts.get(alert_type, 0) + 1
    return type_counts


def _extension_candidates() -> list[Path]:
    return [
        Path("/app/frontend/public/downloads/seraph-extension.zip"),
        Path("/app/backend/frontend/public/downloads/seraph-extension.zip"),
        Path("/workspace/frontend/public/downloads/seraph-extension.zip"),
        Path.cwd() / "frontend/public/downloads/seraph-extension.zip",
    ]


def _extension_source_dirs() -> list[Path]:
    return [
        Path("/app/frontend/public/downloads/seraph-extension"),
        Path("/app/backend/frontend/public/downloads/seraph-extension"),
        Path("/workspace/frontend/public/downloads/seraph-extension"),
        Path.cwd() / "frontend/public/downloads/seraph-extension",
    ]


def _build_zip_if_needed(zip_path: Path) -> bool:
    if zip_path.exists():
        return True

    src_dir = next((d for d in _extension_source_dirs() if d.exists() and d.is_dir()), None)
    if src_dir is None:
        return False

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in src_dir.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(src_dir))

    return zip_path.exists()


@router.get("/download")
async def download_extension():
    """Download the browser extension zip file"""
    for candidate in _extension_candidates():
        if candidate.exists() or _build_zip_if_needed(candidate):
            return FileResponse(
                path=str(candidate),
                filename="seraph-extension.zip",
                media_type="application/zip",
            )

    raise HTTPException(
        status_code=404,
        detail="Extension package not found. Expected a ZIP or source folder under frontend/public/downloads/seraph-extension.",
    )


@router.post("/add-malicious-domain")
async def add_malicious_domain(domain: str, reason: str):
    """Add a domain to the malicious list (admin only)"""
    MALICIOUS_DOMAINS[domain.lower().strip()] = reason
    return {"status": "added", "domain": domain}


@router.delete("/remove-malicious-domain")
async def remove_malicious_domain(domain: str):
    """Remove a domain from the malicious list (admin only)"""
    domain = domain.lower().strip()
    if domain in MALICIOUS_DOMAINS:
        del MALICIOUS_DOMAINS[domain]
        return {"status": "removed", "domain": domain}
    raise HTTPException(status_code=404, detail="Domain not found")
