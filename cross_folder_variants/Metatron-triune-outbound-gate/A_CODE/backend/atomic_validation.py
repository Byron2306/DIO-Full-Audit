import json
import os
import shlex
import shutil
import subprocess
import uuid
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import asyncio
import yaml

try:
    from runtime_paths import ensure_data_dir
except Exception:
    from backend.runtime_paths import ensure_data_dir

REPO_ROOT = Path(__file__).resolve().parents[1]
BUNDLED_PWSH_CANDIDATES = (
    REPO_ROOT / "tools" / "powershell" / "pwsh",
    REPO_ROOT / "tools" / "powershell" / "pwsh.exe",
)

try:
    import winrm
except Exception:
    winrm = None

try:
    from services.world_events import emit_world_event
except Exception:
    try:
        from backend.services.world_events import emit_world_event
    except Exception:
        emit_world_event = None

try:
    from soar_engine import soar_engine as _soar_engine
except Exception:
    try:
        from backend.soar_engine import soar_engine as _soar_engine
    except Exception:
        _soar_engine = None


ARCHIVED_SOAR_EXECUTION_PATH = Path(
    os.environ.get(
        "MITRE_ARCHIVED_SOAR_EXECUTION_PATH",
        str(REPO_ROOT / "backend" / "data" / "soar_executions_archive.json"),
    )
)


class AtomicValidationManager:
    def __init__(self):
        self.enabled = os.environ.get("ATOMIC_VALIDATION_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
        self.atomic_root = Path(os.environ.get("ATOMIC_RED_TEAM_PATH", "/opt/atomic-red-team/atomics"))
        self.atomic_powershell_config = Path(
            os.environ.get("ATOMIC_POWERSHELL_CONFIG", "config/atomic_powershell.yml")
        )
        configured_results_dir = Path(
            os.environ.get("ATOMIC_VALIDATION_RESULTS_DIR", "/var/lib/seraph-ai/atomic-validation")
        )
        self.runner = os.environ.get("ATOMIC_RUNNER", "auto").strip()
        self.module_path = os.environ.get("PWSH_MODULE_PATH", "Invoke-AtomicRedTeam")
        self.db = None
        self.default_runner_profile = os.environ.get("ATOMIC_DEFAULT_RUNNER_PROFILE", "").strip()
        self.runner_profiles: List[Dict[str, Any]] = []

        # Sandbox isolation: when ATOMIC_SANDBOX_IMAGE is set, each job is executed
        # in a fresh Docker sibling container (--network none, --cap-drop ALL) rather
        # than directly inside the privileged backend process.
        self.sandbox_image = os.environ.get("ATOMIC_SANDBOX_IMAGE", "").strip()
        # Host-side paths for bind-mounts passed to sibling sandbox containers.
        # These must be host-visible paths (not container-internal paths) because
        # the Docker socket spawns containers on the host, not inside this container.
        self.sandbox_atomic_host_path = os.environ.get("ATOMIC_RED_TEAM_HOST_PATH", "").strip()
        self.sandbox_invoke_host_path = os.environ.get("INVOKE_ATOMICREDTEAM_HOST_PATH", "").strip()
        # Optional host-side path to the bundled PowerShell distribution (tools/powershell).
        # If omitted, we try to derive it from ATOMIC_RED_TEAM_HOST_PATH's parent folder.
        self.sandbox_pwsh_host_path = os.environ.get("ATOMIC_PWSH_HOST_PATH", "").strip()
        if not self.sandbox_pwsh_host_path and self.sandbox_atomic_host_path:
            try:
                self.sandbox_pwsh_host_path = str(
                    Path(self.sandbox_atomic_host_path).resolve().parent / "tools" / "powershell"
                )
            except Exception:
                self.sandbox_pwsh_host_path = ""
        # Named volume that holds run result JSON files; shared between backend and sandbox.
        self.sandbox_validation_volume = os.environ.get(
            "ATOMIC_VALIDATION_VOLUME", "metatron-triune-outbound-gate_atomic_validation_reports"
        ).strip()

        try:
            configured_results_dir.mkdir(parents=True, exist_ok=True)
            self.results_dir = configured_results_dir
        except OSError:
            self.results_dir = ensure_data_dir("atomic-validation")

        self.jobs = [
            {
                "job_id": "weekly-t1059",
                "name": "Command and Scripting Interpreter Validation",
                "description": "Execute Atomic tests for T1059 to validate script interpreter detections.",
                "techniques": ["T1059", "T1059.001", "T1059.003"],
                "default_test_guids": [],
                "priority": "high",
                "frequency": "weekly",
            },
            {
                "job_id": "weekly-t1547",
                "name": "Boot/Logon Autostart Persistence Validation",
                "description": "Validate persistence detections with Atomic tests for startup artifacts.",
                "techniques": ["T1547", "T1547.001"],
                "default_test_guids": [],
                "priority": "high",
                "frequency": "weekly",
            },
            {
                "job_id": "weekly-t1003",
                "name": "Credential Dumping Validation",
                "description": "Validate credential access telemetry and detections using Atomic tests.",
                "techniques": ["T1003", "T1003.001", "T1555"],
                "default_test_guids": [],
                "priority": "critical",
                "frequency": "weekly",
            },
            {
                "job_id": "weekly-t1041",
                "name": "Exfiltration Over C2 Validation",
                "description": "Run exfiltration-focused emulation scenarios and verify C2/exfil analytics.",
                "techniques": ["T1041", "T1048"],
                "default_test_guids": [],
                "priority": "high",
                "frequency": "weekly",
            },
            {
                "job_id": "weekly-t1562",
                "name": "Defense Evasion Validation",
                "description": "Validate security controls tampering and evasion detections.",
                "techniques": ["T1562", "T1562.001", "T1027"],
                "default_test_guids": [],
                "priority": "high",
                "frequency": "weekly",
            },
        ]
        self.jobs_source = "built_in"
        self._load_atomic_powershell_config()

    def _load_atomic_powershell_config(self) -> None:
        if not self.atomic_powershell_config.exists():
            return
        try:
            with open(self.atomic_powershell_config, "r", encoding="utf-8") as handle:
                payload = yaml.safe_load(handle) or {}
        except Exception:
            return

        if not isinstance(payload, dict):
            return

        def _expand(value: Any) -> Any:
            if isinstance(value, str):
                return os.path.expandvars(value)
            if isinstance(value, dict):
                return {k: _expand(v) for k, v in value.items()}
            if isinstance(value, list):
                return [_expand(v) for v in value]
            return value

        payload = _expand(payload)

        runner = str(payload.get("runner") or "").strip()
        if runner:
            self.runner = runner
        default_runner_profile = str(payload.get("default_runner_profile") or "").strip()
        if default_runner_profile:
            self.default_runner_profile = default_runner_profile
        module_path = str(payload.get("module_path") or "").strip()
        if module_path:
            self.module_path = module_path
        atomic_root = str(payload.get("atomic_root") or "").strip()
        if atomic_root:
            self.atomic_root = Path(atomic_root)

        configured_profiles = payload.get("runner_profiles")
        if isinstance(configured_profiles, list):
            parsed_profiles: List[Dict[str, Any]] = []
            for profile in configured_profiles:
                if not isinstance(profile, dict):
                    continue
                profile_id = str(profile.get("profile_id") or "").strip()
                profile_type = str(profile.get("type") or "local").strip().lower()
                if not profile_id:
                    continue
                def _parse_int(value: Any, default: int) -> int:
                    try:
                        return int(value)
                    except Exception:
                        return default
                parsed_profiles.append(
                    {
                        "profile_id": profile_id,
                        "type": profile_type,
                        "enabled": bool(profile.get("enabled", True)),
                        "description": str(profile.get("description") or "").strip(),
                        "platforms": [str(p).strip().lower() for p in (profile.get("platforms") or []) if str(p).strip()],
                        "runner": str(profile.get("runner") or "").strip(),
                        "module_path": str(profile.get("module_path") or "").strip(),
                        "atomic_root": str(profile.get("atomic_root") or "").strip(),
                        "sandbox_image": str(profile.get("sandbox_image") or "").strip(),
                        "sandbox_atomic_host_path": str(profile.get("sandbox_atomic_host_path") or "").strip(),
                        "sandbox_invoke_host_path": str(profile.get("sandbox_invoke_host_path") or "").strip(),
                        "sandbox_validation_volume": str(profile.get("sandbox_validation_volume") or "").strip(),
                        "remote_host": str(profile.get("remote_host") or "").strip(),
                        "remote_user": str(profile.get("remote_user") or "").strip(),
                        "remote_port": _parse_int(profile.get("remote_port"), 22),
                        "ssh_key_path": str(profile.get("ssh_key_path") or "").strip(),
                        "ssh_options": [str(o).strip() for o in (profile.get("ssh_options") or []) if str(o).strip()],
                        "password_env": str(profile.get("password_env") or "").strip(),
                        "remote_shell": str(profile.get("remote_shell") or "pwsh").strip(),
                        "winrm_transport": str(profile.get("winrm_transport") or "ntlm").strip().lower(),
                        "winrm_server_cert_validation": str(profile.get("winrm_server_cert_validation") or "ignore").strip().lower(),
                    }
                )
            self.runner_profiles = parsed_profiles

        configured_jobs = payload.get("jobs")
        if not isinstance(configured_jobs, list):
            return

        parsed_jobs: List[Dict] = []
        for job in configured_jobs:
            if not isinstance(job, dict):
                continue
            job_id = str(job.get("job_id") or "").strip()
            name = str(job.get("name") or "").strip()
            if not job_id or not name:
                continue
            techniques = [str(t).strip() for t in (job.get("techniques") or []) if str(t).strip()]
            if not techniques:
                continue
            parsed_jobs.append(
                {
                    "job_id": job_id,
                    "name": name,
                    "description": str(job.get("description") or "").strip(),
                    "techniques": techniques,
                    "default_test_guids": [str(g).strip() for g in (job.get("default_test_guids") or []) if str(g).strip()],
                    "priority": str(job.get("priority") or "high").strip(),
                    "frequency": str(job.get("frequency") or "weekly").strip(),
                    "runner_profile": str(job.get("runner_profile") or "").strip(),
                    "skip_prereqs": bool(job.get("skip_prereqs", False)),
                    "show_details_brief": bool(job.get("show_details_brief", False)),
                }
            )

        if parsed_jobs:
            self.jobs = parsed_jobs
            self.jobs_source = "atomic_powershell.yml"

    def set_db(self, db):
        self.db = db

    def _emit_atomic_event(self, event_type: str, entity_refs: Optional[List[str]] = None, payload: Optional[Dict] = None):
        if emit_world_event is None or self.db is None:
            return
        try:
            asyncio.run(
                emit_world_event(
                    self.db,
                    event_type=event_type,
                    entity_refs=entity_refs or [],
                    payload=payload or {},
                    trigger_triune=False,
                    source="backend.atomic_validation",
                )
            )
        except Exception:
            pass

    def _trigger_soar_for_techniques(self, techniques_executed: List[str], job_id: str, run_id: str) -> None:
        """
        When an atomic job completes successfully, fire a SOAR trigger event so the
        validated techniques gain soar_execution_* evidence for S5 MITRE scoring.
        The trigger uses the 'atomic_validation_completed' event type and lists the
        validated technique IDs so _collect_soar_record_techniques picks them up.
        """
        if not techniques_executed:
            return
        if _soar_engine is None:
            self._archive_soar_execution(techniques_executed, job_id, run_id, reason="live_soar_unavailable")
            return
        try:
            normalized_job_id = str(job_id or "").strip().lower()
            event = {
                "trigger_type": "anomaly_detected",
                "source": "atomic_validation",
                "job_id": job_id,
                "run_id": run_id,
                "validated_techniques": techniques_executed,
                # Embed technique IDs in a string field so _extract_attack_techniques
                # finds them via regex scan of the execution record dict.
                "mitre_techniques_validated": " ".join(techniques_executed),
                "confidence": "high",
                "validation_status": "validated",
                "severity": "high",
            }

            # Align atomic validation events with existing active SOAR playbooks.
            if "execution" in normalized_job_id:
                event.update(
                    {
                        "trigger_type": "suspicious_process",
                    }
                )
            elif "discovery" in normalized_job_id or "initial-access-recon" in normalized_job_id:
                event.update(
                    {
                        "trigger_type": "autonomous_recon",
                        "machine_likelihood": "high",
                        "intents": "recon",
                        "burstiness": "high",
                    }
                )
            elif "credential-access" in normalized_job_id:
                event.update(
                    {
                        "trigger_type": "rapid_credential_access",
                        "machine_likelihood": "high",
                        "intents": "credential_access",
                    }
                )
            elif "defense-evasion" in normalized_job_id:
                event.update(
                    {
                        "trigger_type": "tool_chain_switching",
                    }
                )
            elif "persistence" in normalized_job_id:
                event.update(
                    {
                        "trigger_type": "goal_persistent_loop",
                        "goal_persistence": "high",
                        "machine_likelihood": "high",
                    }
                )
            elif "collection-exfil" in normalized_job_id:
                event.update(
                    {
                        "trigger_type": "ai_exfiltration_pattern",
                        "machine_likelihood": "high",
                        "intents": "exfil_prep",
                    }
                )
            elif "c2-lateral" in normalized_job_id or "lateral-access" in normalized_job_id:
                event.update(
                    {
                        "trigger_type": "automated_lateral_movement",
                        "machine_likelihood": "high",
                        "intents": "lateral_movement",
                        "tool_switch_latency": "fast",
                    }
                )
            if "privilege-escalation" in normalized_job_id:
                event.update(
                    {
                        "trigger_type": "suspicious_process",
                        "technique": "privilege_escalation",
                        "severity": "high",
                    }
                )
            elif "impact" in normalized_job_id:
                event.update(
                    {
                        "trigger_type": "ransomware_detected",
                        "severity": "critical",
                    }
                )

            executions = asyncio.run(_soar_engine.trigger_playbooks(event))
            if executions:
                self._persist_soar_execution_records([self._serialize_soar_execution(execution) for execution in executions])
            else:
                self._archive_soar_execution(techniques_executed, job_id, run_id, reason="live_soar_no_match")
        except Exception:
            self._archive_soar_execution(techniques_executed, job_id, run_id, reason="live_soar_trigger_failed")

    def _serialize_soar_execution(self, execution: Any) -> Dict[str, Any]:
        payload = asdict(execution)
        trigger_event = payload.get("trigger_event")
        if isinstance(trigger_event, dict):
            trigger_event.pop("_id", None)
        for step in payload.get("step_results") or []:
            if isinstance(step, dict):
                step.pop("_id", None)
        return payload

    def _persist_soar_execution_records(self, payloads: List[Dict[str, Any]]) -> None:
        if not payloads:
            return
        try:
            ARCHIVED_SOAR_EXECUTION_PATH.parent.mkdir(parents=True, exist_ok=True)
            if ARCHIVED_SOAR_EXECUTION_PATH.exists():
                existing = json.loads(ARCHIVED_SOAR_EXECUTION_PATH.read_text(encoding="utf-8"))
                if not isinstance(existing, list):
                    existing = []
            else:
                existing = []
            existing_by_id = {
                row.get("id"): row
                for row in existing
                if isinstance(row, dict) and row.get("id")
            }
            for payload in payloads:
                payload_id = payload.get("id") if isinstance(payload, dict) else None
                if payload_id:
                    existing_by_id[payload_id] = payload
            ARCHIVED_SOAR_EXECUTION_PATH.write_text(
                json.dumps(list(existing_by_id.values()), indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _archive_soar_execution(self, techniques_executed: List[str], job_id: str, run_id: str, *, reason: str) -> None:
        payload = {
            "id": f"atomic-{run_id}",
            "playbook_id": f"atomic-validation-{job_id}",
            "playbook_name": f"Atomic Validation {job_id}",
            "trigger_event": {
                "trigger_type": "anomaly_detected",
                "source": "atomic_validation",
                "job_id": job_id,
                "run_id": run_id,
                "validated_techniques": techniques_executed,
                "mitre_techniques": techniques_executed,
                "mitre_techniques_validated": " ".join(techniques_executed),
                "reason": reason,
            },
            "status": "completed",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "step_results": [],
        }
        self._persist_soar_execution_records([payload])

    def _resolve_runner(self, requested: Optional[str] = None) -> Optional[str]:
        requested = (requested or self.runner or "auto").strip()
        if requested and requested.lower() not in {"auto", "default"}:
            # Handle absolute paths directly
            if os.path.isabs(requested) and os.path.exists(requested):
                return requested
            resolved = shutil.which(requested)
            if resolved:
                return resolved
        for candidate in ("pwsh", "powershell", "powershell.exe", "pwsh.exe"):
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        for candidate in BUNDLED_PWSH_CANDIDATES:
            if candidate.exists():
                return str(candidate)
        return None

    def _runner_available(self) -> bool:
        return self._resolve_runner() is not None

    @staticmethod
    def _ps_quote(value: str) -> str:
        return "'" + str(value or "").replace("'", "''") + "'"

    def _default_profiles(self) -> List[Dict[str, Any]]:
        profiles: List[Dict[str, Any]] = [
            {
                "profile_id": "local-direct",
                "type": "local",
                "enabled": True,
                "description": "Direct local PowerShell execution inside backend container",
                "platforms": ["linux"],
                "runner": self.runner,
                "module_path": str(self.module_path),
                "atomic_root": self.atomic_root.as_posix(),
            }
        ]
        if self.sandbox_image:
            profiles.insert(
                0,
                {
                    "profile_id": "linux-sandbox",
                    "type": "docker",
                    "enabled": True,
                    "description": "Linux sibling Docker sandbox",
                    "platforms": ["linux", "containers"],
                    "runner": self.runner,
                    "module_path": str(self.module_path),
                    "atomic_root": "/opt/atomic-red-team/atomics",
                    "sandbox_image": self.sandbox_image,
                    "sandbox_atomic_host_path": self.sandbox_atomic_host_path,
                    "sandbox_invoke_host_path": self.sandbox_invoke_host_path,
                    "sandbox_validation_volume": self.sandbox_validation_volume,
                },
            )
        return profiles

    def _all_runner_profiles(self) -> List[Dict[str, Any]]:
        merged: List[Dict[str, Any]] = []
        seen = set()
        for profile in self.runner_profiles + self._default_profiles():
            profile_id = str(profile.get("profile_id") or "").strip()
            if not profile_id or profile_id in seen:
                continue
            merged.append(profile)
            seen.add(profile_id)
        return merged

    def _resolve_runner_profile(self, requested_profile: str = "") -> Dict[str, Any]:
        profiles = [profile for profile in self._all_runner_profiles() if profile.get("enabled", True)]
        if not profiles:
            return {}
        profile_id = (requested_profile or self.default_runner_profile or "").strip()
        if profile_id:
            for profile in profiles:
                if profile.get("profile_id") == profile_id:
                    return profile
        return profiles[0]

    def _atomic_available(self) -> bool:
        return self.atomic_root.exists()

    def _resolve_atomic_root(self) -> Path:
        """Resolve the actual Atomic Red Team root visible inside the backend container."""
        candidates = [self.atomic_root]
        if self.atomic_root.name != "atomics":
            candidates.append(self.atomic_root / "atomics")
        candidates.extend([
            Path("/opt/atomic-red-team/atomics"),
            Path("/opt/atomic-red-team"),
        ])
        for candidate in candidates:
            try:
                if candidate.exists():
                    return candidate
            except Exception:
                continue
        return self.atomic_root

    def _technique_has_atomic(self, technique: str, atomic_root: str) -> bool:
        normalized = str(technique or "").strip().upper()
        if not normalized:
            return False
        root_path = Path(atomic_root)
        yaml_path = root_path / normalized / f"{normalized}.yaml"
        return yaml_path.exists()

    def _filter_runnable_techniques(self, techniques: List[str], atomic_root: str) -> List[str]:
        runnable: List[str] = []
        seen = set()
        for technique in techniques or []:
            normalized = str(technique or "").strip().upper()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            if self._technique_has_atomic(normalized, atomic_root):
                runnable.append(normalized)
        return runnable

    def _host_atomic_root_for_profile(self, profile: Optional[Dict[str, Any]]) -> str:
        if not profile:
            return self.atomic_root.as_posix()
        profile_type = str(profile.get("type") or "local").strip().lower()
        atomic_root = str(profile.get("atomic_root") or self.atomic_root.as_posix()).strip()
        if profile_type in {"winrm", "ssh"}:
            return self.atomic_root.as_posix()
        # For docker sandbox profiles, this function is used for preflight checks (YAML existence)
        # inside the current backend process. The backend container typically has atomics mounted
        # at /opt/atomic-red-team/atomics, while the sandbox uses host-side bind mounts when
        # spawning sibling containers via the host Docker socket. Host filesystem paths (e.g.
        # /home/.../atomic-red-team/atomics) are not visible from inside the backend container,
        # so do NOT use them for existence checks here.
        return atomic_root

    def _build_invoke_script(
        self,
        techniques: List[str],
        *,
        atomic_root: str,
        host_atomic_root: Optional[str] = None,
        module_path: str,
        show_details_brief: bool = False,
        skip_prereqs: bool = False,
    ) -> str:
        technique_list = self._filter_runnable_techniques(techniques, host_atomic_root or atomic_root)
        if not technique_list:
            raise ValueError(
                f"Atomic validation skipped: no runnable atomic YAML found for requested techniques under {host_atomic_root or atomic_root}"
            )
        import_cmd = f"Import-Module {self._ps_quote(module_path)} -ErrorAction Stop" if module_path else "Import-Module Invoke-AtomicRedTeam -ErrorAction Stop"
        show_details = " -ShowDetailsBrief" if show_details_brief else ""
        prereqs = " -SkipPrereqs" if skip_prereqs else ""
        invoke_cmds = "; ".join(
            f"Invoke-AtomicTest {t} -PathToAtomicsFolder {self._ps_quote(atomic_root)}{show_details}{prereqs}"
            for t in technique_list
        )
        return (
            f"{import_cmd}; "
            f"$env:PathToAtomicsFolder={self._ps_quote(atomic_root)}; "
            f"{invoke_cmds}"
        )

    def _build_command(self, techniques: List[str], *, show_details_brief: bool = False, skip_prereqs: bool = False) -> List[str]:
        runner = self._resolve_runner() or self.runner or "pwsh"
        script = self._build_invoke_script(
            techniques,
            atomic_root=self.atomic_root.as_posix(),
            host_atomic_root=self.atomic_root.as_posix(),
            module_path=str(self.module_path),
            show_details_brief=show_details_brief,
            skip_prereqs=skip_prereqs,
        )
        return [runner, "-NoProfile", "-Command", script]

    def _build_sandbox_command(
        self,
        techniques: List[str],
        run_id: str,
        profile: Optional[Dict[str, Any]] = None,
        *,
        show_details_brief: bool = False,
        skip_prereqs: bool = False,
    ) -> Optional[List[str]]:
        """Wrap the pwsh atomic command in a Docker sandbox container.

        Returns None if sandbox is not configured (caller falls back to direct exec).
        The sandbox container runs with --network none and --cap-drop ALL so that
        atomic tests are isolated from the host network and kernel surface.
        """
        profile = profile or {}
        sandbox_image = str(profile.get("sandbox_image") or self.sandbox_image or "").strip()
        if not sandbox_image:
            return None

        profile_runner = str(profile.get("runner") or self.runner or "pwsh").strip()
        module_path = str(profile.get("module_path") or self.module_path or "Invoke-AtomicRedTeam").strip()
        atomic_root = str(profile.get("atomic_root") or "/opt/atomic-red-team/atomics").strip()
        sandbox_atomic_host_path = str(profile.get("sandbox_atomic_host_path") or self.sandbox_atomic_host_path or "").strip()
        # Use the container-visible atomic root for YAML existence checks; the sandbox container
        # itself is mounted from host paths later via `sandbox_atomic_host_path`.
        host_atomic_root = atomic_root
        pwsh_cmd = [
            profile_runner,
            "-NoProfile",
            "-Command",
            self._build_invoke_script(
                techniques,
                atomic_root=atomic_root,
                host_atomic_root=host_atomic_root,
                module_path=module_path,
                show_details_brief=show_details_brief,
                skip_prereqs=skip_prereqs,
            ),
        ]
        # Note: the sandbox image may not have pwsh installed. We bind-mount the
        # repo-bundled PowerShell distribution (tools/powershell) into /opt/pwsh
        # when available and, if the runner is `pwsh`, switch to /opt/pwsh/pwsh.

        cmd = [
            "docker", "run", "--rm",
            "--name", f"seraph-atomic-{run_id[:12]}",
            "--network", "none",
            "--cap-drop", "ALL",
            "--cap-add", "SETUID",
            "--cap-add", "SETGID",
            "--cap-add", "CHOWN",
            "--cap-add", "DAC_OVERRIDE",
            "--cap-add", "FOWNER",
            "--cap-add", "SYS_PTRACE",
            "--security-opt", "no-new-privileges:false",
        ]

        # Bind-mount atomics and invoke-atomicredteam from host paths
        sandbox_invoke_host_path = str(profile.get("sandbox_invoke_host_path") or self.sandbox_invoke_host_path or "").strip()
        sandbox_validation_volume = str(profile.get("sandbox_validation_volume") or self.sandbox_validation_volume or "").strip()
        sandbox_pwsh_host_path = str(profile.get("sandbox_pwsh_host_path") or self.sandbox_pwsh_host_path or "").strip()
        if sandbox_atomic_host_path:
            cmd += ["-v", f"{sandbox_atomic_host_path}:/opt/atomic-red-team:ro"]
        if sandbox_invoke_host_path:
            cmd += ["-v", f"{sandbox_invoke_host_path}:/opt/invoke-atomicredteam:ro"]
        if sandbox_pwsh_host_path:
            cmd += ["-v", f"{sandbox_pwsh_host_path}:/opt/pwsh:ro"]
            if profile_runner == "pwsh":
                pwsh_cmd[0] = "/opt/pwsh/pwsh"

        # Named volume for results — shared with the backend
        if sandbox_validation_volume:
            cmd += ["-v", f"{sandbox_validation_volume}:/var/lib/seraph-ai/atomic-validation"]

        cmd.append(sandbox_image)
        cmd.extend(pwsh_cmd)
        return cmd

    def _build_ssh_command(
        self,
        techniques: List[str],
        profile: Dict[str, Any],
        *,
        show_details_brief: bool = False,
        skip_prereqs: bool = False,
    ) -> List[str]:
        remote_host = str(profile.get("remote_host") or "").strip()
        remote_user = str(profile.get("remote_user") or "").strip()
        if not remote_host:
            raise ValueError("ssh runner profile missing remote_host")
        remote_target = f"{remote_user}@{remote_host}" if remote_user else remote_host
        remote_shell = str(profile.get("remote_shell") or "pwsh").strip()
        remote_port = int(profile.get("remote_port") or 22)
        module_path = str(profile.get("module_path") or self.module_path or "Invoke-AtomicRedTeam").strip()
        atomic_root = str(profile.get("atomic_root") or self.atomic_root.as_posix()).strip()
        host_atomic_root = self._host_atomic_root_for_profile(profile)
        remote_script = self._build_invoke_script(
            techniques,
            atomic_root=atomic_root,
            host_atomic_root=host_atomic_root,
            module_path=module_path,
            show_details_brief=show_details_brief,
            skip_prereqs=skip_prereqs,
        )
        remote_cmd = " ".join(
            shlex.quote(part)
            for part in [remote_shell, "-NoProfile", "-NonInteractive", "-Command", remote_script]
        )
        cmd = ["ssh", "-p", str(remote_port)]
        ssh_key_path = str(profile.get("ssh_key_path") or "").strip()
        if ssh_key_path:
            cmd += ["-i", ssh_key_path]
        for opt in (profile.get("ssh_options") or []):
            cmd += ["-o", str(opt)]
        cmd += [remote_target, remote_cmd]
        return cmd

    def _build_winrm_command(
        self,
        techniques: List[str],
        profile: Dict[str, Any],
        *,
        show_details_brief: bool = False,
        skip_prereqs: bool = False,
    ) -> List[str]:
        remote_host = str(profile.get("remote_host") or "").strip()
        remote_user = str(profile.get("remote_user") or "").strip()
        remote_port = int(profile.get("remote_port") or 5985)
        if not remote_host:
            raise ValueError("winrm runner profile missing remote_host")
        if winrm is not None:
            password_env = str(profile.get("password_env") or "").strip()
            return [
                "pywinrm",
                remote_host,
                remote_user or "",
                password_env,
                str(remote_port),
                *techniques,
            ]
        runner = self._resolve_runner(str(profile.get("runner") or self.runner or ""))
        if not runner:
            raise ValueError("winrm runner profile requires a local PowerShell executable")
        password_env = str(profile.get("password_env") or "").strip()
        module_path = str(profile.get("module_path") or self.module_path or "Invoke-AtomicRedTeam").strip()
        atomic_root = str(profile.get("atomic_root") or self.atomic_root.as_posix()).strip()
        inner_script = self._build_invoke_script(
            techniques,
            atomic_root=atomic_root,
            host_atomic_root=atomic_root,
            module_path=module_path,
            show_details_brief=show_details_brief,
            skip_prereqs=skip_prereqs,
        )
        if remote_user and password_env:
            outer_script = (
                f"$sec = ConvertTo-SecureString $env:{password_env} -AsPlainText -Force; "
                f"$cred = New-Object System.Management.Automation.PSCredential({self._ps_quote(remote_user)}, $sec); "
                f"Invoke-Command -ComputerName {self._ps_quote(remote_host)} -Credential $cred -ScriptBlock {{ {inner_script} }}"
            )
        else:
            outer_script = (
                f"Invoke-Command -ComputerName {self._ps_quote(remote_host)} -ScriptBlock {{ {inner_script} }}"
            )
        return [runner, "-NoProfile", "-NonInteractive", "-Command", outer_script]

    def _build_local_profile_command(
        self,
        techniques: List[str],
        profile: Dict[str, Any],
        *,
        show_details_brief: bool = False,
        skip_prereqs: bool = False,
    ) -> List[str]:
        runner = self._resolve_runner(str(profile.get("runner") or self.runner or "")) or self.runner or "pwsh"
        module_path = str(profile.get("module_path") or self.module_path or "Invoke-AtomicRedTeam").strip()
        atomic_root = str(profile.get("atomic_root") or self.atomic_root.as_posix()).strip()
        script = self._build_invoke_script(
            techniques,
            atomic_root=atomic_root,
            host_atomic_root=atomic_root,
            module_path=module_path,
            show_details_brief=show_details_brief,
            skip_prereqs=skip_prereqs,
        )
        return [runner, "-NoProfile", "-Command", script]

    def _build_profile_command(
        self,
        techniques: List[str],
        run_id: str,
        profile: Dict[str, Any],
        *,
        show_details_brief: bool = False,
        skip_prereqs: bool = False,
    ) -> Tuple[List[str], str]:
        profile_type = str(profile.get("type") or "local").strip().lower()
        if profile_type == "docker":
            command = self._build_sandbox_command(
                techniques,
                run_id,
                profile,
                show_details_brief=show_details_brief,
                skip_prereqs=skip_prereqs,
            )
            if not command:
                raise ValueError("docker runner profile is missing sandbox_image")
            return command, "sandbox"
        if profile_type == "ssh":
            return (
                self._build_ssh_command(
                    techniques,
                    profile,
                    show_details_brief=show_details_brief,
                    skip_prereqs=skip_prereqs,
                ),
                "remote_ssh",
            )
        if profile_type == "winrm":
            return (
                self._build_winrm_command(
                    techniques,
                    profile,
                    show_details_brief=show_details_brief,
                    skip_prereqs=skip_prereqs,
                ),
                "remote_winrm",
            )
        return (
            self._build_local_profile_command(
                techniques,
                profile,
                show_details_brief=show_details_brief,
                skip_prereqs=skip_prereqs,
            ),
            "direct",
        )

    def _execute_winrm_profile(self, techniques: List[str], profile: Dict[str, Any]) -> Tuple[int, str, str]:
        if winrm is None:
            raise RuntimeError("pywinrm is not installed for WinRM execution")
        remote_host = str(profile.get("remote_host") or "").strip()
        remote_user = str(profile.get("remote_user") or "").strip()
        remote_port = int(profile.get("remote_port") or 5985)
        password_env = str(profile.get("password_env") or "").strip()
        password = os.environ.get(password_env, "") if password_env else ""
        if not remote_host:
            raise RuntimeError("winrm runner profile missing remote_host")
        if not remote_user:
            raise RuntimeError("winrm runner profile missing remote_user")
        if not password:
            raise RuntimeError(f"winrm runner profile missing password in env var {password_env or '<unset>'}")

        module_path = str(profile.get("module_path") or self.module_path or "Invoke-AtomicRedTeam").strip()
        atomic_root = str(profile.get("atomic_root") or self.atomic_root.as_posix()).strip()
        host_atomic_root = self._host_atomic_root_for_profile(profile)
        script = self._build_invoke_script(
            techniques,
            atomic_root=atomic_root,
            host_atomic_root=host_atomic_root,
            module_path=module_path,
            show_details_brief=False,
        )

        transport = str(profile.get("winrm_transport") or profile.get("winrm_auth_method") or "auto").strip().lower()
        if transport == "negotiate":
            transport = "auto"
        if transport not in {"auto", "basic", "certificate", "ntlm", "kerberos", "credssp", "plaintext", "ssl"}:
            transport = "auto"

        transport_candidates = [transport]
        if transport == "auto":
            transport_candidates = ["basic", "ntlm", "kerberos"]
        elif transport == "basic":
            transport_candidates = ["basic", "ntlm", "kerberos"]
        elif transport == "ntlm":
            transport_candidates = ["ntlm", "kerberos", "basic"]
        elif transport == "kerberos":
            transport_candidates = ["kerberos", "ntlm", "basic"]

        if "kerberos" in transport_candidates:
            try:
                import kerberos  # type: ignore
            except Exception:
                try:
                    import requests_kerberos  # type: ignore
                except Exception:
                    transport_candidates = [t for t in transport_candidates if t != "kerberos"]

        server_cert_validation = str(profile.get("winrm_server_cert_validation") or "ignore").strip().lower()
        last_exc = None
        from winrm.exceptions import InvalidCredentialsError, WinRMError

        for candidate in transport_candidates:
            try:
                session = winrm.Session(
                    f"http://{remote_host}:{remote_port}/wsman",
                    auth=(remote_user, password),
                    transport=candidate,
                    server_cert_validation=server_cert_validation,
                )
                response = session.run_ps(script)
                stdout = response.std_out.decode(errors="ignore")
                stderr = response.std_err.decode(errors="ignore")
                return int(response.status_code), stdout, stderr
            except (InvalidCredentialsError, WinRMError) as exc:
                last_exc = exc
                continue

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("WinRM execution failed for remote host")

    def _sandbox_available(self) -> bool:
        """True if sandbox image is configured and docker CLI is reachable."""
        if not self.sandbox_image:
            return False
        docker_bin = shutil.which("docker")
        return docker_bin is not None

    def _extract_techniques_from_output(self, *chunks: str) -> List[str]:
        pattern = re.compile(r"\bT\d{4}(?:\.\d{3})?\b", re.IGNORECASE)
        found = set()
        for chunk in chunks:
            text = str(chunk or "")
            for match in pattern.finditer(text):
                found.add(match.group(0).upper())
        return sorted(found)

    @staticmethod
    def _looks_like_real_atomic_execution(exit_code: int, stdout: str, command: Any) -> bool:
        command_repr = str(command or "")
        stdout_text = str(stdout or "")
        if exit_code != 0:
            return False
        if "Executing test:" not in stdout_text:
            return False
        if "ShowDetailsBrief" in command_repr:
            return False
        # Must have at least one test block that actually succeeded
        try:
            from evidence_bundle import stdout_has_real_success
            return stdout_has_real_success(stdout_text)
        except ImportError:
            try:
                from backend.evidence_bundle import stdout_has_real_success
                return stdout_has_real_success(stdout_text)
            except ImportError:
                return True  # fallback if evidence_bundle not importable

    @staticmethod
    def _summarize_failure(exit_code: int, stdout: str, stderr: str) -> str:
        """Create a compact but actionable failure message for UI toasts."""
        detail = (stderr or stdout or "").strip().replace("\n", " ")
        detail = re.sub(r"\s+", " ", detail)
        if detail:
            detail = detail[:180]
            return f"Atomic execution returned non-zero (exit={exit_code}): {detail}"
        return f"Atomic execution returned non-zero (exit={exit_code})"

    def get_status(self) -> Dict:
        resolved_runner = self._resolve_runner()
        atomic_root = self._resolve_atomic_root()
        return {
            "enabled": self.enabled,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "atomic_root": str(atomic_root),
            "atomic_root_exists": atomic_root.exists(),
            "atomic_powershell_config": str(self.atomic_powershell_config),
            "atomic_powershell_config_exists": self.atomic_powershell_config.exists(),
            "runner": self.runner,
            "resolved_runner": resolved_runner,
            "runner_available": bool(resolved_runner),
            "results_dir": str(self.results_dir),
            "jobs_configured": len(self.jobs),
            "jobs_source": self.jobs_source,
            "sandbox_image": self.sandbox_image or None,
            "sandbox_available": self._sandbox_available(),
            "sandbox_atomic_host_path": self.sandbox_atomic_host_path or None,
            "sandbox_invoke_host_path": self.sandbox_invoke_host_path or None,
            "sandbox_validation_volume": self.sandbox_validation_volume or None,
            "default_runner_profile": self.default_runner_profile or None,
            "runner_profiles": self._all_runner_profiles(),
        }

    def list_jobs(self) -> Dict:
        return {
            "count": len(self.jobs),
            "jobs": self.jobs,
        }

    def _run_result_path(self, run_id: str) -> Path:
        return self.results_dir / f"run_{run_id}.json"

    def _persist_run(self, payload: Dict) -> None:
        run_id = payload.get("run_id", uuid.uuid4().hex)
        path = self._run_result_path(run_id)
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        except (OSError, IOError) as exc:
            if getattr(exc, "errno", None) in {13, 30}:
                fallback_dir = ensure_data_dir("atomic-validation")
                fallback_dir.mkdir(parents=True, exist_ok=True)
                self.results_dir = fallback_dir
                path = self._run_result_path(run_id)
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, indent=2)
                payload["result_dir_fallback"] = str(fallback_dir)
            else:
                raise

    def list_runs(self, limit: int = 50) -> Dict:
        # Collect run files from primary results dir plus any extra dirs configured
        all_dirs = [self.results_dir]
        extra_dirs_env = os.environ.get("ATOMIC_EXTRA_RUN_DIRS", "").strip()
        if extra_dirs_env:
            for d in extra_dirs_env.split(":"):
                p = Path(d)
                if p.is_dir():
                    all_dirs.append(p)

        all_files: List[Path] = []
        for d in all_dirs:
            all_files.extend(d.glob("run_*.json"))
        files = sorted(all_files, key=lambda p: p.stat().st_mtime, reverse=True)

        # Always compute full summary stats across all runs (not capped by limit)
        validated_techniques: set = set()
        successful_runs = 0
        total_count = 0
        rows: List[Dict] = []
        for path in files:
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    row = json.load(handle)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            total_count += 1
            if row.get("status") == "success":
                successful_runs += 1
                for t in row.get("techniques_executed", []) or row.get("techniques", []):
                    validated_techniques.add(t)
            if len(rows) < limit:
                rows.append(row)

        return {
            "count": total_count,
            "runs": rows,
            "summary": {
                "successful_runs": successful_runs,
                "validated_techniques": sorted(validated_techniques),
                "validated_technique_count": len(validated_techniques),
            },
        }

    def run_job(self, job_id: str, dry_run: bool = False) -> Dict:
        job = next((j for j in self.jobs if j["job_id"] == job_id), None)
        if not job:
            self._emit_atomic_event("atomic_validation_job_failed", [job_id], {"reason": "unknown_job"})
            return {
                "ok": False,
                "message": f"Unknown job_id: {job_id}",
            }

        run_id = uuid.uuid4().hex
        started_at = datetime.now(timezone.utc).isoformat()

        if not self.enabled:
            payload = {
                "run_id": run_id,
                "job_id": job_id,
                "job_name": job["name"],
                "status": "skipped",
                "message": "Atomic validation is disabled by configuration",
                "techniques": job.get("techniques", []),
                "techniques_executed": job.get("techniques", []),
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "dry_run": dry_run,
            }
            self._persist_run(payload)
            self._emit_atomic_event("atomic_validation_job_skipped", [job_id, run_id], {"reason": "disabled"})
            return {"ok": True, **payload}

        selected_profile = self._resolve_runner_profile(str(job.get("runner_profile") or ""))
        effective_atomic_root = self._host_atomic_root_for_profile(selected_profile)
        runnable_techniques = self._filter_runnable_techniques(job.get("techniques", []), effective_atomic_root)
        try:
            effective_command, execution_mode = self._build_profile_command(
                job.get("techniques", []),
                run_id,
                selected_profile,
                show_details_brief=bool(job.get("show_details_brief", False)),
                skip_prereqs=bool(job.get("skip_prereqs", False)),
            )
            command = effective_command
        except ValueError as exc:
            message = str(exc)
            status = "skipped" if message.lower().startswith("atomic validation skipped:") else "failed"
            payload = {
                "run_id": run_id,
                "job_id": job_id,
                "job_name": job["name"],
                "status": status,
                "message": message if message.lower().startswith("atomic validation") else f"Atomic validation failed: {message}",
                "techniques": runnable_techniques,
                "techniques_executed": [],
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "dry_run": dry_run,
                "runner_profile": selected_profile.get("profile_id") if selected_profile else None,
            }
            self._persist_run(payload)
            return {"ok": False, **payload}

        if dry_run:
            payload = {
                "run_id": run_id,
                "job_id": job_id,
                "job_name": job["name"],
                "status": "dry_run",
                "message": "Dry run only. Command not executed.",
                "techniques": runnable_techniques,
                "techniques_executed": runnable_techniques,
                "command": command,
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "dry_run": True,
                "runner_profile": selected_profile.get("profile_id") if selected_profile else None,
                "execution_mode": execution_mode,
            }
            self._persist_run(payload)
            self._emit_atomic_event("atomic_validation_job_dry_run", [job_id, run_id], {"techniques": runnable_techniques})
            return {"ok": True, **payload}

        profile_type = str(selected_profile.get("type") or "local").strip().lower() if selected_profile else "local"
        if profile_type == "local" and not self._resolve_runner(str(selected_profile.get("runner") or self.runner or "")):
            payload = {
                "run_id": run_id,
                "job_id": job_id,
                "job_name": job["name"],
                "status": "skipped",
                "message": (
                    f"Atomic validation skipped: no PowerShell runner available "
                    f"(configured='{selected_profile.get('runner') or self.runner}'). Install PowerShell or set ATOMIC_RUNNER."
                ),
                "techniques": runnable_techniques,
                "techniques_executed": [],
                "command": command,
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "dry_run": False,
                "runner_profile": selected_profile.get("profile_id") if selected_profile else None,
                "execution_mode": execution_mode,
            }
            self._persist_run(payload)
            self._emit_atomic_event("atomic_validation_job_skipped", [job_id, run_id], {"reason": "runner_unavailable"})
            return {"ok": True, **payload}

        if profile_type == "local" and not self._atomic_available():
            payload = {
                "run_id": run_id,
                "job_id": job_id,
                "job_name": job["name"],
                "status": "failed",
                "message": f"Atomic Red Team folder not found: {self.atomic_root}",
                "techniques": runnable_techniques,
                "techniques_executed": runnable_techniques,
                "command": command,
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "dry_run": False,
                "runner_profile": selected_profile.get("profile_id") if selected_profile else None,
                "execution_mode": execution_mode,
            }
            self._persist_run(payload)
            self._emit_atomic_event("atomic_validation_job_failed", [job_id, run_id], {"reason": "atomic_root_missing"})
            return {"ok": False, **payload}

        try:
            if profile_type == "winrm" and winrm is not None:
                exit_code, stdout_text, stderr_text = self._execute_winrm_profile(job.get("techniques", []), selected_profile)
            else:
                proc = subprocess.run(effective_command, capture_output=True, text=True, timeout=1200, check=False)
                exit_code = proc.returncode
                stdout_text = proc.stdout or ""
                stderr_text = proc.stderr or ""

            status = "success" if exit_code == 0 else "failed"
            detected_techniques = self._extract_techniques_from_output(stdout_text, stderr_text)
            techniques_executed = sorted(set(runnable_techniques + detected_techniques))
            real_execution = self._looks_like_real_atomic_execution(exit_code, stdout_text, effective_command)
            if exit_code == 0 and not real_execution:
                status = "failed"
            # Check for partial execution (some tests succeeded, some failed)
            if status == "success" and real_execution:
                try:
                    from evidence_bundle import count_test_outcomes
                    ok, fail = count_test_outcomes(stdout_text)
                    if ok > 0 and fail > 0:
                        status = "partial"
                    elif ok == 0 and fail > 0:
                        status = "failed"
                        real_execution = False
                except ImportError:
                    pass
            payload = {
                "run_id": run_id,
                "job_id": job_id,
                "job_name": job["name"],
                "status": status,
                "message": (
                    "Completed"
                    if exit_code == 0 and real_execution
                    else "Atomic command exited 0 but no test execution markers were observed"
                    if exit_code == 0
                    else self._summarize_failure(exit_code, stdout_text, stderr_text)
                ),
                "techniques": runnable_techniques,
                "detected_techniques": detected_techniques,
                "techniques_executed": techniques_executed,
                "command": effective_command,
                "exit_code": exit_code,
                "stdout": stdout_text[-12000:],
                "stderr": stderr_text[-12000:],
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "dry_run": False,
                "execution_mode": execution_mode,
                "runner_profile": selected_profile.get("profile_id") if selected_profile else None,
                "real_execution": real_execution,
                "sandbox": "docker-network-none-cap-drop-all" if execution_mode == "sandbox" else None,
            }
            self._persist_run(payload)
            self._emit_atomic_event(
                "atomic_validation_job_completed",
                [job_id, run_id],
                {
                    "status": status,
                    "exit_code": exit_code,
                    "techniques": runnable_techniques,
                    "techniques_executed": techniques_executed,
                    "execution_mode": execution_mode,
                },
            )
            if exit_code == 0 and real_execution:
                self._trigger_soar_for_techniques(techniques_executed, job_id, run_id)
            return {"ok": exit_code == 0 and real_execution, **payload}
        except subprocess.TimeoutExpired as exc:
            detected_techniques = self._extract_techniques_from_output(exc.stdout, exc.stderr)
            techniques_executed = sorted(set(runnable_techniques + detected_techniques))
            payload = {
                "run_id": run_id,
                "job_id": job_id,
                "job_name": job["name"],
                "status": "failed",
                "message": "Atomic validation run timed out",
                "techniques": runnable_techniques,
                "detected_techniques": detected_techniques,
                "techniques_executed": techniques_executed,
                "command": effective_command,
                "stdout": (exc.stdout or "")[-12000:] if isinstance(exc.stdout, str) else "",
                "stderr": (exc.stderr or "")[-12000:] if isinstance(exc.stderr, str) else "",
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "dry_run": False,
                "execution_mode": execution_mode,
                "runner_profile": selected_profile.get("profile_id") if selected_profile else None,
            }
            self._persist_run(payload)
            self._emit_atomic_event("atomic_validation_job_failed", [job_id, run_id], {"reason": "timeout"})
            return {"ok": False, **payload}


atomic_validation = AtomicValidationManager()
