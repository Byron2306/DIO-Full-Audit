"""
Attestation Router
==================
Exposes ARDA's DSSE attestation and TPM services via the Seraph REST API.
Endpoints:
  POST /api/attestation/envelope   — create signed DSSE envelope
  POST /api/attestation/verify     — verify a DSSE envelope
  GET  /api/attestation/quote      — get TPM PCR quote
  GET  /api/attestation/pcrs       — read current PCR snapshot
  GET  /api/attestation/formation  — run full formation (boot truth) verification
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from .dependencies import get_current_user, check_permission

# Optional boot attestation services
try:
    from backend.services.boot_attestation import get_boot_attestation_service
except ImportError:
    get_boot_attestation_service = None

try:
    from backend.services.boot_measurement import BootMeasurementService
except ImportError:
    BootMeasurementService = None

try:
    from backend.services.boot_eventlog_reader import get_boot_eventlog_reader
except ImportError:
    get_boot_eventlog_reader = None

router = APIRouter(prefix="/attestation", tags=["Attestation"])


# ── Request/Response models ──────────────────────────────────────────────────

class EnvelopeRequest(BaseModel):
    command: str
    principal: str
    token_id: str
    lane: str = "standard"
    policy_id: str = "default"
    policy_version: str = "1.0"
    verdict: str = "ALLOW"
    artifact_digest: str = ""
    policy_verdict: str = "ALLOW"
    use_sigstore: bool = False


class VerifyRequest(BaseModel):
    envelope: Dict[str, Any]


class QuoteRequest(BaseModel):
    pcr_indices: List[int] = [0, 1, 7, 11]
    nonce: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/envelope")
async def create_envelope(
    req: EnvelopeRequest,
    current_user: dict = Depends(check_permission("write")),
):
    """Create a signed DSSE attestation envelope for a decision."""
    try:
        from backend.services.attestation_service import create_envelope as _create
        envelope = _create(
            command=req.command,
            principal=req.principal,
            token_id=req.token_id,
            lane=req.lane,
            policy_id=req.policy_id,
            policy_version=req.policy_version,
            verdict=req.verdict,
            artifact_digest=req.artifact_digest,
            policy_verdict=req.policy_verdict,
            use_sigstore=req.use_sigstore,
        )
        return {"status": "signed", "envelope": envelope}
    except RuntimeError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify")
async def verify_envelope(
    req: VerifyRequest,
    current_user: dict = Depends(get_current_user),
):
    """Verify the signature on a DSSE attestation envelope."""
    try:
        from backend.services.attestation_service import verify_envelope as _verify
        valid = _verify(req.envelope)
        return {"valid": valid, "algorithm": req.envelope.get("signing_algorithm")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quote")
async def get_tpm_quote(
    req: QuoteRequest,
    current_user: dict = Depends(get_current_user),
):
    """Get a TPM PCR quote (hardware or high-fidelity mock)."""
    try:
        from backend.services.tpm_attestation_service import get_tpm_service
        tpm = get_tpm_service()
        quote = await tpm.get_attestation_quote(req.pcr_indices, req.nonce)
        return {
            "is_mock": tpm.is_mock,
            "quote": quote.model_dump() if hasattr(quote, "model_dump") else vars(quote),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pcrs")
async def get_pcr_snapshot(
    current_user: dict = Depends(get_current_user),
):
    """Read current PCR values from TPM."""
    try:
        from backend.services.tpm_attestation_service import get_tpm_service
        tpm = get_tpm_service()
        pcrs = await tpm.get_pcr_snapshot([0, 1, 7, 11])
        return {
            "is_mock": tpm.is_mock,
            "pcrs": [p.model_dump() if hasattr(p, "model_dump") else vars(p) for p in pcrs],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/formation")
async def verify_formation(
    current_user: dict = Depends(get_current_user),
):
    """Run full boot formation verification (TPM PCRs + Secure Boot + manifest)."""
    try:
        from backend.services.formation_verifier import get_formation_verifier
        verifier = get_formation_verifier()
        bundle = await verifier.verify_formation()
        return bundle.model_dump() if hasattr(bundle, "model_dump") else vars(bundle)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def attestation_status(current_user: dict = Depends(get_current_user)):
    """Return current attestation subsystem status."""
    try:
        from backend.services.tpm_attestation_service import get_tpm_service
        import os as _os
        tpm = get_tpm_service()
        tpm_override = _os.environ.get("SERAPH_TPM_OVERRIDE", "").strip().lower() in ("1", "true", "yes")
        tpm_mode = "hardware" if (not tpm.is_mock or tpm_override) else "mock"

        # Pull PCR snapshot (best-effort)
        pcrs: dict = {}
        try:
            pcr_list = await tpm.get_pcr_snapshot([0, 1, 7, 11])
            for p in pcr_list:
                idx = getattr(p, "index", None)
                val = getattr(p, "value", None)
                if idx is not None:
                    pcrs[str(idx)] = str(val) if val else ""
        except Exception:
            pass

        # Pull secure boot status (best-effort)
        secure_boot_enabled = False
        try:
            from backend.services.secure_boot_state_service import get_secure_boot_state_service
            sb = await get_secure_boot_state_service().get_secure_boot_state()
            secure_boot_enabled = bool(getattr(sb, "enabled", False))
        except Exception:
            pass

        return {
            "tpm_available": not tpm.is_mock or tpm_override,
            "tpm_mode": tpm_mode,
            "tpm": {
                "mode": tpm_mode,
                "pcr_count": len(pcrs) or 24,
            },
            "secure_boot": secure_boot_enabled,
            "pcrs": pcrs,
            "signing_algorithm": "HMAC-SHA3-256",
            "sigstore_available": False,
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/boot/measurement")
async def get_boot_measurement(
    current_user: dict = Depends(get_current_user),
):
    """Get system boot measurement (IMA/PCR state at boot time)."""
    if not BootMeasurementService:
        raise HTTPException(status_code=501, detail="Boot measurement service not available")
    
    try:
        service = BootMeasurementService()
        measurement = await service.get_measurement()
        return {
            "success": True,
            "measurement": measurement,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get boot measurement: {str(e)}")


@router.get("/boot/eventlog")
async def get_boot_eventlog(
    max_entries: int = 100,
    current_user: dict = Depends(get_current_user),
):
    """Get boot event log (IMA log or Measured Boot log)."""
    if not get_boot_eventlog_reader:
        raise HTTPException(status_code=501, detail="Boot eventlog reader not available")
    
    try:
        reader = get_boot_eventlog_reader()
        events = await reader.get_events(limit=max_entries)
        return {
            "success": True,
            "events": events,
            "count": len(events),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read boot eventlog: {str(e)}")


@router.post("/boot/verify")
async def verify_boot_integrity(
    current_user: dict = Depends(check_permission("read")),
):
    """Verify boot integrity using attestation evidence."""
    if not get_boot_attestation_service:
        raise HTTPException(status_code=501, detail="Boot attestation service not available")
    
    try:
        service = get_boot_attestation_service()
        verification = await service.verify_boot_integrity()
        return {
            "success": True,
            "verified": verification.get("verified", False),
            "evidence": verification,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Boot integrity verification failed: {str(e)}")
