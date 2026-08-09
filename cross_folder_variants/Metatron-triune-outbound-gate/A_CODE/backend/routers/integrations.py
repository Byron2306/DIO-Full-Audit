from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import os
import shutil
import time
from pathlib import Path

from .dependencies import (
    check_permission,
    get_current_user,
    get_optional_current_user,
    has_permission,
    optional_machine_token,
    get_db,
)
try:
    from services.world_events import emit_world_event
except Exception:
    from backend.services.world_events import emit_world_event
from integrations_manager import (
    ingest_indicators_direct,
    run_runtime_tool,
    get_job_async,
    list_jobs_async,
    SUPPORTED_RUNTIME_TOOLS,
)
from integrations_manager import ingest_host_logs
verify_integrations_machine_token = optional_machine_token(
    env_keys=["INTEGRATION_API_KEY", "SWARM_AGENT_TOKEN"],
    header_names=["x-internal-token", "x-agent-token"],
    subject="integrations internal",
)

router = APIRouter(prefix="/integrations", tags=["Integrations"])


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_COMPOSE_FILE = Path(
    os.getenv("SERAPH_COMPOSE_FILE", str(_PROJECT_ROOT / "docker-compose.yml"))
).resolve()
_IDLE_TIMEOUT_SECONDS = max(60, int(os.getenv("INTEGRATIONS_WARM_IDLE_SECONDS", "1800") or "1800"))
_IDLE_REAPER_POLL_SECONDS = max(15, int(os.getenv("INTEGRATIONS_WARM_REAPER_POLL_SECONDS", "60") or "60"))

# Tool name -> compose profile/services to start/stop on demand.
_INTEGRATION_WARM_TARGETS: Dict[str, Dict[str, Any]] = {
    "amass": {"profile": "amass", "services": ["amass"]},
    "spiderfoot": {"profile": "spiderfoot", "services": ["spiderfoot"]},
    "bloodhound": {"profile": "bloodhound", "services": ["bloodhound", "neo4j"]},
    "velociraptor": {"profile": "velociraptor", "services": ["velociraptor"]},
    "purplesharp": {"profile": "purplesharp", "services": ["purplesharp"]},
    "osquery": {"profile": "osquery", "services": ["fleet-mysql", "fleet-redis", "fleet", "osquery"]},
    "atomic": {"profile": "atomic", "services": ["atomic"]},
    "falco": {"profile": "falco", "services": ["falco"]},
    "yara": {"profile": "yara", "services": ["yara"]},
    "suricata": {"profile": "suricata", "services": ["suricata"]},
    "trivy": {"profile": "trivy", "services": ["trivy"]},
    "arkime": {"profile": "arkime", "services": ["arkime-capture", "elasticsearch"]},
    "clamav": {"profile": "clamav", "services": ["clamav"]},
    "cuckoo": {"profile": "sandbox", "services": ["cuckoo", "cuckoo-web"]},
}

_warm_lock = asyncio.Lock()
_warm_state: Dict[str, Dict[str, Any]] = {}
_idle_reaper_task: Optional[asyncio.Task] = None


def _compose_base_command() -> List[str]:
    if shutil.which("docker"):
        return ["docker", "compose"]
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    raise RuntimeError("Neither docker compose nor docker-compose is available")


async def _run_compose(profile: str, action: str, services: List[str]) -> Dict[str, Any]:
    base = _compose_base_command()
    cmd = [
        *base,
        "--project-directory",
        str(_PROJECT_ROOT),
        "-f",
        str(_COMPOSE_FILE),
        "--profile",
        profile,
        action,
    ]
    if action == "up":
        cmd.append("-d")
    cmd.extend(services)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return {
        "command": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout": (stdout or b"").decode("utf-8", errors="ignore"),
        "stderr": (stderr or b"").decode("utf-8", errors="ignore"),
    }


async def _warm_target(name: str) -> Dict[str, Any]:
    target = _INTEGRATION_WARM_TARGETS[name]
    result = await _run_compose(target["profile"], "up", target["services"])
    if result["returncode"] != 0:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to warm integration services",
                "integration": name,
                "command": result["command"],
                "stderr": result["stderr"][-2000:],
            },
        )

    now = time.monotonic()
    async with _warm_lock:
        _warm_state[name] = {
            "last_warm_monotonic": now,
            "last_warm_epoch": time.time(),
            "profile": target["profile"],
            "services": list(target["services"]),
        }

    return {
        "integration": name,
        "profile": target["profile"],
        "services": list(target["services"]),
        "idle_timeout_seconds": _IDLE_TIMEOUT_SECONDS,
        "compose": {
            "command": result["command"],
            "stdout": result["stdout"][-2000:],
            "stderr": result["stderr"][-2000:],
        },
    }


async def _stop_target(name: str, reason: str) -> None:
    target = _INTEGRATION_WARM_TARGETS.get(name)
    if not target:
        return

    result = await _run_compose(target["profile"], "stop", target["services"])
    if result["returncode"] != 0:
        return

    async with _warm_lock:
        _warm_state.pop(name, None)

    await emit_world_event(
        get_db(),
        event_type="integration_runtime_cooled",
        entity_refs=[name],
        payload={
            "integration": name,
            "reason": reason,
            "profile": target["profile"],
            "services": list(target["services"]),
        },
        trigger_triune=False,
    )


async def _idle_reaper_loop() -> None:
    while True:
        await asyncio.sleep(_IDLE_REAPER_POLL_SECONDS)
        now = time.monotonic()

        async with _warm_lock:
            due = [
                name
                for name, state in _warm_state.items()
                if (now - float(state.get("last_warm_monotonic") or 0.0)) >= _IDLE_TIMEOUT_SECONDS
            ]

        for name in due:
            try:
                await _stop_target(name, reason="idle_timeout")
            except Exception:
                continue


@router.on_event("startup")
async def _start_idle_reaper() -> None:
    global _idle_reaper_task
    if _idle_reaper_task is None or _idle_reaper_task.done():
        _idle_reaper_task = asyncio.create_task(_idle_reaper_loop())


@router.on_event("shutdown")
async def _stop_idle_reaper() -> None:
    global _idle_reaper_task
    if _idle_reaper_task is not None:
        _idle_reaper_task.cancel()
        _idle_reaper_task = None


def _allow_any_authenticated_user_for_runtime() -> bool:
    return str(os.getenv("INTEGRATIONS_ALLOW_ANY_AUTH_USER", "1")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _runtime_user_authorized(user: Optional[dict], permission: str) -> bool:
    if user is None:
        return False
    if has_permission(user, permission):
        return True
    return _allow_any_authenticated_user_for_runtime()


def _allow_public_runtime_reads() -> bool:
    """Permit unauthenticated read-only runtime catalog access in local/non-strict mode."""
    return str(os.getenv("INTEGRATIONS_ALLOW_PUBLIC_READ", "1")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

class AmassRequest(BaseModel):
    domain: str
    runtime_target: Optional[str] = "server"
    agent_id: Optional[str] = None

class IngestItem(BaseModel):
    type: Optional[str] = None
    value: str
    confidence: Optional[int] = 50
    threat_level: Optional[str] = "medium"
    description: Optional[str] = ""
    tags: Optional[List[str]] = []
    references: Optional[List[str]] = []

class DirectIngestRequest(BaseModel):
    source: str
    indicators: List[IngestItem]

class RuntimeLaunchRequest(BaseModel):
    tool: str
    params: Optional[Dict[str, Any]] = None
    runtime_target: Optional[str] = "server"
    agent_id: Optional[str] = None


class ToolRunRequest(BaseModel):
    params: Optional[Dict[str, Any]] = None
    runtime_target: Optional[str] = "server"
    agent_id: Optional[str] = None


def _runtime_job_response(job: Dict[str, Any]) -> Dict[str, Any]:
    result = job.get("result") if isinstance(job, dict) else {}
    result = result if isinstance(result, dict) else {}
    return {
        "status": job.get("status"),
        "job_id": job.get("id"),
        "tool": job.get("tool"),
        "runtime_target": (job.get("params") or {}).get("runtime_target") or result.get("runtime_target") or "server",
        "agent_id": result.get("agent_id") or (job.get("params") or {}).get("agent_id"),
        "command_id": result.get("command_id"),
        "queue_id": result.get("queue_id"),
        "decision_id": result.get("decision_id"),
        "result": result,
    }


async def _start_tool_runtime(
    *,
    tool: str,
    params: Dict[str, Any],
    runtime_target: str,
    agent_id: Optional[str],
    user: Dict[str, Any],
) -> Dict[str, Any]:
    job = await run_runtime_tool(
        tool=tool,
        params=params or {},
        runtime_target=runtime_target or "server",
        agent_id=agent_id,
        actor=user.get("email", user.get("id", "unknown")),
        governance_context={
            "approved": True,
            "decision_id": f"integration-{tool}-direct",
            "queue_id": f"integration-{tool}-direct",
        },
    )
    await emit_world_event(
        get_db(),
        event_type=f"integration_{tool}_runtime_requested",
        entity_refs=[tool, job.get("id"), (job.get("result") or {}).get("queue_id")],
        payload={
            "tool": tool,
            "actor": user.get("id"),
            "runtime_target": runtime_target or "server",
            "agent_id": agent_id,
        },
        trigger_triune=False,
    )
    return _runtime_job_response(job)

@router.post("/amass/run")
async def start_amass(req: AmassRequest, user: dict = Depends(check_permission("write"))):
    """Run Amass on server or queue it for unified-agent runtime."""
    return await _start_tool_runtime(
        tool="amass",
        params={"domain": req.domain},
        runtime_target=req.runtime_target or "server",
        agent_id=req.agent_id,
        user=user,
    )

@router.get("/jobs")
async def get_jobs(
    machine_auth: Optional[dict] = Depends(verify_integrations_machine_token),
    user: Optional[dict] = Depends(get_optional_current_user),
):
    if machine_auth is None:
        if user is None and not _allow_public_runtime_reads():
            raise HTTPException(status_code=401, detail="Authentication required")
        if user is not None and not _runtime_user_authorized(user, "read"):
            raise HTTPException(status_code=403, detail="Permission denied. Required: read")
    return await list_jobs_async()

@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    machine_auth: Optional[dict] = Depends(verify_integrations_machine_token),
    user: Optional[dict] = Depends(get_optional_current_user),
):
    if machine_auth is None:
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        if not _runtime_user_authorized(user, "read"):
            raise HTTPException(status_code=403, detail="Permission denied. Required: read")
    job = await get_job_async(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='job not found')
    return job

@router.post("/ingest/direct")
async def direct_ingest(
    req: DirectIngestRequest,
    request: Request,
    machine_auth: Optional[dict] = Depends(verify_integrations_machine_token),
    user: Optional[dict] = Depends(get_optional_current_user),
):
    """Allow direct ingest either via authenticated user OR internal token header for M2M calls.

    Internal clients (workers/agents) should send header `X-Internal-Token` with value
    set in `INTEGRATION_API_KEY` env var.
    """
    internal = machine_auth is not None
    if not internal:
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        if not _runtime_user_authorized(user, "write"):
            raise HTTPException(status_code=403, detail="Permission denied. Required: write")

    items = [i.dict() for i in req.indicators]
    job = await ingest_indicators_direct(req.source, items)
    actor = "machine" if internal else user.get("id")
    await emit_world_event(get_db(), event_type="integration_direct_ingest", entity_refs=[job["id"], req.source], payload={"indicator_count": len(items), "internal": internal, "actor": actor}, trigger_triune=False)
    return {"job_id": job['id'], "status": job['status'], "result": job.get('result')}


class VelociraptorRequest(BaseModel):
    collection_name: Optional[str] = None
    runtime_target: Optional[str] = "server"
    agent_id: Optional[str] = None


@router.post('/velociraptor/run')
async def start_velociraptor(req: VelociraptorRequest, user: dict = Depends(check_permission('write'))):
    return await _start_tool_runtime(
        tool="velociraptor",
        params={"collection_name": req.collection_name},
        runtime_target=req.runtime_target or "server",
        agent_id=req.agent_id,
        user=user,
    )


class PurpleSharpRequest(BaseModel):
    target: Optional[str] = None
    options: Optional[Dict[str, Any]] = None
    runtime_target: Optional[str] = "server"
    agent_id: Optional[str] = None


@router.post('/purplesharp/run')
async def start_purplesharp(req: PurpleSharpRequest, user: dict = Depends(check_permission('write'))):
    return await _start_tool_runtime(
        tool="purplesharp",
        params={"target": req.target, "options": req.options or {}},
        runtime_target=req.runtime_target or "server",
        agent_id=req.agent_id,
        user=user,
    )


@router.post('/arkime/run')
async def start_arkime(req: ToolRunRequest, user: dict = Depends(check_permission("write"))):
    return await _start_tool_runtime(
        tool="arkime",
        params=req.params or {},
        runtime_target=req.runtime_target or "server",
        agent_id=req.agent_id,
        user=user,
    )


@router.post('/bloodhound/run')
async def start_bloodhound(req: ToolRunRequest, user: dict = Depends(check_permission("write"))):
    return await _start_tool_runtime(
        tool="bloodhound",
        params=req.params or {},
        runtime_target=req.runtime_target or "server",
        agent_id=req.agent_id,
        user=user,
    )


@router.post('/spiderfoot/run')
async def start_spiderfoot(req: ToolRunRequest, user: dict = Depends(check_permission("write"))):
    return await _start_tool_runtime(
        tool="spiderfoot",
        params=req.params or {},
        runtime_target=req.runtime_target or "server",
        agent_id=req.agent_id,
        user=user,
    )


@router.post('/sigma/run')
async def start_sigma(req: ToolRunRequest, user: dict = Depends(check_permission("write"))):
    return await _start_tool_runtime(
        tool="sigma",
        params=req.params or {},
        runtime_target=req.runtime_target or "server",
        agent_id=req.agent_id,
        user=user,
    )


@router.post('/atomic/run')
async def start_atomic(req: ToolRunRequest, user: dict = Depends(check_permission("write"))):
    return await _start_tool_runtime(
        tool="atomic",
        params=req.params or {},
        runtime_target=req.runtime_target or "server",
        agent_id=req.agent_id,
        user=user,
    )


@router.post('/falco/run')
async def start_falco(req: ToolRunRequest, user: dict = Depends(check_permission("write"))):
    return await _start_tool_runtime(
        tool="falco",
        params=req.params or {},
        runtime_target=req.runtime_target or "server",
        agent_id=req.agent_id,
        user=user,
    )


@router.post('/yara/run')
async def start_yara(req: ToolRunRequest, user: dict = Depends(check_permission("write"))):
    return await _start_tool_runtime(
        tool="yara",
        params=req.params or {},
        runtime_target=req.runtime_target or "server",
        agent_id=req.agent_id,
        user=user,
    )


@router.post('/suricata/run')
async def start_suricata(req: ToolRunRequest, user: dict = Depends(check_permission("write"))):
    return await _start_tool_runtime(
        tool="suricata",
        params=req.params or {},
        runtime_target=req.runtime_target or "server",
        agent_id=req.agent_id,
        user=user,
    )


@router.post('/trivy/run')
async def start_trivy(req: ToolRunRequest, user: dict = Depends(check_permission("write"))):
    return await _start_tool_runtime(
        tool="trivy",
        params=req.params or {},
        runtime_target=req.runtime_target or "server",
        agent_id=req.agent_id,
        user=user,
    )


@router.post('/cuckoo/run')
async def start_cuckoo(req: ToolRunRequest, user: dict = Depends(check_permission("write"))):
    return await _start_tool_runtime(
        tool="cuckoo",
        params=req.params or {},
        runtime_target=req.runtime_target or "server",
        agent_id=req.agent_id,
        user=user,
    )


@router.post('/osquery/run')
async def start_osquery(req: ToolRunRequest, user: dict = Depends(check_permission("write"))):
    return await _start_tool_runtime(
        tool="osquery",
        params=req.params or {},
        runtime_target=req.runtime_target or "server",
        agent_id=req.agent_id,
        user=user,
    )


@router.post('/zeek/run')
async def start_zeek(req: ToolRunRequest, user: dict = Depends(check_permission("write"))):
    return await _start_tool_runtime(
        tool="zeek",
        params=req.params or {},
        runtime_target=req.runtime_target or "server",
        agent_id=req.agent_id,
        user=user,
    )


@router.post('/clamav/run')
async def start_clamav(req: ToolRunRequest, user: dict = Depends(check_permission("write"))):
    """Run ClamAV antivirus scan. Params: action (scan|status), scan_path."""
    return await _start_tool_runtime(
        tool="clamav",
        params=req.params or {},
        runtime_target=req.runtime_target or "server",
        agent_id=req.agent_id,
        user=user,
    )


class HostLogIngestRequest(BaseModel):
    source: str
    raw: str


@router.get("/runtime/tools")
async def runtime_supported_tools(
    machine_auth: Optional[dict] = Depends(verify_integrations_machine_token),
    user: Optional[dict] = Depends(get_optional_current_user),
):
    if machine_auth is None:
        if user is None and not _allow_public_runtime_reads():
            raise HTTPException(status_code=401, detail="Authentication required")
        if user is not None and not _runtime_user_authorized(user, "read"):
            raise HTTPException(status_code=403, detail="Permission denied. Required: read")
    return {"tools": sorted(SUPPORTED_RUNTIME_TOOLS)}


@router.post("/runtime/run")
async def start_runtime_launch(
    payload: RuntimeLaunchRequest,
    machine_auth: Optional[dict] = Depends(verify_integrations_machine_token),
    user: Optional[dict] = Depends(get_optional_current_user),
):
    if machine_auth is None:
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        if not _runtime_user_authorized(user, "write"):
            raise HTTPException(status_code=403, detail="Permission denied. Required: write")
        actor = user.get("email", user.get("id", "unknown"))
    else:
        actor = "integration-machine-token"

    tool = str(payload.tool or "").strip().lower()
    if tool not in SUPPORTED_RUNTIME_TOOLS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported tool '{payload.tool}'. Supported: {sorted(SUPPORTED_RUNTIME_TOOLS)}",
        )
    job = await run_runtime_tool(
        tool=tool,
        params=payload.params or {},
        runtime_target=payload.runtime_target or "server",
        agent_id=payload.agent_id,
        actor=actor,
        governance_context={
            "approved": True,
            "decision_id": f"integration-{tool}-direct",
            "queue_id": f"integration-{tool}-direct",
        },
    )
    await emit_world_event(
        get_db(),
        event_type=f"integration_{tool}_runtime_requested",
        entity_refs=[tool, job.get("id"), (job.get("result") or {}).get("queue_id")],
        payload={
            "tool": tool,
            "actor": actor,
            "runtime_target": payload.runtime_target or "server",
            "agent_id": payload.agent_id,
            "auth_mode": "machine_token" if machine_auth is not None else "user",
        },
        trigger_triune=False,
    )
    return _runtime_job_response(job)


@router.post("/{name}/warm")
async def warm_integration_runtime(
    name: str,
    user: dict = Depends(check_permission("write")),
):
    integration = str(name or "").strip().lower()
    if integration not in _INTEGRATION_WARM_TARGETS:
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"Unknown integration '{name}'",
                "supported": sorted(_INTEGRATION_WARM_TARGETS.keys()),
            },
        )

    response = await _warm_target(integration)
    await emit_world_event(
        get_db(),
        event_type="integration_runtime_warmed",
        entity_refs=[integration],
        payload={
            "integration": integration,
            "actor": user.get("email", user.get("id")),
            "profile": response["profile"],
            "services": response["services"],
            "idle_timeout_seconds": response["idle_timeout_seconds"],
        },
        trigger_triune=False,
    )
    return response


@router.post('/ingest/host')
async def ingest_host(
    req: HostLogIngestRequest,
    machine_auth: Optional[dict] = Depends(verify_integrations_machine_token),
    user: Optional[dict] = Depends(get_optional_current_user),
):
    """Ingest raw host telemetry (Sysmon/Auditd) text and extract indicators."""
    internal = machine_auth is not None
    if not internal:
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        if not _runtime_user_authorized(user, "write"):
            raise HTTPException(status_code=403, detail="Permission denied. Required: write")
    job = await ingest_host_logs(req.source, req.raw)
    actor = "machine" if internal else user.get("id")
    await emit_world_event(get_db(), event_type="integration_host_ingest", entity_refs=[job["id"], req.source], payload={"raw_size": len(req.raw), "actor": actor}, trigger_triune=False)
    return {"job_id": job['id'], "status": job['status'], "result": job.get('result')}


@router.get('/artifacts/{job_id}')
async def list_artifacts(job_id: str, request: Request, user: dict = Depends(get_current_user)):
    """List artifact filenames for a job (if available)."""
    job = await get_job_async(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='job not found')
    result = job.get('result') or {}
    artifacts = result.get('artifacts') or []
    artifact_dir = result.get('artifact_dir')
    return {"artifacts": artifacts, "artifact_dir": artifact_dir}


@router.get('/artifact/{job_id}/{filename}')
async def get_artifact(job_id: str, filename: str, request: Request, user: dict = Depends(get_current_user)):
    """Download a specific artifact file for a job.
    Note: artifact paths are trusted only when running in controlled environment.
    """
    job = await get_job_async(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='job not found')
    result = job.get('result') or {}
    artifact_dir = result.get('artifact_dir')
    if not artifact_dir:
        raise HTTPException(status_code=404, detail='no artifacts for this job')
    # Prevent path traversal
    safe_base = os.path.abspath(artifact_dir)
    candidate = os.path.abspath(os.path.join(safe_base, filename))
    if not candidate.startswith(safe_base):
        raise HTTPException(status_code=400, detail='invalid filename')
    if not os.path.exists(candidate):
        raise HTTPException(status_code=404, detail='file not found')
    return FileResponse(candidate, filename=filename)
