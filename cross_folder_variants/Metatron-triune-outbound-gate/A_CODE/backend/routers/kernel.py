"""
Kernel Enforcement Router
=========================
Exposes ARDA's BPF LSM kernel enforcement layer controls.
The LSM must be loaded via bpf/build.sh --load (requires root + kernel 5.7+).

Sensor telemetry endpoints (sensors, events, capabilities) are handled by
the kernel_sensors.py router at /api/v1/kernel.

Endpoints:
  GET  /api/v1/kernel/status                       — LSM state (armed/mock/unavailable)
  POST /api/v1/kernel/workload/trust                — mark executable as harmonic (trusted)
  POST /api/v1/kernel/workload/distrust             — mark executable as fallen (blocked)
  GET  /api/v1/kernel/enforcement                   — get enforcement toggle state
  POST /api/v1/kernel/enforcement/{state}           — enable/disable enforcement (on/off)
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from .dependencies import get_current_user, check_permission

router = APIRouter(prefix="/kernel", tags=["Kernel Enforcement"])

def _loader_container_name() -> str:
    import os
    return (os.environ.get("ARDA_LSM_CONTAINER_NAME") or "arda-lsm-loader").strip() or "arda-lsm-loader"


def _docker_container_running(name: str) -> bool:
    import subprocess
    try:
        out = subprocess.check_output(
            ["docker", "inspect", "--format", "{{.State.Running}}", name],
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).decode().strip()
        return out.lower() == "true"
    except Exception:
        return False


def _find_arda_state_map_id_via_loader(name: str) -> Optional[int]:
    """
    Use bpftool inside the loader container to locate the arda_state_map id.
    Returns None if unavailable.
    """
    import subprocess
    try:
        proc = subprocess.run(
            ["docker", "exec", name, "bpftool", "map", "show"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
        if proc.returncode != 0:
            return None
        for line in (proc.stdout or "").splitlines():
            lo = line.lower()
            if "arda_state" in lo and "map" in lo:
                # Typical: "123: hash  name arda_state_map  flags 0x0"
                head = line.split(":", 1)[0].strip()
                try:
                    return int(head)
                except ValueError:
                    continue
        return None
    except Exception:
        return None


def _parse_u32_state_map_dump(raw: str) -> Optional[bool]:
    """
    Parse `bpftool -j map dump id <id>` output for key=0, value=0/1.
    """
    import json
    import re

    try:
        records = json.loads(raw)
        if isinstance(records, list):
            for rec in records:
                if not isinstance(rec, dict):
                    continue
                k = rec.get("key")
                v = rec.get("value")
                if k == 0:
                    return bool(v == 1)
                # Some bpftool versions emit hex arrays
                if isinstance(k, list) and k and str(k[0]).lower() in ("0x00", "0"):
                    if isinstance(v, list) and v:
                        return bool(str(v[0]).lower() in ("0x01", "1"))
    except Exception:
        pass

    # Fallback regex for hex array format
    try:
        key0_value1 = re.search(r'"key"\s*:\s*\[\s*"0x00"\s*\].*?"value"\s*:\s*\[\s*"0x01"\s*\]', raw, re.DOTALL)
        key0_value0 = re.search(r'"key"\s*:\s*\[\s*"0x00"\s*\].*?"value"\s*:\s*\[\s*"0x00"\s*\]', raw, re.DOTALL)
        if key0_value1:
            return True
        if key0_value0:
            return False
    except Exception:
        pass

    return None


def _get_enforcement_via_loader() -> Optional[dict]:
    """
    Best-effort read of enforcement state via the privileged loader container.
    Returns a dict suitable for the API response, or None if not available.
    """
    import subprocess
    name = _loader_container_name()
    if not _docker_container_running(name):
        return None
    map_id = _find_arda_state_map_id_via_loader(name)
    if not map_id:
        return None
    try:
        proc = subprocess.run(
            ["docker", "exec", name, "bpftool", "-j", "map", "dump", "id", str(map_id)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
        if proc.returncode != 0:
            return None
        parsed = _parse_u32_state_map_dump(proc.stdout or "")
        if parsed is None:
            return None
        return {
            "enforcement": bool(parsed),
            "is_authoritative": False,
            "source": "loader_container",
            "loader_container": name,
            "state_map_id": map_id,
        }
    except Exception:
        return None


def _set_enforcement_via_loader(enabled: bool) -> Optional[dict]:
    """
    Best-effort enforcement toggle via the loader container (bpftool map update).
    Returns API response dict, or None if not available.
    """
    import subprocess
    name = _loader_container_name()
    if not _docker_container_running(name):
        return None
    map_id = _find_arda_state_map_id_via_loader(name)
    if not map_id:
        return None
    val = "01" if enabled else "00"
    try:
        proc = subprocess.run(
            [
                "docker", "exec", name, "bpftool", "map", "update", "id", str(map_id),
                "key", "hex", "00", "00", "00", "00",
                "value", "hex", val, "00", "00", "00",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
        if proc.returncode != 0:
            return None
        # Read-back for confirmation
        return _get_enforcement_via_loader()
    except Exception:
        return None


class WorkloadTrustRequest(BaseModel):
    executable_path: str
    quantum_signature: Optional[dict] = None


class WorkloadDistrustRequest(BaseModel):
    executable_path: str


@router.get("/status")
async def get_kernel_status(current_user: dict = Depends(get_current_user)):
    """Return BPF LSM enforcement status."""
    import os as _os
    try:
        from services.os_enforcement_service import get_os_enforcement_service
        svc = get_os_enforcement_service()
        # Operator override: SERAPH_KERNEL_ENABLED=true reports sensor as active
        kernel_override = _os.environ.get("SERAPH_KERNEL_ENABLED", "").strip().lower() in ("1", "true", "yes")
        is_auth = bool(svc.is_authoritative)
        effective_mode = "ring0_armed" if (is_auth or kernel_override) else "simulation"
        return {
            "is_authoritative": is_auth,
            "mode": effective_mode,
            "operator_override": kernel_override,
            "mode_source": "authoritative" if is_auth else ("operator_override" if kernel_override else "simulation"),
            "bpf_source": getattr(svc, "bpf_source", None),
            "sovereign_mode": _os.environ.get("ARDA_SOVEREIGN_MODE", "0") == "1",
            "trusted_workloads": len(svc.lsm_map) if isinstance(svc.lsm_map, dict) else "hardware_map",
        }
    except Exception as e:
        return {"is_authoritative": False, "mode": "unavailable", "error": str(e)}


@router.post("/workload/trust")
async def trust_workload(
    req: WorkloadTrustRequest,
    current_user: dict = Depends(check_permission("manage_users")),
):
    """Mark an executable as harmonic (allowed) in the BPF LSM map."""
    try:
        from services.os_enforcement_service import get_os_enforcement_service
        svc = get_os_enforcement_service()
        result = svc.update_workload_harmony(
            executable_path=req.executable_path,
            is_harmonic=True,
            quantum_signature=req.quantum_signature,
        )
        if result is False:
            raise HTTPException(status_code=403, detail="BPF harmony update vetoed — check quantum signature and manifest")
        return {"status": "harmonic", "executable": req.executable_path}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workload/distrust")
async def distrust_workload(
    req: WorkloadDistrustRequest,
    current_user: dict = Depends(check_permission("manage_users")),
):
    """Mark an executable as fallen (blocked) in the BPF LSM map."""
    try:
        from services.os_enforcement_service import get_os_enforcement_service
        svc = get_os_enforcement_service()
        svc.update_workload_harmony(
            executable_path=req.executable_path,
            is_harmonic=False,
        )
        return {"status": "fallen", "executable": req.executable_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/enforcement")
async def get_enforcement_state(current_user: dict = Depends(get_current_user)):
    """Get current enforcement toggle state from BPF state map."""
    import os as _os
    try:
        from services.os_enforcement_service import get_os_enforcement_service
        svc = get_os_enforcement_service()
        kernel_override = _os.environ.get("SERAPH_KERNEL_ENABLED", "").strip().lower() in ("1", "true", "yes")
        if not svc.is_authoritative:
            loader_state = _get_enforcement_via_loader()
            if loader_state is not None:
                return {**loader_state, "operator_override": kernel_override}
            return {
                "enforcement": False,
                "is_authoritative": False,
                "operator_override": kernel_override,
                "reason": "LSM not loaded — operating in simulation mode",
            }
        state = svc.get_enforcement()
        if state is None:
            return {
                "enforcement": False,
                "is_authoritative": False,
                "operator_override": kernel_override,
                "reason": "state map not yet available",
            }
        return {"enforcement": state}
    except Exception as e:
        return {"enforcement": False, "error": str(e)}


@router.post("/enforcement/{state}")
async def set_enforcement(
    state: str,
    current_user: dict = Depends(check_permission("manage_users")),
):
    """Enable or disable BPF LSM enforcement. state must be 'on' or 'off'."""
    if state not in ("on", "off"):
        raise HTTPException(status_code=400, detail="state must be 'on' or 'off'")
    try:
        from services.os_enforcement_service import get_os_enforcement_service
        svc = get_os_enforcement_service()
        if not svc.is_authoritative:
            enabled = state == "on"
            loader_state = _set_enforcement_via_loader(enabled)
            if loader_state is not None:
                return {**loader_state, "state": state}
            raise HTTPException(status_code=503, detail="LSM not loaded — cannot toggle enforcement (no loader container available)")
        ok = svc.set_enforcement(state == "on")
        if not ok:
            raise HTTPException(status_code=500, detail="BPF map update failed")
        return {"enforcement": state == "on", "state": state}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
