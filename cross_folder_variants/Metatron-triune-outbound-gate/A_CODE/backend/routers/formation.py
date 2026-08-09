"""
Formation Router
================
Exposes ARDA's cluster formation verification and manifest management.
Endpoints:
  GET  /api/formation/status   — current formation truth bundle
  POST /api/formation/verify   — trigger full formation verification
  GET  /api/formation/manifest — get the current signed formation manifest
  POST /api/formation/manifest — update/sign a new formation manifest
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Any, Dict, Optional

from .dependencies import get_current_user, check_permission

# Optional cluster services
try:
    from backend.services.cluster_consensus_guard import get_cluster_consensus_guard
except ImportError:
    get_cluster_consensus_guard = None

try:
    from backend.services.cluster_consensus import get_cluster_consensus
except ImportError:
    get_cluster_consensus = None

router = APIRouter(prefix="/formation", tags=["Formation"])


class ManifestUpdateRequest(BaseModel):
    expected_pcr_constraints: Dict[str, str] = {}
    nodes: list = []
    metadata: Dict[str, Any] = {}


@router.get("/status")
async def get_formation_status(current_user: dict = Depends(get_current_user)):
    """Return the current formation truth bundle (last verification result)."""
    try:
        from backend.services.formation_verifier import get_formation_verifier
        verifier = get_formation_verifier()
        truth = verifier.get_truth()
        if truth is None:
            # Dual-module-path singleton may have been populated in a different import
            # context at startup — run verification now so this call always returns data.
            try:
                truth = await verifier.verify_formation()
            except Exception as ve:
                return {"status": "unverified", "message": f"Formation verification failed: {ve}"}
        return truth.model_dump() if hasattr(truth, "model_dump") else vars(truth)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify")
async def run_formation_verify(current_user: dict = Depends(check_permission("write"))):
    """Trigger full hardware-bound formation verification (TPM + Secure Boot + manifest)."""
    try:
        from backend.services.formation_verifier import get_formation_verifier
        verifier = get_formation_verifier()
        bundle = await verifier.verify_formation()
        result = bundle.model_dump() if hasattr(bundle, "model_dump") else vars(bundle)
        result["status_label"] = "lawful" if result.get("status") == "lawful" else "FORMATION_FRACTURED"
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/manifest")
async def get_manifest(current_user: dict = Depends(get_current_user)):
    """Get the current signed formation manifest."""
    try:
        from backend.services.formation_manifest import get_formation_manifest_service
        svc = get_formation_manifest_service()
        manifest = await svc.load_canonical_manifest()
        return manifest.model_dump() if hasattr(manifest, "model_dump") else vars(manifest)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/manifest")
async def update_manifest(
    req: ManifestUpdateRequest,
    current_user: dict = Depends(check_permission("manage_users")),
):
    """Sign and store a new formation manifest."""
    try:
        from backend.services.formation_manifest import get_formation_manifest_service
        svc = get_formation_manifest_service()
        manifest = await svc.create_manifest(
            expected_pcr_constraints=req.expected_pcr_constraints,
            nodes=req.nodes,
            metadata=req.metadata,
        )
        return {
            "status": "signed",
            "manifest_id": manifest.manifest_id if hasattr(manifest, "manifest_id") else "unknown",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cluster/consensus")
async def get_cluster_consensus_status(current_user: dict = Depends(get_current_user)):
    """Get cluster consensus status."""
    if not get_cluster_consensus:
        raise HTTPException(status_code=501, detail="Cluster consensus service not available")
    
    try:
        consensus = get_cluster_consensus()
        status = await consensus.get_status()
        return {
            "success": True,
            "consensus_state": status,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get consensus status: {str(e)}")


@router.post("/cluster/consensus/validate")
async def validate_cluster_consensus(
    cluster_data: dict,
    current_user: dict = Depends(check_permission("read")),
):
    """Validate cluster consensus integrity."""
    if not get_cluster_consensus_guard:
        raise HTTPException(status_code=501, detail="Cluster consensus guard not available")
    
    try:
        guard = get_cluster_consensus_guard()
        validation = await guard.validate(cluster_data)
        return {
            "success": True,
            "valid": validation.get("valid", False),
            "details": validation,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Consensus validation failed: {str(e)}")
