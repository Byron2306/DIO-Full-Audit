"""
Platform Sovereignty Router
============================
Exposes the ARDA WorldManifold (cross-platform attestation + sovereignty)
via the Seraph REST API.

Endpoints:
  GET  /api/platform/summary          — platform capabilities + provider info
  GET  /api/platform/sovereignty      — current sovereignty state (5-layer)
  GET  /api/platform/pcrs             — TPM PCR snapshot (Linux tpm2-tools / Windows PowerShell)
  GET  /api/platform/secure-boot      — Secure Boot state
  GET  /api/platform/boot-log         — IMA/Measured Boot event log (last 100 entries)
  POST /api/platform/apply-posture    — apply enforcement posture to a node
  GET  /api/platform/evidence/{ainur} — collect evidence from a named Ainur collector
                                        ainur: varda | ulmo | manwe | mandos
"""
from __future__ import annotations

import logging
import sys
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .dependencies import check_permission, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/platform", tags=["Platform Sovereignty"])

# ---------------------------------------------------------------------------
# Bootstrap WorldManifold once per process (thread-safe singleton via lru_cache)
# ---------------------------------------------------------------------------

def _arda_windows_src() -> str:
    """Return the absolute path to the arda_windows src/ directory.

    Search order:
      1. backend/arda_windows/ copy (present when running inside Docker container)
      2. project_root/Arda Windows/src/ (local dev layout)
    """
    here = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(here)
    # Inside the container, arda_windows is copied into backend/
    if os.path.isdir(os.path.join(backend_dir, "arda_windows")):
        return backend_dir
    # Local dev: backend/routers/ → backend/ → project root → Arda Windows/src
    project_root = os.path.dirname(backend_dir)
    return os.path.join(project_root, "Arda Windows", "src")


@lru_cache(maxsize=1)
def _get_manifold():
    src_path = _arda_windows_src()
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    try:
        from arda_windows.world_manifold import WorldManifold
        arkime_url = os.environ.get("ARKIME_ES_URL", "")
        manifold = WorldManifold.build(arkime_es_url=arkime_url if arkime_url else None)
        logger.info("WorldManifold initialised: platform=%s", manifold.capabilities.platform)
        return manifold
    except Exception as exc:
        logger.error("WorldManifold init failed: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class PostureRequest(BaseModel):
    node_id: str
    posture: str  # enforce | audit | quarantine | off
    verdict: Dict[str, Any] = {}


class WorkloadRequest(BaseModel):
    id: str
    remote_addr: Optional[str] = None
    label: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/summary")
async def platform_summary(
    current_user: dict = Depends(get_current_user),
):
    """Return platform capabilities and provider information."""
    try:
        manifold = _get_manifold()
        return manifold.platform_summary()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/sovereignty")
async def sovereignty_state(
    current_user: dict = Depends(get_current_user),
):
    """Evaluate the current sovereignty state across all trust layers."""
    try:
        manifold = _get_manifold()
        assessment = manifold.sovereignty.evaluate_sovereignty_state()
        reasons = manifold.sovereignty.explain_state_reasons()
        return {
            "state": assessment.state,
            "provider": assessment.provider,
            "reasons": reasons,
            "attributes": assessment.attributes,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/pcrs")
async def pcr_snapshot(
    indices: str = "0,1,4,7",
    current_user: dict = Depends(get_current_user),
):
    """
    Read TPM PCR values for the given comma-separated indices.
    Example: GET /api/platform/pcrs?indices=0,4,7
    """
    try:
        idx_list = [int(i.strip()) for i in indices.split(",") if i.strip().isdigit()]
        manifold = _get_manifold()
        snapshots = manifold.attestation.get_pcr_snapshot(idx_list)
        return {
            "platform": manifold.capabilities.platform,
            "pcrs": [{"index": p.index, "value": p.value} for p in snapshots],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/secure-boot")
async def secure_boot_state(
    current_user: dict = Depends(get_current_user),
):
    """Return the current Secure Boot state."""
    try:
        manifold = _get_manifold()
        state = manifold.attestation.get_secure_boot_state()
        return {
            "enabled": state.enabled,
            "setup_mode": state.setup_mode,
            "secure_boot_mode": state.secure_boot_mode,
            "vendor_keys": state.vendor_keys,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/boot-log")
async def boot_event_log(
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
):
    """Return measured boot / IMA event log entries."""
    try:
        manifold = _get_manifold()
        events = manifold.attestation.get_boot_event_log()
        capped = events[:max(1, min(limit, 500))]
        return {
            "total": len(events),
            "returned": len(capped),
            "events": [
                {
                    "pcr_index": e.pcr_index,
                    "event_type": e.event_type,
                    "digest": e.digest,
                    "event_data": e.event_data,
                    "timestamp_iso": e.timestamp_iso,
                }
                for e in capped
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/apply-posture")
async def apply_posture(
    req: PostureRequest,
    current_user: dict = Depends(check_permission("write")),
):
    """
    Apply an enforcement posture to a node.
    Requires 'write' permission. Posture: enforce | audit | quarantine | off.
    """
    allowed_postures = {"enforce", "audit", "quarantine", "off"}
    if req.posture not in allowed_postures:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid posture '{req.posture}'. Allowed: {sorted(allowed_postures)}",
        )
    try:
        manifold = _get_manifold()
        result = manifold.enforcement.apply_posture(req.node_id, req.posture, req.verdict)
        return {
            "success": result.success,
            "posture": result.posture,
            "provider": result.provider,
            "actions": result.actions,
            "details": result.details,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/trust-workload")
async def trust_workload(
    req: WorkloadRequest,
    current_user: dict = Depends(check_permission("write")),
):
    """Mark a workload identity as trusted."""
    try:
        manifold = _get_manifold()
        result = manifold.enforcement.trust_workload(req.model_dump())
        return {
            "success": result.success,
            "provider": result.provider,
            "actions": result.actions,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/distrust-workload")
async def distrust_workload(
    req: WorkloadRequest,
    current_user: dict = Depends(check_permission("write")),
):
    """Mark a workload identity as distrusted / blocked."""
    try:
        manifold = _get_manifold()
        result = manifold.enforcement.distrust_workload(req.model_dump())
        return {
            "success": result.success,
            "provider": result.provider,
            "actions": result.actions,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


_AINUR_COLLECTORS = {"varda", "ulmo", "manwe", "mandos"}


@router.get("/evidence/{ainur}")
async def collect_evidence(
    ainur: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Collect evidence from a named Ainur telemetry source.
    ainur: varda (file/registry) | ulmo (network) | manwe (process) | mandos (threat/AV)
    """
    if ainur not in _AINUR_COLLECTORS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown Ainur '{ainur}'. Valid: {sorted(_AINUR_COLLECTORS)}",
        )
    try:
        manifold = _get_manifold()
        collector = getattr(manifold.evidence, f"collect_{ainur}_evidence")
        packet = collector({})
        return {
            "source": packet.source,
            "confidence": packet.confidence,
            "sweep_id": packet.sweep_id,
            "evidence": packet.evidence,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
