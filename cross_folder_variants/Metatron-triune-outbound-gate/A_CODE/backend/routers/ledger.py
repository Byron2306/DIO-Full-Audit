"""
Ledger and Evidence Router
===========================
Exposes ledger, evidence management, and cryptographic validation endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, Dict, Any, List

from .dependencies import get_current_user, check_permission, get_db

# Optional ledger and evidence services
try:
    from services.document_evidence import DocumentEvidence
except ImportError:
    DocumentEvidence = None

try:
    from services.signed_manifest_validator import SignedManifestValidator
except ImportError:
    SignedManifestValidator = None

try:
    from services.ipsative_ledger import IpsativeLedger
except ImportError:
    IpsativeLedger = None

try:
    from services.heartbeat_signer import HeartbeatSigner
except ImportError:
    HeartbeatSigner = None

try:
    from services.heartbeat_verifier import HeartbeatVerifier
except ImportError:
    HeartbeatVerifier = None

try:
    from services.metatron_heartbeat import MetatronHeartbeat
except ImportError:
    MetatronHeartbeat = None

router = APIRouter(prefix="/ledger", tags=["Ledger"])


@router.post("/evidence/document")
async def document_evidence(
    evidence_type: str,
    content: Dict[str, Any],
    current_user: dict = Depends(check_permission("write")),
):
    """Document evidence in the ledger."""
    if not DocumentEvidence:
        raise HTTPException(status_code=501, detail="Document evidence service not available")
    
    try:
        service = DocumentEvidence()
        evidence = await service.document(evidence_type, content)
        return {
            "success": True,
            "evidence_id": evidence.get("id"),
            "timestamp": evidence.get("timestamp"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to document evidence: {str(e)}")


@router.post("/manifest/validate")
async def validate_signed_manifest(
    manifest: Dict[str, Any],
    current_user: dict = Depends(check_permission("read")),
):
    """Validate a cryptographically signed manifest."""
    if not SignedManifestValidator:
        raise HTTPException(status_code=501, detail="Manifest validator not available")
    
    try:
        validator = SignedManifestValidator()
        validation = await validator.validate(manifest)
        return {
            "success": True,
            "valid": validation.get("valid", False),
            "signature_verified": validation.get("signature_verified", False),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.get("/ipsative/query")
async def query_ipsative_ledger(
    query: str,
    current_user: dict = Depends(get_current_user),
):
    """Query the ipsative ledger."""
    if not IpsativeLedger:
        raise HTTPException(status_code=501, detail="Ipsative ledger not available")
    
    try:
        ledger = IpsativeLedger()
        results = await ledger.query(query)
        return {
            "success": True,
            "query": query,
            "results": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.post("/heartbeat/sign")
async def sign_heartbeat(
    heartbeat_data: Dict[str, Any],
    current_user: dict = Depends(check_permission("write")),
):
    """Sign a heartbeat message."""
    if not HeartbeatSigner:
        raise HTTPException(status_code=501, detail="Heartbeat signer not available")
    
    try:
        signer = HeartbeatSigner()
        signed = await signer.sign(heartbeat_data)
        return {
            "success": True,
            "signed_heartbeat_id": signed.get("id"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signing failed: {str(e)}")


@router.post("/heartbeat/verify")
async def verify_heartbeat(
    signed_heartbeat: Dict[str, Any],
    current_user: dict = Depends(check_permission("read")),
):
    """Verify a signed heartbeat."""
    if not HeartbeatVerifier:
        raise HTTPException(status_code=501, detail="Heartbeat verifier not available")
    
    try:
        verifier = HeartbeatVerifier()
        verification = await verifier.verify(signed_heartbeat)
        return {
            "success": True,
            "verified": verification.get("verified", False),
            "signer": verification.get("signer"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@router.get("/metatron/heartbeat/status")
async def get_metatron_heartbeat_status(
    current_user: dict = Depends(get_current_user),
):
    """Get Metatron system heartbeat status."""
    if not MetatronHeartbeat:
        raise HTTPException(status_code=501, detail="Metatron heartbeat service not available")
    
    try:
        heartbeat = MetatronHeartbeat()
        status = await heartbeat.get_status()
        return {
            "success": True,
            "heartbeat_status": status,
            "alive": status.get("alive", False),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")
