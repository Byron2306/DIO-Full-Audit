import asyncio
import json
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import os
import re
import shutil
from collections import deque

from routers.dependencies import get_db

_scheduler_task = None
_scheduler_config = {}
_runtime_semaphore = None

from runtime_paths import ensure_data_dir
from threat_intel import threat_intel
from backend.services.governance_context import assert_governance_context

try:
    from backend.services.world_events import emit_world_event
except Exception:  # pragma: no cover
    emit_world_event = None

logger = logging.getLogger(__name__)

# Directory for temporary integration outputs
INTEGRATIONS_DIR = ensure_data_dir("integrations")
INTEGRATIONS_DIR.mkdir(parents=True, exist_ok=True)

_jobs: Dict[str, Dict[str, Any]] = {}
SUPPORTED_RUNTIME_TOOLS = {
    "amass",
    "arkime",
    "bloodhound",
    "spiderfoot",
    "velociraptor",
    "purplesharp",
    "sigma",
    "atomic",
    "falco",
    "yara",
    "suricata",
    "trivy",
    "cuckoo",
    "osquery",
    "zeek",
    "clamav",
}


def _runtime_max_concurrent() -> int:
    try:
        return max(1, int(os.environ.get("INTEGRATION_RUNTIME_MAX_CONCURRENT", "1") or 1))
    except Exception:
        return 1


def _get_runtime_semaphore() -> asyncio.Semaphore:
    global _runtime_semaphore
    desired = _runtime_max_concurrent()
    current = _runtime_semaphore
    if current is None or getattr(current, "_seraph_limit", None) != desired:
        current = asyncio.Semaphore(desired)
        setattr(current, "_seraph_limit", desired)
        _runtime_semaphore = current
    return current


def _db_collection():
    db = get_db()
    if db is None:
        return None
    return db.integrations_jobs


def _json_safe(value: Any) -> Any:
    """Recursively make integration job payloads JSON-safe."""
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for key, inner in value.items():
            if key == "_id":
                # Do not leak database-specific identifiers in API payloads.
                continue
            out[key] = _json_safe(inner)
        return out
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    # Handle bson.ObjectId without importing bson as hard dependency.
    if value.__class__.__name__ == "ObjectId":
        return str(value)
    return value


async def _emit_integration_event(event_type: str, entity_refs: List[str] = None, payload: Dict[str, Any] = None, trigger_triune: bool = False):
    db = get_db()
    if db is None or emit_world_event is None:
        return
    try:
        await emit_world_event(
            db,
            event_type=event_type,
            entity_refs=entity_refs or [],
            payload=payload or {},
            trigger_triune=trigger_triune,
        )
    except Exception:
        logger.debug("integration world event emission failed", exc_info=True)

async def _new_job(tool: str, params: Dict[str, Any]):
    job_id = str(uuid.uuid4())
    job_doc = {
        "id": job_id,
        "tool": tool,
        "params": params,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "result": None,
    }
    # insert into DB if available
    col = _db_collection()
    if col is not None:
        await col.insert_one(dict(job_doc))
    # also keep in-memory copy for quick listing
    _jobs[job_id] = dict(job_doc)
    await _emit_integration_event(
        "integration_job_created_service",
        entity_refs=[job_id],
        payload={"tool": tool},
        trigger_triune=False,
    )
    return job_id


async def _persist_job(job_id: str, **fields: Any) -> Dict[str, Any]:
    """Persist integration job updates in memory + DB."""
    now = datetime.utcnow().isoformat()
    fields = dict(fields or {})
    fields.setdefault("updated_at", now)
    if job_id not in _jobs:
        _jobs[job_id] = {"id": job_id}
    _jobs[job_id].update(fields)
    col = _db_collection()
    if col is not None:
        try:
            await col.update_one({"id": job_id}, {"$set": fields})
        except Exception:
            logger.debug("Failed to persist integration job update", exc_info=True)
    return _jobs.get(job_id, {"id": job_id, **fields})


async def _extract_indicators_from_json_file(path: str, source: str) -> List[Dict[str, Any]]:
    """Best-effort parser for Arkime/BloodHound/SpiderFoot exported JSON."""
    indicators: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return indicators

    def add_ioc(ioc_type: str, value: Any):
        raw = str(value or "").strip()
        if not raw:
            return
        indicators.append({"type": ioc_type, "value": raw, "confidence": 60})

    def walk(obj: Any):
        if isinstance(obj, dict):
            for key, value in obj.items():
                low = str(key).lower()
                if isinstance(value, (str, int, float)):
                    text = str(value).strip()
                    if not text:
                        continue
                    if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", text):
                        add_ioc("ip", text)
                    elif "@" in text and "." in text:
                        add_ioc("email", text)
                    elif "." in text and len(text) > 3 and " " not in text:
                        add_ioc("domain", text)
                if low in {"srcip", "dstip", "ip", "sourceip", "destinationip", "lastlogonip"}:
                    if isinstance(value, list):
                        for entry in value:
                            add_ioc("ip", entry)
                    else:
                        add_ioc("ip", value)
                elif low in {"host", "hosts", "hostname", "domain", "domains", "name", "samaccountname"}:
                    if isinstance(value, list):
                        for entry in value:
                            add_ioc("domain", entry)
                    else:
                        add_ioc("domain", value)
                elif low in {"userprincipalname", "email"}:
                    if isinstance(value, list):
                        for entry in value:
                            add_ioc("email", entry)
                    else:
                        add_ioc("email", value)
                walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for item in indicators:
        key = f"{item.get('type')}:{str(item.get('value') or '').lower()}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _tail_lines(path: Path, limit: int = 200) -> List[str]:
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return list(deque(fh, maxlen=max(1, int(limit))))
    except Exception:
        return []


def _tool_binary(name: str) -> str:
    if name in {"pwsh", "powershell"}:
        candidates = [
            os.environ.get("PWSH_PATH", ""),
            os.environ.get("ATOMIC_RUNNER", ""),
            "/opt/pwsh/pwsh",
            "/opt/pwsh.exe",
            "/usr/bin/pwsh",
            "/usr/local/bin/pwsh",
        ]
        for candidate in candidates:
            if candidate:
                path = Path(candidate)
                if path.exists() and os.access(path, os.X_OK):
                    return str(path)
    return shutil.which(name) or ""


def _resolve_input_file(input_file: str) -> Tuple[Optional[Path], Optional[str]]:
    """Resolve and validate an input artifact path."""
    raw = str(input_file or "").strip()
    if not raw:
        return None, "input_file_required"
    try:
        candidate = Path(raw).expanduser()
        candidate = candidate.resolve() if candidate.is_absolute() else (Path.cwd() / candidate).resolve()
    except Exception:
        return None, "input_file_invalid_path"
    if not candidate.exists():
        return None, "input_file_not_found"
    if not candidate.is_file():
        return None, "input_file_not_a_file"
    if not os.access(candidate, os.R_OK):
        return None, "input_file_not_readable"
    return candidate, None


async def _ingest_export_file(
    *,
    tool: str,
    input_file: str,
    strict_nonempty_parse: bool = False,
) -> Dict[str, Any]:
    resolved, err = _resolve_input_file(input_file)
    if err:
        raise ValueError(err)
    source_path = str(resolved)
    indicators = await _extract_indicators_from_json_file(source_path, tool)
    if strict_nonempty_parse and not indicators:
        raise RuntimeError("empty_indicator_parse")
    ingested = await threat_intel.ingest_indicators(tool, indicators) if indicators else {"ingested": 0}
    return {
        "ingested": ingested.get("ingested", 0) if isinstance(ingested, dict) else 0,
        "source_file": source_path,
        "indicators_extracted": len(indicators),
        "strict_nonempty_parse": bool(strict_nonempty_parse),
    }


async def _new_running_job(tool: str, params: Dict[str, Any]) -> str:
    job_id = await _new_job(tool, params)
    await _persist_job(job_id, status="running")
    return job_id


def _agent_command_for_tool(tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a bounded integration_runtime command payload for unified_agent.
    unified_agent executes this command type with a strict tool allowlist.
    """
    return {
        "command_type": "integration_runtime",
        "parameters": {
            "tool": tool,
            "params": params or {},
        },
    }


async def _queue_unified_agent_runtime(
    *,
    job_id: str,
    tool: str,
    params: Dict[str, Any],
    actor: str,
    agent_id: str,
) -> Dict[str, Any]:
    """Queue integration runtime command for a unified agent through governed dispatch."""
    try:
        from backend.services.governed_dispatch import GovernedDispatchService
    except Exception:
        from backend.services.governed_dispatch import GovernedDispatchService

    db = get_db()
    if db is None:
        await _persist_job(job_id, status="failed", result={"error": "database_unavailable"})
        return _jobs.get(job_id, {"id": job_id, "status": "failed"})

    command_id = f"integration-{uuid.uuid4().hex[:10]}"
    now = datetime.utcnow().isoformat()
    command = _agent_command_for_tool(tool, params)
    command_doc = {
        "command_id": command_id,
        "agent_id": agent_id,
        "type": "command",
        "command_type": command["command_type"],
        "parameters": command["parameters"],
        "priority": "high",
        "status": "gated_pending_approval",
        "created_at": now,
        "updated_at": now,
        "created_by": actor or "integration_runtime",
        "issued_by": actor or "integration_runtime",
        "state_version": 1,
        "state_transition_log": [
            {
                "from_status": None,
                "to_status": "gated_pending_approval",
                "actor": actor or "integration_runtime",
                "reason": "integration runtime queued for approval",
                "timestamp": now,
                "metadata": {"tool": tool},
            }
        ],
    }
    dispatch = GovernedDispatchService(db)
    queued = await dispatch.queue_gated_agent_command(
        action_type="agent_command",
        actor=actor or "integration_runtime",
        agent_id=agent_id,
        command_doc=command_doc,
        impact_level="high",
        entity_refs=[agent_id, command_id, job_id, tool],
        requires_triune=True,
    )
    gate = queued.get("queued", {})
    result = {
        "runtime_target": "unified_agent",
        "agent_id": agent_id,
        "command_id": command_id,
        "queue_id": gate.get("queue_id"),
        "decision_id": gate.get("decision_id"),
        "command_type": command["command_type"],
    }
    await _persist_job(job_id, status="queued_for_triune_approval", result=result)
    return _jobs.get(job_id, {"id": job_id, "status": "queued_for_triune_approval"})


async def _sync_agent_command_state(job: Dict[str, Any]) -> Dict[str, Any]:
    """Hydrate integration job state from unified agent command status."""
    try:
        result = job.get("result") or {}
        command_id = result.get("command_id")
        if not command_id:
            return job
        db = get_db()
        if db is None:
            return job
        cmd = await db.agent_commands.find_one({"command_id": command_id}, {"_id": 0})
        if not cmd:
            return job
        cmd_status = str(cmd.get("status") or "").lower()
        mapped_status = job.get("status")
        if cmd_status in {"completed"}:
            mapped_status = "completed"
        elif cmd_status in {"failed", "error", "cancelled", "unknown_command", "rejected", "denied", "expired"}:
            mapped_status = "failed"
        elif cmd_status in {"delivered", "pending", "queued", "gated_pending_approval"}:
            mapped_status = "running" if cmd_status in {"pending", "delivered"} else "queued_for_triune_approval"
        updated_result = dict(result)
        updated_result["agent_command_status"] = cmd_status
        if cmd.get("result") is not None:
            updated_result["agent_result"] = cmd.get("result")
        if mapped_status != job.get("status") or updated_result != result:
            await _persist_job(job.get("id"), status=mapped_status, result=updated_result)
            return _jobs.get(job.get("id"), job)
    except Exception:
        logger.debug("Failed to sync integration job from agent command", exc_info=True)
    return job


async def _run_subprocess(cmd: List[str], cwd: Path = None, timeout: int = 3600):
    logger.info("Running command: %s", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd) if cwd else None,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise
    return proc.returncode, stdout.decode(errors='ignore'), stderr.decode(errors='ignore')


async def run_amass(
    domain: str,
    governance_context: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Run Amass via Docker on the server, parse JSON-lines output and ingest domains."""
    assert_governance_context(governance_context, action="integrations.run_amass")
    params = {"domain": domain}
    job_id = await _new_running_job("amass", params)

    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    outname = f"amass_{domain}_{ts}_{job_id}.txt"
    errname = f"amass_{domain}_{ts}_{job_id}.stderr.txt"
    outpath = INTEGRATIONS_DIR / outname
    errpath = INTEGRATIONS_DIR / errname

    # OWASP Amass v4 writes results to a file; because this runs via the host Docker socket,
    # avoid bind-mounts (host-path ambiguity) and instead cat the output back over stdout.
    timeout_minutes = int(os.environ.get("AMASS_TIMEOUT_MINUTES", "2") or 2)
    amass_script = (
        f"amass enum -d {domain} -timeout {timeout_minutes} -dir /tmp -o /tmp/amass_out.txt "
        f">/dev/null 2>/tmp/amass_err.txt; "
        f"rc=$?; "
        f"cat /tmp/amass_out.txt 2>/dev/null || true; "
        f"cat /tmp/amass_err.txt >&2 || true; "
        f"exit $rc"
    )
    cmd = ["docker", "run", "--rm", "caffix/amass:latest", "sh", "-lc", amass_script]

    try:
        rc, out, err = await _run_subprocess(cmd, timeout=max(300, timeout_minutes * 60 + 180))
        try:
            outpath.write_text(out or "", encoding="utf-8")
        except Exception:
            pass
        try:
            errpath.write_text(err or "", encoding="utf-8")
        except Exception:
            pass
        if rc != 0:
            await _persist_job(
                job_id,
                status="failed",
                result={
                    "rc": rc,
                    "stderr_tail": (err or "")[-4000:],
                    "stdout_tail": (out or "")[-4000:],
                    "artifact_dir": str(INTEGRATIONS_DIR),
                    "artifacts": [n for n in [outname, errname] if (INTEGRATIONS_DIR / n).exists()],
                },
            )
            return _jobs[job_id]

        # Parse output text (one host per line).
        indicators = []
        discovered_domains = set()
        if outpath.exists():
            for line in outpath.read_text(encoding="utf-8", errors="ignore").splitlines():
                row = line.strip()
                if not row:
                    continue
                # Amass output may include source annotations; keep the first token-like field.
                value = row.split()[0].strip().strip(",")
                if not value:
                    continue
                discovered_domains.add(value.lower())
                indicators.append({"type": "domain", "value": value, "confidence": 50})

        # Ingest into threat intel
        if indicators:
            res = await threat_intel.ingest_indicators('amass', indicators)
        else:
            res = {"ingested": 0}

        result_payload = {
            **(res if isinstance(res, dict) else {"ingested": 0}),
            "artifact_dir": str(INTEGRATIONS_DIR),
            "artifacts": [n for n in [outname, errname] if (INTEGRATIONS_DIR / n).exists()],
            "indicators_extracted": len(indicators),
            "enumerated_domain_count": len(discovered_domains),
            "stdout_tail": (out or "")[-4000:],
            "stderr_tail": (err or "")[-2000:],
        }
        await _persist_job(job_id, status="completed", result=result_payload)
        await _emit_integration_event(
            "integration_job_completed_service",
            entity_refs=[job_id],
            payload={"tool": "amass", "ingested": res.get("ingested", 0) if isinstance(res, dict) else None},
            trigger_triune=False,
        )
        return _jobs[job_id]
    except Exception as e:
        logger.exception("Amass run failed")
        await _persist_job(job_id, status="failed", result={"error": str(e), "artifact_dir": str(INTEGRATIONS_DIR)})
        await _emit_integration_event(
            "integration_job_failed_service",
            entity_refs=[job_id],
            payload={"tool": "amass", "error": str(e)},
            trigger_triune=False,
        )
        return _jobs[job_id]


async def ingest_indicators_direct(source: str, indicators: List[Dict[str, Any]]):
    """Convenience wrapper to ingest programmatically provided indicators."""
    job_id = await _new_job("ingest", {"source": source, "count": len(indicators)})
    _jobs[job_id]["status"] = "running"
    _jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()
    col = _db_collection()
    if col is not None:
        await col.update_one({"id": job_id}, {"$set": {"status": "running", "updated_at": _jobs[job_id]["updated_at"]}})
    try:
        res = await threat_intel.ingest_indicators(source, indicators)
        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["result"] = res
        _jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()
        col = _db_collection()
        if col is not None:
            await col.update_one({"id": job_id}, {"$set": {"status": "completed", "result": res, "updated_at": _jobs[job_id]["updated_at"]}})
        return _jobs[job_id]
    except Exception as e:
        logger.exception("Direct ingest failed")
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["result"] = {"error": str(e)}
        _jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()
        return _jobs[job_id]


async def get_job_async(job_id: str):
    db = get_db()
    doc = None
    if db is not None:
        try:
            doc = await db.integrations_jobs.find_one({"id": job_id}, {"_id": 0})
        except Exception:
            logger.debug("Failed reading integration job from DB", exc_info=True)
            doc = None

    mem = _jobs.get(job_id)
    if doc is None and mem is None:
        return None

    # DB should be authoritative when available (prevents stale in-memory status).
    if doc is not None:
        merged = dict(mem or {})
        merged.update(dict(doc))
    else:
        merged = dict(mem or {})

    hydrated = await _sync_agent_command_state(merged)
    _jobs[job_id] = dict(hydrated)
    return _json_safe(hydrated)


def get_job(job_id: str):
    """Synchronous compatibility wrapper (prefer get_job_async)."""
    if job_id in _jobs:
        return _json_safe(_jobs[job_id])
    return None


async def list_jobs_async(limit: int = 200):
    jobs_map: Dict[str, Dict[str, Any]] = {}
    db = get_db()
    if db is not None:
        try:
            docs = await db.integrations_jobs.find({}, {"_id": 0}).sort("updated_at", -1).limit(limit).to_list(length=limit)
            for doc in docs:
                jid = str(doc.get("id") or "")
                if jid:
                    jobs_map[jid] = dict(doc)
        except Exception:
            logger.debug("Failed listing integration jobs from DB", exc_info=True)
    for jid, job in _jobs.items():
        # Keep DB fields authoritative when present.
        if jid in jobs_map:
            merged = dict(job)
            merged.update(jobs_map[jid])
            jobs_map[jid] = merged
        else:
            jobs_map[jid] = dict(job)

    hydrated: List[Dict[str, Any]] = []
    for job in jobs_map.values():
        hydrated.append(await _sync_agent_command_state(job))

    hydrated.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
    return [_json_safe(job) for job in hydrated[:limit]]


def list_jobs():
    """Synchronous compatibility wrapper (prefer list_jobs_async)."""
    return [_json_safe(job) for job in sorted(_jobs.values(), key=lambda j: str(j.get("updated_at") or ""), reverse=True)]


async def _scheduler_loop():
    """Simple scheduler loop that runs configured tasks periodically.
    Configuration via environment variables:
      - AMASS_SCHEDULE_HOURS (int, optional)
      - AMASS_DOMAINS (comma-separated domains)
    """
    logger.info("Integrations scheduler started")
    try:
        while True:
            try:
                hours = int(os.environ.get('AMASS_SCHEDULE_HOURS', '0'))
                domains = os.environ.get('AMASS_DOMAINS', '').split(',') if os.environ.get('AMASS_DOMAINS') else []
                allow_ungated_scheduler = str(os.environ.get("ALLOW_UNGATED_INTEGRATION_SCHEDULER", "false")).lower() in {"1", "true", "yes", "on"}
                if hours > 0 and domains:
                    if not allow_ungated_scheduler:
                        logger.warning(
                            "Skipping scheduled integration execution because it is not outbound-gated. "
                            "Set ALLOW_UNGATED_INTEGRATION_SCHEDULER=true only for controlled environments."
                        )
                        await asyncio.sleep(max(3600, hours * 3600))
                        continue
                    for d in [x.strip() for x in domains if x.strip()]:
                        logger.info(f"Scheduler: launching amass for {d}")
                        await run_amass(
                            d,
                            governance_context={
                                "approved": True,
                                "decision_id": "scheduler-ungated-allowlist",
                                "queue_id": "scheduler",
                            },
                        )
                # Sleep for hours (default 1 hour if not set to 0)
                sleep_for = max(3600, hours * 3600) if hours > 0 else 3600
            except Exception as e:
                logger.error(f"Scheduler iteration error: {e}")
                sleep_for = 3600

            await asyncio.sleep(sleep_for)
    except asyncio.CancelledError:
        logger.info("Integrations scheduler stopped")


def start_scheduler():
    global _scheduler_task
    if _scheduler_task is None:
        _scheduler_task = asyncio.create_task(_scheduler_loop())
        logger.info("Integrations scheduler task created")
    else:
        logger.info("Integrations scheduler already running")


async def run_velociraptor(
    collection_name: str = None,
    governance_context: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Run a lightweight Velociraptor probe using Docker.

    The upstream implementation expected a Celery worker to exist and enqueue a
    background task. In the default local docker-compose stack, Celery is not
    present, which made the integration appear to "do nothing" in both the
    port-3000 and port-5000 dashboards.

    This implementation is intentionally non-destructive:
    - pulls (or reuses) the Velociraptor image
    - executes `velociraptor version` inside a one-shot container
    - stores output as an artifact for operator inspection
    """
    assert_governance_context(governance_context, action="integrations.run_velociraptor")
    params = {"collection": collection_name, "action": "version"}
    job_id = await _new_running_job("velociraptor", params)

    docker_bin = _tool_binary("docker")
    if not docker_bin:
        await _persist_job(job_id, status="failed", result={"error": "docker_not_available"})
        return _jobs[job_id]

    image = "wlambert/velociraptor:latest"
    try:
        # Best-effort pull (fast if cached)
        await _run_subprocess([docker_bin, "pull", image], timeout=240)

        # The image boots a full server by default; run a safe probe by overriding
        # the entrypoint and executing the embedded binary directly.
        rc, out, err = await _run_subprocess(
            [
                docker_bin,
                "run",
                "--rm",
                "--entrypoint",
                "sh",
                image,
                "-lc",
                "cp /opt/velociraptor/linux/velociraptor /tmp/velociraptor && chmod +x /tmp/velociraptor && /tmp/velociraptor version",
            ],
            timeout=90,
        )
        stdout = (out or "").strip()
        stderr = (err or "").strip()

        artifact_name = f"velociraptor_{job_id}.txt"
        artifact_path = INTEGRATIONS_DIR / artifact_name
        artifact_path.write_text(
            "\n".join(
                [
                    f"collection_name={collection_name or ''}".strip(),
                    f"timestamp={datetime.now(timezone.utc).isoformat()}",
                    f"image={image}",
                    f"return_code={rc}",
                    "",
                    "STDOUT:",
                    stdout,
                    "",
                    "STDERR:",
                    stderr,
                    "",
                ]
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        status = "completed" if rc == 0 else "failed"
        await _persist_job(
            job_id,
            status=status,
            result={
                "action": "version",
                "collection_name": collection_name,
                "image": image,
                "return_code": rc,
                "artifact_dir": str(INTEGRATIONS_DIR),
                "artifacts": [artifact_name],
                "stdout": stdout[:2000],
                "stderr": stderr[:2000],
            },
        )
        return _jobs[job_id]
    except Exception as exc:
        await _persist_job(job_id, status="failed", result={"error": str(exc), "image": image})
        return _jobs[job_id]


async def run_purplesharp(
    target: str = None,
    options: Dict[str, Any] = None,
    governance_context: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Run PurpleSharp with local/winrm execution modes and ingest indicators."""
    assert_governance_context(governance_context, action="integrations.run_purplesharp")
    opts = dict(options or {})
    params = {"target": target, "options": opts}
    job_id = await _new_running_job("purplesharp", params)
    script = Path(__file__).resolve().parent.parent / "unified_agent" / "integrations" / "purplesharp" / "run_purplesharp.sh"
    if not script.exists():
        await _persist_job(job_id, status="failed", result={"error": f"missing_script:{script}"})
        return _jobs[job_id]
    env = dict(os.environ)
    env["OUTDIR"] = str(INTEGRATIONS_DIR)
    if target:
        env["PURPLESHARP_TARGET"] = str(target)
    if opts:
        env["PURPLESHARP_OPTIONS_JSON"] = json.dumps(opts)
    try:
        cmd = ["bash", str(script)]
        if target:
            cmd.extend(["--target", str(target)])
        if opts.get("mode"):
            cmd.extend(["--mode", str(opts.get("mode"))])
        if opts.get("host"):
            cmd.extend(["--host", str(opts.get("host"))])
        if opts.get("username"):
            cmd.extend(["--username", str(opts.get("username"))])
        if opts.get("password"):
            cmd.extend(["--password", str(opts.get("password"))])
        if opts.get("powershell"):
            cmd.extend(["--powershell", str(opts.get("powershell"))])
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        out = (stdout.decode(errors="ignore") or "").strip()
        err = (stderr.decode(errors="ignore") or "").strip()
        recent_artifacts = []
        try:
            now_ts = datetime.now(timezone.utc).timestamp()
            candidates = [p for p in INTEGRATIONS_DIR.glob("purplesharp_*") if p.is_file()]
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            for p in candidates[:15]:
                if now_ts - p.stat().st_mtime <= 600:
                    recent_artifacts.append(p.name)
        except Exception:
            recent_artifacts = []
        if proc.returncode != 0:
            outfile = out.splitlines()[-1].strip() if out else ""
            artifact_name = Path(outfile).name if outfile and Path(outfile).exists() else ""
            await _persist_job(
                job_id,
                status="failed",
                result={
                    "rc": proc.returncode,
                    "stderr": err,
                    "stdout": out[-4000:],
                    "artifact_dir": str(INTEGRATIONS_DIR),
                    "artifacts": (
                        [artifact_name]
                        if artifact_name
                        else sorted(set(recent_artifacts))[:8]
                    ),
                },
            )
            return _jobs[job_id]
        outfile = out.splitlines()[-1].strip() if out else ""
        indicators = []
        if outfile and Path(outfile).exists():
            indicators = await _extract_indicators_from_json_file(outfile, "purplesharp")
        ingested = await threat_intel.ingest_indicators("purplesharp", indicators) if indicators else {"ingested": 0}
        await _persist_job(
            job_id,
            status="completed",
            result={
                "ingested": ingested.get("ingested", 0) if isinstance(ingested, dict) else 0,
                "artifact_dir": str(INTEGRATIONS_DIR),
                "artifacts": [Path(outfile).name] if outfile else [],
                "stdout": out[-4000:],
                "stderr": err[-2000:],
                "execution_mode": opts.get("mode") or "auto",
            },
        )
        return _jobs[job_id]
    except Exception as exc:
        await _persist_job(job_id, status="failed", result={"error": str(exc)})
        return _jobs[job_id]


async def _run_docker_service(
    *,
    tool: str,
    image: str,
    container_name: str,
    ports: List[str],
    env_vars: Dict[str, str] = None,
) -> Dict[str, Any]:
    job_id = await _new_job(tool, {"image": image, "container_name": container_name, "ports": ports})
    await _persist_job(job_id, status="running")
    cmd = ["docker", "run", "-d", "--rm", "--name", container_name]
    for port in ports:
        cmd.extend(["-p", port])
    for key, value in (env_vars or {}).items():
        cmd.extend(["-e", f"{key}={value}"])
    cmd.append(image)
    try:
        rc, out, err = await _run_subprocess(cmd, timeout=240)
        if rc != 0:
            # Common case: service already running / port in use. Surface as ready_with_warning.
            if "port is already allocated" in (err or "").lower() or "is already in use by container" in (err or "").lower():
                await _persist_job(
                    job_id,
                    status="completed",
                    result={"ready": True, "warning": err[:1000], "container_name": container_name, "ports": ports},
                )
                return _jobs[job_id]
            await _persist_job(job_id, status="failed", result={"rc": rc, "stderr": err[:2000]})
            return _jobs[job_id]
        await _persist_job(
            job_id,
            status="completed",
            result={
                "ready": True,
                "container_id": out.strip(),
                "container_name": container_name,
                "ports": ports,
            },
        )
        return _jobs[job_id]
    except Exception as exc:
        await _persist_job(job_id, status="failed", result={"error": str(exc)})
        return _jobs[job_id]


async def run_arkime(governance_context: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
    assert_governance_context(governance_context, action="integrations.run_arkime")
    settings = params or {}
    action = str(settings.get("action") or "start").strip().lower()
    if action in {"status", "health"}:
        return await _run_tool_status_probe("arkime", settings)
    input_file = str(settings.get("input_file") or "").strip()
    if input_file or action in {"ingest", "parse_ingest", "parse"}:
        job_id = await _new_job("arkime", {"action": action, "input_file": input_file})
        await _persist_job(job_id, status="running")
        try:
            result = await _ingest_export_file(
                tool="arkime",
                input_file=input_file,
                strict_nonempty_parse=bool(settings.get("strict_nonempty_parse", False)),
            )
            result["action"] = "parse_ingest"
            await _persist_job(job_id, status="completed", result=result)
        except Exception as exc:
            await _persist_job(
                job_id,
                status="failed",
                result={
                    "action": "parse_ingest",
                    "source_file": input_file,
                    "error": str(exc),
                },
            )
        return _jobs[job_id]
    if action not in {"", "start", "launch", "run"}:
        job_id = await _new_job("arkime", {"action": action})
        await _persist_job(job_id, status="failed", result={"error": f"unsupported_action:{action}"})
        return _jobs[job_id]
    return await _run_docker_service(
        tool="arkime",
        image="mosajjal/arkime:latest",
        container_name=f"arkime-{uuid.uuid4().hex[:6]}",
        ports=["8005:8005", "8006:8006"],
        env_vars={"ES_HOSTS": str(settings.get("es_url") or os.environ.get("ARKIME_ES_URL") or "http://host.docker.internal:9200")},
    )


async def run_bloodhound(governance_context: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
    assert_governance_context(governance_context, action="integrations.run_bloodhound")
    settings = params or {}
    action = str(settings.get("action") or "start").strip().lower()
    if action in {"status", "health"}:
        return await _run_tool_status_probe("bloodhound", settings)
    input_file = str(settings.get("input_file") or "").strip()
    if input_file or action in {"ingest", "parse_ingest", "parse"}:
        job_id = await _new_job("bloodhound", {"action": action, "input_file": input_file})
        await _persist_job(job_id, status="running")
        try:
            result = await _ingest_export_file(
                tool="bloodhound",
                input_file=input_file,
                strict_nonempty_parse=bool(settings.get("strict_nonempty_parse", False)),
            )
            result["action"] = "parse_ingest"
            await _persist_job(job_id, status="completed", result=result)
        except Exception as exc:
            await _persist_job(
                job_id,
                status="failed",
                result={
                    "action": "parse_ingest",
                    "source_file": input_file,
                    "error": str(exc),
                },
            )
        return _jobs[job_id]
    if action not in {"", "start", "launch", "run"}:
        job_id = await _new_job("bloodhound", {"action": action})
        await _persist_job(job_id, status="failed", result={"error": f"unsupported_action:{action}"})
        return _jobs[job_id]
    image = str(settings.get("image") or "specterops/bloodhound:latest")
    return await _run_docker_service(
        tool="bloodhound",
        image=image,
        container_name=f"bloodhound-{uuid.uuid4().hex[:6]}",
        ports=["7474:7474", "7687:7687"],
    )


async def run_spiderfoot(governance_context: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
    assert_governance_context(governance_context, action="integrations.run_spiderfoot")
    settings = params or {}
    action = str(settings.get("action") or "start").strip().lower()
    if action in {"status", "health"}:
        return await _run_tool_status_probe("spiderfoot", settings)
    input_file = str(settings.get("input_file") or "").strip()
    if input_file or action in {"ingest", "parse_ingest", "parse"}:
        job_id = await _new_job("spiderfoot", {"action": action, "input_file": input_file})
        await _persist_job(job_id, status="running")
        try:
            result = await _ingest_export_file(
                tool="spiderfoot",
                input_file=input_file,
                strict_nonempty_parse=bool(settings.get("strict_nonempty_parse", False)),
            )
            result["action"] = "parse_ingest"
            await _persist_job(job_id, status="completed", result=result)
        except Exception as exc:
            await _persist_job(
                job_id,
                status="failed",
                result={
                    "action": "parse_ingest",
                    "source_file": input_file,
                    "error": str(exc),
                },
            )
        return _jobs[job_id]
    if action not in {"", "start", "launch", "run"}:
        job_id = await _new_job("spiderfoot", {"action": action})
        await _persist_job(job_id, status="failed", result={"error": f"unsupported_action:{action}"})
        return _jobs[job_id]
    return await _run_docker_service(
        tool="spiderfoot",
        image="ctdc/spiderfoot:latest",
        container_name=f"spiderfoot-{uuid.uuid4().hex[:6]}",
        ports=[f"{int(settings.get('port') or 5001)}:5001"],
    )


async def run_sigma(governance_context: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
    assert_governance_context(governance_context, action="integrations.run_sigma")
    payload = params or {}
    action = str(payload.get("action") or "reload").lower().strip()
    job_id = await _new_job("sigma", {"action": action, "params": payload})
    await _persist_job(job_id, status="running")
    try:
        from sigma_engine import sigma_engine

        if action == "status":
            result = sigma_engine.get_status()
        elif action == "list_rules":
            result = sigma_engine.list_rules(
                limit=int(payload.get("limit") or 50),
                offset=int(payload.get("offset") or 0),
                query=str(payload.get("query") or ""),
            )
        elif action == "evaluate":
            event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
            result = sigma_engine.evaluate_event(event, max_matches=int(payload.get("max_matches") or 25))
        elif action == "coverage":
            result = sigma_engine.coverage_summary()
        elif action in {"unified_coverage", "coverage_unified"}:
            summary = sigma_engine.coverage_summary()
            result = (summary or {}).get("unified_coverage") if isinstance(summary, dict) else {}
        elif action in {"reload", "refresh"}:
            result = sigma_engine.reload_rules()
        else:
            await _persist_job(job_id, status="failed", result={"error": f"unsupported_action:{action}", "action": action})
            return _jobs[job_id]
        await _persist_job(job_id, status="completed", result={"action": action, "result": result})
        return _jobs[job_id]
    except Exception as exc:
        await _persist_job(job_id, status="failed", result={"error": str(exc), "action": action})
        return _jobs[job_id]


async def run_atomic(governance_context: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
    assert_governance_context(governance_context, action="integrations.run_atomic")
    payload = params or {}
    action = str(payload.get("action") or "run").lower().strip()
    dry_run = bool(payload.get("dry_run", False))
    selected_job = str(payload.get("job_id") or "").strip()
    job_id = await _new_job("atomic", {"action": action, "job_id": selected_job, "dry_run": dry_run})
    await _persist_job(job_id, status="running")
    try:
        import importlib

        atomic_module = importlib.import_module("atomic_validation")
        manager = getattr(atomic_module, "atomic_validation")
        manager.set_db(get_db())
        if action == "status":
            result = {
                "status": manager.get_status(),
                "jobs": manager.list_jobs(),
                "runs": manager.list_runs(limit=25),
            }
            await _persist_job(job_id, status="completed", result=result)
            return _jobs[job_id]
        if action == "jobs":
            await _persist_job(job_id, status="completed", result={"action": action, "result": manager.list_jobs()})
            return _jobs[job_id]
        if action == "runs":
            await _persist_job(
                job_id,
                status="completed",
                result={"action": action, "result": manager.list_runs(limit=int(payload.get("limit") or 50))},
            )
            return _jobs[job_id]
        if action not in {"run", "execute"}:
            await _persist_job(job_id, status="failed", result={"error": f"unsupported_action:{action}", "action": action})
            return _jobs[job_id]
        if not selected_job:
            jobs_payload = manager.list_jobs() or {}
            job_rows = jobs_payload.get("jobs") if isinstance(jobs_payload, dict) else []
            if not isinstance(job_rows, list) or not job_rows:
                await _persist_job(job_id, status="failed", result={"error": "atomic_jobs_unavailable"})
                return _jobs[job_id]
            selected_job = str((job_rows[0] or {}).get("job_id") or "")
            if not selected_job:
                await _persist_job(job_id, status="failed", result={"error": "atomic_jobs_unavailable"})
                return _jobs[job_id]
        result = await asyncio.to_thread(manager.run_job, selected_job, dry_run)
        if isinstance(result, dict):
            result.setdefault("selected_job_id", selected_job)
        ok = bool(result.get("ok", False))
        await _persist_job(job_id, status="completed" if ok else "failed", result=result)
        return _jobs[job_id]
    except Exception as exc:
        await _persist_job(job_id, status="failed", result={"error": str(exc)})
        return _jobs[job_id]


async def run_trivy(governance_context: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
    assert_governance_context(governance_context, action="integrations.run_trivy")
    payload = params or {}
    action = str(payload.get("action") or "status").lower().strip()
    job_id = await _new_running_job("trivy", {"action": action, "params": payload})
    try:
        from container_security import container_security

        if action == "scan_image":
            image_name = str(payload.get("image_name") or "").strip()
            if not image_name:
                await _persist_job(job_id, status="failed", result={"error": "image_name_required"})
                return _jobs[job_id]
            result = await container_security.scan_image(image_name, bool(payload.get("force", False)))
        elif action == "scan_all":
            result = await container_security.scan_all_images()
        else:
            result = container_security.get_stats()
        await _persist_job(job_id, status="completed", result={"action": action, "result": result})
        return _jobs[job_id]
    except Exception as exc:
        await _persist_job(job_id, status="failed", result={"action": action, "error": str(exc)})
        return _jobs[job_id]


async def run_falco(governance_context: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
    assert_governance_context(governance_context, action="integrations.run_falco")
    payload = params or {}
    action = str(payload.get("action") or "status").lower().strip()
    job_id = await _new_running_job("falco", {"action": action, "params": payload})
    try:
        from container_security import container_security

        if action == "alerts":
            limit = int(payload.get("limit") or 100)
            alerts = container_security.falco.get_alerts(limit=limit)
            result = {"alerts": alerts, "count": len(alerts)}
        elif action == "escape_attempts":
            limit = int(payload.get("limit") or 100)
            attempts = container_security.falco.get_escape_attempts(limit=limit)
            result = {"attempts": attempts, "count": len(attempts)}
        else:
            result = await container_security.get_runtime_security_status()
        await _persist_job(job_id, status="completed", result={"action": action, "result": result})
        return _jobs[job_id]
    except Exception as exc:
        await _persist_job(job_id, status="failed", result={"action": action, "error": str(exc)})
        return _jobs[job_id]


async def run_suricata(governance_context: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
    assert_governance_context(governance_context, action="integrations.run_suricata")
    payload = params or {}
    action = str(payload.get("action") or "status").lower().strip()
    eve_path = Path(str(payload.get("eve_path") or "/var/log/suricata/eve.json"))
    stats_path = Path(str(payload.get("stats_path") or "/var/log/suricata/stats.log"))
    job_id = await _new_running_job("suricata", {"action": action, "eve_path": str(eve_path), "stats_path": str(stats_path)})
    try:
        if action == "alerts":
            alerts = []
            for line in reversed(_tail_lines(eve_path, limit=int(payload.get("limit") or 400))):
                raw = line.strip()
                if not raw:
                    continue
                try:
                    item = json.loads(raw)
                except Exception:
                    continue
                if item.get("event_type") == "alert":
                    alerts.append(item)
            result = {"available": eve_path.exists(), "alert_count": len(alerts), "alerts": alerts[: int(payload.get("return_limit") or 120)]}
        else:
            alert_count = 0
            for line in _tail_lines(eve_path, limit=4000):
                if '"event_type":"alert"' in line or '"event_type": "alert"' in line:
                    alert_count += 1
            result = {
                "available": eve_path.exists() or stats_path.exists(),
                "eve_json_exists": eve_path.exists(),
                "stats_log_exists": stats_path.exists(),
                "recent_alert_count": alert_count,
            }
        await _persist_job(job_id, status="completed", result={"action": action, "result": result})
        return _jobs[job_id]
    except Exception as exc:
        await _persist_job(job_id, status="failed", result={"action": action, "error": str(exc)})
        return _jobs[job_id]


async def run_yara(governance_context: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
    assert_governance_context(governance_context, action="integrations.run_yara")
    payload = params or {}
    action = str(payload.get("action") or "status").lower().strip()
    job_id = await _new_running_job("yara", {"action": action, "params": payload})
    try:
        yara_bin = _tool_binary("yara")
        rule_dirs = [
            Path(str(payload.get("rules_path") or "")).expanduser(),
            Path("/yara_rules"),
            Path("/app/yara_rules"),
            Path("/etc/yara/rules"),
            Path("/var/lib/seraph-ai/yara_rules"),
        ]
        resolved_rules_path = ""
        for directory in rule_dirs:
            if not str(directory):
                continue
            if directory.exists():
                resolved_rules_path = str(directory)
                break

        if action == "scan":
            rules_path = resolved_rules_path or str(payload.get("rules_path") or "/yara_rules")
            target_path = str(payload.get("target_path") or "/tmp")
            timeout_s = int(payload.get("timeout") or 180)
            if yara_bin:
                cmd = [yara_bin, "-r", rules_path, target_path]
                rc, out, err = await _run_subprocess(cmd, timeout=timeout_s)
            else:
                docker_bin = _tool_binary("docker")
                if not docker_bin:
                    await _persist_job(job_id, status="failed", result={"error": "yara_binary_not_found_and_docker_unavailable"})
                    return _jobs[job_id]

                # Fall back to a one-shot container scan so the integration works in a minimal stack.
                # Image choice is intentionally boring; can be overridden by env.
                yara_image = os.environ.get("YARA_DOCKER_IMAGE") or "alpine:3.20"
                # Ensure rules and target are readable inside the container.
                rc, out, err = await _run_subprocess(
                    [
                        docker_bin,
                        "run",
                        "--rm",
                        "-v",
                        f"{rules_path}:/rules:ro",
                        "-v",
                        f"{target_path}:/target:ro",
                        yara_image,
                        "sh",
                        "-lc",
                        "apk add --no-cache yara >/dev/null 2>&1 && yara -r /rules /target",
                    ],
                    timeout=timeout_s,
                )
            result = {
                "return_code": rc,
                "success": rc in {0, 1},
                "stdout": out[-12000:],
                "stderr": err[-4000:],
                "rules_path": rules_path,
                "target_path": target_path,
            }
            await _persist_job(job_id, status="completed" if rc in {0, 1} else "failed", result=result)
            return _jobs[job_id]

        # status
        rule_count = 0
        for directory in rule_dirs:
            if directory.exists():
                rule_count += sum(1 for _ in directory.glob("**/*.yar")) + sum(1 for _ in directory.glob("**/*.yara"))
        version = ""
        if yara_bin:
            rc, out, _ = await _run_subprocess([yara_bin, "--version"], timeout=10)
            if rc == 0:
                version = (out or "").strip()
        docker_available = bool(_tool_binary("docker"))
        result = {
            "available": bool(yara_bin) or docker_available,
            "runtime": "binary" if yara_bin else ("docker" if docker_available else "none"),
            "version": version,
            "rule_count": rule_count,
            "rules_path": resolved_rules_path,
            "docker_image": os.environ.get("YARA_DOCKER_IMAGE") or "alpine:3.20",
        }
        await _persist_job(job_id, status="completed", result={"action": action, "result": result})
        return _jobs[job_id]
    except Exception as exc:
        await _persist_job(job_id, status="failed", result={"action": action, "error": str(exc)})
        return _jobs[job_id]


async def run_osquery(governance_context: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
    assert_governance_context(governance_context, action="integrations.run_osquery")
    payload = params or {}
    action = str(payload.get("action") or "status").lower().strip()
    job_id = await _new_running_job("osquery", {"action": action, "params": payload})
    try:
        from osquery_fleet import osquery_fleet

        if action == "live_query":
            sql = str(payload.get("sql") or "").strip()
            result = osquery_fleet.run_live_query(sql, selected=payload.get("selected") or {})
        elif action == "queries":
            result = osquery_fleet.list_queries(limit=int(payload.get("limit") or 50), query=str(payload.get("query") or ""))
        elif action == "results":
            result = osquery_fleet.get_results(limit=int(payload.get("limit") or 100))
        elif action == "stats":
            result = osquery_fleet.get_stats()
        else:
            result = osquery_fleet.get_status()
        ok = bool(result.get("ok", True)) if isinstance(result, dict) else True
        await _persist_job(job_id, status="completed" if ok else "failed", result={"action": action, "result": result})
        return _jobs[job_id]
    except Exception as exc:
        await _persist_job(job_id, status="failed", result={"action": action, "error": str(exc)})
        return _jobs[job_id]


async def run_zeek(governance_context: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
    assert_governance_context(governance_context, action="integrations.run_zeek")
    payload = params or {}
    action = str(payload.get("action") or "status").lower().strip()
    requested_dir = str(payload.get("log_dir") or os.environ.get("ZEEK_LOG_DIR") or "/var/log/zeek/current")
    candidates = [
        Path(requested_dir),
        Path("/var/log/zeek/current"),
        Path("/var/log/zeek"),
        Path("/usr/local/zeek/logs/current"),
        Path("/usr/local/zeek/logs"),
    ]
    zeek_dir = next((candidate for candidate in candidates if candidate.exists()), Path(requested_dir))
    job_id = await _new_running_job("zeek", {"action": action, "log_dir": str(zeek_dir)})
    try:
        if action == "log":
            log_type = str(payload.get("log_type") or "conn")
            log_path = zeek_dir / f"{log_type}.log"
            rows = [line.strip() for line in _tail_lines(log_path, limit=int(payload.get("limit") or 150)) if line.strip()]
            result = {"available": log_path.exists(), "log_type": log_type, "count": len(rows), "records": rows}
        elif action == "stats":
            conn_lines = _tail_lines(zeek_dir / "conn.log", limit=2000)
            dns_lines = _tail_lines(zeek_dir / "dns.log", limit=2000)
            notice_lines = _tail_lines(zeek_dir / "notice.log", limit=400)
            result = {
                "available": zeek_dir.exists(),
                "conn_events": len([l for l in conn_lines if l and not l.startswith("#")]),
                "dns_events": len([l for l in dns_lines if l and not l.startswith("#")]),
                "notice_events": len([l for l in notice_lines if l and not l.startswith("#")]),
            }
        else:
            logs = sorted([p.stem for p in zeek_dir.glob("*.log")]) if zeek_dir.exists() else []
            result = {"available": zeek_dir.exists(), "log_dir": str(zeek_dir), "log_types": logs, "log_count": len(logs)}
        await _persist_job(job_id, status="completed", result={"action": action, "result": result})
        return _jobs[job_id]
    except Exception as exc:
        await _persist_job(job_id, status="failed", result={"action": action, "error": str(exc)})
        return _jobs[job_id]


async def run_cuckoo(governance_context: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
    assert_governance_context(governance_context, action="integrations.run_cuckoo")
    payload = params or {}
    action = str(payload.get("action") or "status").lower().strip()
    job_id = await _new_running_job("cuckoo", {"action": action, "params": payload})
    try:
        try:
            from backend.services.cuckoo_sandbox import cuckoo_sandbox
        except Exception:
            from backend.services.cuckoo_sandbox import cuckoo_sandbox

        cuckoo_sandbox.set_db(get_db())
        if action == "submit_file":
            file_path = str(payload.get("file_path") or "").strip()
            if not file_path:
                await _persist_job(job_id, status="failed", result={"error": "file_path_required"})
                return _jobs[job_id]
            result = await asyncio.to_thread(cuckoo_sandbox.submit_file, file_path, payload.get("options") or {})
        elif action == "submit_url":
            url = str(payload.get("url") or "").strip()
            if not url:
                await _persist_job(job_id, status="failed", result={"error": "url_required"})
                return _jobs[job_id]
            result = await asyncio.to_thread(cuckoo_sandbox.submit_url, url, payload.get("options") or {})
        elif action == "task_status":
            task_id = str(payload.get("task_id") or "").strip()
            result = await asyncio.to_thread(cuckoo_sandbox.get_task_status, task_id)
        elif action == "report":
            task_id = str(payload.get("task_id") or "").strip()
            result = await asyncio.to_thread(cuckoo_sandbox.get_report, task_id)
        else:
            result = await asyncio.to_thread(cuckoo_sandbox.get_status)
        ok = bool(result.get("success", True)) if isinstance(result, dict) else True
        await _persist_job(job_id, status="completed" if ok else "failed", result={"action": action, "result": result})
        return _jobs[job_id]
    except Exception as exc:
        await _persist_job(job_id, status="failed", result={"action": action, "error": str(exc)})
        return _jobs[job_id]


async def run_clamav(governance_context: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Run ClamAV antivirus scan."""
    assert_governance_context(governance_context, action="integrations.run_clamav")
    payload = params or {}
    action = str(payload.get("action") or "scan").lower().strip()
    scan_path = str(payload.get("scan_path") or "/tmp").strip()
    job_id = await _new_running_job("clamav", {"action": action, "scan_path": scan_path, "params": payload})
    try:
        clam_bin = _tool_binary("clamscan") or _tool_binary("clamdscan")
        if not clam_bin:
            # Try docker-based ClamAV
            docker_bin = _tool_binary("docker")
            if docker_bin:
                cmd = [docker_bin, "run", "--rm", "-v", f"{scan_path}:/scandir:ro",
                       "clamav/clamav:stable", "clamscan", "--recursive", "/scandir"]
            else:
                await _persist_job(job_id, status="failed", result={"error": "clamscan not found; install clamav or start clamav docker service"})
                return _jobs[job_id]
        else:
            cmd = [clam_bin, "--recursive", "--infected", "--no-summary", scan_path]

        if action == "status":
            version_bin = _tool_binary("clamscan") or _tool_binary("clamdscan")
            rc, out, _ = await _run_subprocess([version_bin, "--version"] if version_bin else ["echo", "not installed"], timeout=10)
            result = {
                "available": version_bin is not None,
                "binary": version_bin,
                "version": (out or "").strip().splitlines()[0] if out else "unknown",
            }
            await _persist_job(job_id, status="completed", result={"action": "status", "result": result})
            return _jobs[job_id]

        rc, out, err = await _run_subprocess(cmd, timeout=120)
        lines = (out or "").strip().splitlines()
        infected = [l for l in lines if "FOUND" in l]
        result = {
            "scan_path": scan_path,
            "return_code": rc,
            "infected_count": len(infected),
            "infected_files": infected,
            "output": (out or "")[:2000],
            "clean": rc == 0,
        }
        status = "completed" if rc in (0, 1) else "failed"
        await _persist_job(job_id, status=status, result={"action": action, "result": result})

        if infected:
            await _emit_integration_event(
                "clamav_threat_detected",
                entity_refs=[scan_path],
                payload={"infected_files": infected, "count": len(infected)},
            )
        return _jobs[job_id]
    except Exception as exc:
        await _persist_job(job_id, status="failed", result={"action": action, "error": str(exc)})
        return _jobs[job_id]


async def _run_tool_status_probe(tool: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Non-destructive readiness probe for integration tooling."""
    payload = params or {}
    job_id = await _new_running_job(tool, {"action": "status", "params": payload})
    try:
        docker_bin = _tool_binary("docker")
        docker_containers: List[Dict[str, str]] = []
        if docker_bin:
            rc, out, _ = await _run_subprocess([docker_bin, "ps", "--format", "{{.Image}}|{{.Names}}"], timeout=15)
            if rc == 0:
                for line in (out or "").splitlines():
                    if "|" not in line:
                        continue
                    image, name = line.split("|", 1)
                    docker_containers.append({"image": image.strip(), "name": name.strip()})

        def _matching_containers(tokens: List[str]) -> List[Dict[str, str]]:
            lowered_tokens = [str(t).lower() for t in tokens if t]
            matches: List[Dict[str, str]] = []
            for row in docker_containers:
                image = str(row.get("image") or "").lower()
                name = str(row.get("name") or "").lower()
                if any(token in image or token in name for token in lowered_tokens):
                    matches.append(row)
            return matches

        if tool == "amass":
            parser = Path(__file__).resolve().parent.parent / "unified_agent" / "integrations" / "amass" / "parse_amass.py"
            result = {
                "available": bool(docker_bin),
                "docker_available": bool(docker_bin),
                "image": "caffix/amass:latest",
                "running_containers": _matching_containers(["amass", "caffix/amass"]),
                "parser_available": parser.exists(),
                "parser_path": str(parser),
            }
        elif tool == "velociraptor":
            result = {
                "available": bool(docker_bin),
                "docker_available": bool(docker_bin),
                "image": "wlambert/velociraptor:latest",
                "running_containers": _matching_containers(["velociraptor", "wlambert/velociraptor"]),
            }
        elif tool == "purplesharp":
            script = Path(__file__).resolve().parent.parent / "unified_agent" / "integrations" / "purplesharp" / "run_purplesharp.sh"
            result = {
                "available": script.exists(),
                "script_path": str(script),
                "pwsh_available": bool(_tool_binary("pwsh") or _tool_binary("powershell")),
            }
        elif tool == "arkime":
            parser = Path(__file__).resolve().parent.parent / "unified_agent" / "integrations" / "arkime" / "parse_arkime.py"
            result = {
                "available": bool(docker_bin),
                "docker_available": bool(docker_bin),
                "image": "quay.io/arkime/arkime:latest",
                "running_containers": _matching_containers(["arkime"]),
                "parser_available": parser.exists(),
                "parser_path": str(parser),
            }
        elif tool == "bloodhound":
            parser = Path(__file__).resolve().parent.parent / "unified_agent" / "integrations" / "bloodhound" / "parse_bloodhound.py"
            result = {
                "available": bool(docker_bin),
                "docker_available": bool(docker_bin),
                "image": "specterops/bloodhound:latest",
                "running_containers": _matching_containers(["bloodhound", "neo4j"]),
                "parser_available": parser.exists(),
                "parser_path": str(parser),
            }
        elif tool == "spiderfoot":
            result = {
                "available": bool(docker_bin),
                "docker_available": bool(docker_bin),
                "image": "ctdc/spiderfoot:latest",
                "running_containers": _matching_containers(["spiderfoot"]),
            }
        elif tool == "sigma":
            from sigma_engine import sigma_engine

            result = {"available": True, "engine": sigma_engine.get_status()}
        elif tool == "atomic":
            import importlib

            atomic_module = importlib.import_module("atomic_validation")
            manager = getattr(atomic_module, "atomic_validation")
            manager.set_db(get_db())
            jobs = manager.list_jobs()
            result = {
                "available": True,
                "status": manager.get_status(),
                "jobs_count": int((jobs or {}).get("count") or 0) if isinstance(jobs, dict) else 0,
            }
        elif tool == "clamav":
            clam_bin = _tool_binary("clamscan") or _tool_binary("clamdscan")
            version_str = ""
            if clam_bin:
                rc, out, _ = await _run_subprocess([clam_bin, "--version"], timeout=10)
                version_str = (out or "").strip().splitlines()[0] if out else ""
            result = {
                "available": clam_bin is not None or bool(_matching_containers(["clamav"])),
                "binary": clam_bin,
                "version": version_str,
                "running_containers": _matching_containers(["clamav", "seraph-clamav"]),
                "image": "clamav/clamav:stable",
            }
        else:
            result = {"available": True}
        await _persist_job(job_id, status="completed", result={"action": "status", "result": result})
        return _jobs[job_id]
    except Exception as exc:
        await _persist_job(job_id, status="failed", result={"action": "status", "error": str(exc)})
        return _jobs[job_id]


async def run_runtime_tool(
    *,
    tool: str,
    params: Dict[str, Any] = None,
    runtime_target: str = "server",
    agent_id: str = None,
    actor: str = "integration_runtime",
    governance_context: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Unified runtime launcher for security integrations.
    runtime_target:
      - server: execute on backend runtime
      - unified_agent_local/unified_agent_remote: queue command to a unified agent
    """
    t = str(tool or "").strip().lower()
    if t not in SUPPORTED_RUNTIME_TOOLS:
        raise ValueError(f"Unsupported tool '{tool}'. Supported: {sorted(SUPPORTED_RUNTIME_TOOLS)}")
    rt = str(runtime_target or "server").strip().lower()
    payload = dict(params or {})
    payload["runtime_target"] = rt
    action = str(payload.get("action") or "").strip().lower()
    context = governance_context or {
        "approved": True,
        "decision_id": "integration-runtime-direct",
        "queue_id": "integration-runtime-direct",
    }
    if rt in {"unified_agent_local", "unified_agent_remote", "agent", "unified_agent"}:
        db = get_db()
        resolved_agent_id = str(agent_id or "").strip()
        if not resolved_agent_id and db is not None:
            agent = await db.unified_agents.find_one(
                {"status": {"$in": ["online", "healthy"]}},
                {"_id": 0, "agent_id": 1},
            )
            if not agent:
                agent = await db.unified_agents.find_one({}, {"_id": 0, "agent_id": 1})
            if agent:
                resolved_agent_id = str(agent.get("agent_id") or "").strip()
        if resolved_agent_id:
            payload["agent_id"] = resolved_agent_id
        if not resolved_agent_id:
            job_id = await _new_job(t, {"runtime_target": rt, "params": payload})
            await _persist_job(job_id, status="failed", result={"error": "no_unified_agent_available"})
            return _jobs[job_id]
        job_id = await _new_job(t, {"runtime_target": rt, "agent_id": resolved_agent_id, "params": payload})
        return await _queue_unified_agent_runtime(
            job_id=job_id,
            tool=t,
            params=payload,
            actor=actor,
            agent_id=resolved_agent_id,
        )

    if action == "status" and t in {"amass", "velociraptor", "purplesharp", "arkime", "bloodhound", "spiderfoot", "clamav"}:
        return await _run_tool_status_probe(t, payload)

    # Default (no action specified) for tools that need params falls back to status probe
    if not action and t in {"amass", "purplesharp"}:
        return await _run_tool_status_probe(t, payload)

    async with _get_runtime_semaphore():
        if t == "amass":
            domain = str(payload.get("domain") or "").strip()
            if not domain:
                job_id = await _new_job("amass", {"runtime_target": rt, "params": payload})
                await _persist_job(job_id, status="failed", result={"error": "domain_required"})
                return _jobs[job_id]
            return await run_amass(domain, governance_context=context)
        if t == "velociraptor":
            return await run_velociraptor(collection_name=payload.get("collection_name"), governance_context=context)
        if t == "purplesharp":
            return await run_purplesharp(target=payload.get("target"), options=payload.get("options"), governance_context=context)
        if t == "arkime":
            return await run_arkime(governance_context=context, params=payload)
        if t == "bloodhound":
            return await run_bloodhound(governance_context=context, params=payload)
        if t == "spiderfoot":
            return await run_spiderfoot(governance_context=context, params=payload)
        if t == "sigma":
            return await run_sigma(governance_context=context, params=payload)
        if t == "atomic":
            return await run_atomic(governance_context=context, params=payload)
        if t == "trivy":
            return await run_trivy(governance_context=context, params=payload)
        if t == "falco":
            return await run_falco(governance_context=context, params=payload)
        if t == "suricata":
            return await run_suricata(governance_context=context, params=payload)
        if t == "yara":
            return await run_yara(governance_context=context, params=payload)
        if t == "osquery":
            return await run_osquery(governance_context=context, params=payload)
        if t == "zeek":
            return await run_zeek(governance_context=context, params=payload)
        if t == "cuckoo":
            return await run_cuckoo(governance_context=context, params=payload)
        if t == "clamav":
            return await run_clamav(governance_context=context, params=payload)
    raise ValueError(f"Unsupported tool '{tool}'")


async def ingest_host_logs(source: str, raw_text: str) -> Dict[str, Any]:
    """Parse Sysmon or auditd log text to extract IOCs and ingest them.

    This is a heuristic parser: extracts IPs, domains, file hashes, and common indicators.
    """
    job_id = await _new_job("host_ingest", {"source": source})
    _jobs[job_id]["status"] = "running"
    _jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()
    try:
        import re
        ips = set(re.findall(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", raw_text))
        domains = set(re.findall(r"\b([a-zA-Z0-9.-]+\.[a-zA-Z]{2,6})\b", raw_text))
        sha256s = set(re.findall(r"\b[a-fA-F0-9]{64}\b", raw_text))

        indicators = []
        for ip in ips:
            indicators.append({'type': 'ip', 'value': ip, 'confidence': 60})
        for d in domains:
            indicators.append({'type': 'domain', 'value': d, 'confidence': 50})
        for h in sha256s:
            indicators.append({'type': 'sha256', 'value': h, 'confidence': 60})

        res = await threat_intel.ingest_indicators(source, indicators)
        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["result"] = res
        _jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()
        return _jobs[job_id]
    except Exception as e:
        logger.exception("Host log ingest failed")
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["result"] = {"error": str(e)}
        _jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()
        return _jobs[job_id]


def stop_scheduler():
    global _scheduler_task
    if _scheduler_task:
        _scheduler_task.cancel()
        _scheduler_task = None
