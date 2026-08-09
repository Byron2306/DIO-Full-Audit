#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import random
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List
from urllib import error, request


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "evidence" / "sovereign_stack" / "THE_LAST_CHORD_PROTOCOL" / "armageddon"
RUNS_DIR = ROOT / "evidence" / "sovereign_stack" / "THE_LAST_CHORD_PROTOCOL" / "runs"
LAST_CHORD_PROTOCOL_PATH = ROOT / "scripts" / "run_last_chord_protocol.py"
AGENT_PROFILES_PATH = ROOT / "tests" / "adversarial" / "agent_profiles.py"
DEFAULT_GROUP_ID = "last_chord_armageddon_001"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

API_KEY_ENV_BY_PROVIDER = {
    "gemini": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "grok": "GROK_API_KEY",
}

DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash",
    "anthropic": "claude-sonnet-4-5-20250929",
    "grok": "grok-3-mini",
}


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    model: str
    api_key_env: str


@dataclass(frozen=True)
class RunPlan:
    wave_index: int
    slot_index: int
    provider: str
    model: str
    agent_class: str
    aatr_id: str | None
    attempted_action: str
    scenario_id: str | None
    mutation: str
    steps: int
    run_id: str


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_last_chord_module():
    return _load_module(LAST_CHORD_PROTOCOL_PATH, "run_last_chord_protocol")


def _load_live_aab_module():
    return _load_module(ROOT / "run_live_aab.py", "run_live_aab")


AgentClass = _load_module(AGENT_PROFILES_PATH, "agent_profiles").AgentClass


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _slug(value: str) -> str:
    return value.replace("_", "-")


def _json_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _merkle_root(leaf_hashes: List[str]) -> str | None:
    if not leaf_hashes:
        return None
    level = list(leaf_hashes)
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [
            hashlib.sha256(f"{left}{right}".encode("utf-8")).hexdigest()
            for left, right in zip(level[0::2], level[1::2])
        ]
    return level[0]


def _extract_trailing_json(stdout: str) -> Dict[str, Any] | None:
    stripped = stdout.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    end = stripped.rfind("}")
    start = stripped.rfind("{", 0, end + 1)
    while start != -1 and end != -1 and start < end:
        candidate = stripped[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            start = stripped.rfind("{", 0, start)
    return {"raw_stdout": stripped}


def _default_providers() -> List[ProviderConfig]:
    return [
        ProviderConfig(name=name, model=DEFAULT_MODELS[name], api_key_env=API_KEY_ENV_BY_PROVIDER[name])
        for name in ("gemini", "anthropic", "grok")
    ]


def _build_jitter_plan(
    *,
    group_id: str,
    mutation: str,
    waves: List[List[RunPlan]],
    jitter_ms_min: int,
    jitter_ms_max: int,
) -> Dict[str, Any]:
    seed_material = f"{group_id}:{mutation}:{len(waves)}:{jitter_ms_min}:{jitter_ms_max}"
    seed = int(hashlib.sha256(seed_material.encode("utf-8")).hexdigest()[:16], 16)
    rng = random.Random(seed)
    wave_entries: List[Dict[str, Any]] = []
    for wave in waves:
        scheduled_offset_ms = 0
        run_entries: List[Dict[str, Any]] = []
        for run in wave:
            launch_jitter_ms = 0 if jitter_ms_max <= 0 else rng.randint(jitter_ms_min, jitter_ms_max)
            scheduled_offset_ms += launch_jitter_ms
            run_entries.append({
                "run_id": run.run_id,
                "launch_jitter_ms": launch_jitter_ms,
                "scheduled_offset_ms": scheduled_offset_ms,
            })
        wave_entries.append({
            "wave_index": wave[0].wave_index,
            "runs": run_entries,
        })
    return {
        "mode": "random_jitter",
        "seed": seed,
        "jitter_ms_min": jitter_ms_min,
        "jitter_ms_max": jitter_ms_max,
        "waves": wave_entries,
    }


class NetworkCaptureSession:
    def __init__(
        self,
        *,
        group_id: str,
        port: int,
        requested_backend: str,
        capture_interface: str,
        capture_with_sudo: bool,
        capture_packet_limit: int | None = None,
        capture_wait_seconds: float | None = None,
    ) -> None:
        self._group_id = group_id
        self._port = port
        self._requested_backend = requested_backend
        self._capture_interface = capture_interface
        self._capture_with_sudo = capture_with_sudo
        self._capture_filter = f"tcp port {port}"
        self._pcap_proc: subprocess.Popen[str] | None = None
        self._capture_dir = OUTPUT_DIR / f"{group_id}_network_capture"
        self._pcap_path = self._capture_dir / f"{group_id}.pcap"
        self._zeek_dir = self._capture_dir / "zeek"
        self._zeek_image = os.environ.get("ARMAGEDDON_ZEEK_IMAGE", "blacktop/zeek:latest")
        self._sudo_askpass_path: Path | None = None
        self._capture_pid: int | None = None
        self._capture_packet_limit = max(
            1,
            capture_packet_limit if capture_packet_limit is not None else int(os.environ.get("ARMAGEDDON_CAPTURE_PACKET_LIMIT", "32")),
        )
        self._capture_wait_seconds = max(
            1.0,
            capture_wait_seconds if capture_wait_seconds is not None else float(os.environ.get("ARMAGEDDON_CAPTURE_WAIT_SECONDS", "10")),
        )

    def _sudo_wrapped_cmd(self, base_cmd: List[str]) -> tuple[List[str], Dict[str, str]]:
        env = os.environ.copy()
        if not self._capture_with_sudo:
            return base_cmd, env
        if self._sudo_askpass_path:
            env["SUDO_ASKPASS"] = str(self._sudo_askpass_path)
            return ["sudo", "-A", *base_cmd], env
        return ["sudo", "-n", *base_cmd], env

    def _terminate_capture_fallback(self, sigspec: str) -> None:
        cmd, env = self._sudo_wrapped_cmd(["pkill", sigspec, "-f", str(self._pcap_path)])
        subprocess.run(
            cmd,
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )

    def _resolve_capture_pid(self) -> int | None:
        proc = subprocess.run(
            ["pgrep", "-f", str(self._pcap_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return None
        for line in reversed(proc.stdout.splitlines()):
            line = line.strip()
            if line.isdigit():
                return int(line)
        return None

    def _signal_capture_pid(self, sigspec: str) -> None:
        capture_pid = self._capture_pid or self._resolve_capture_pid()
        if capture_pid is None:
            return
        self._capture_pid = capture_pid
        cmd, env = self._sudo_wrapped_cmd(["kill", sigspec, str(capture_pid)])
        subprocess.run(
            cmd,
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )

    def _capture_pid_running(self) -> bool:
        capture_pid = self._capture_pid or self._resolve_capture_pid()
        if capture_pid is None:
            return False
        self._capture_pid = capture_pid
        try:
            os.kill(capture_pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def _wait_for_capture_exit(self, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if not self._capture_pid_running():
                return True
            time.sleep(0.1)
        return not self._capture_pid_running()

    def _host_zeek_available(self) -> bool:
        return shutil.which("zeek") is not None

    def _docker_zeek_available(self) -> bool:
        proc = subprocess.run(
            ["docker", "image", "inspect", self._zeek_image],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return proc.returncode == 0

    def _zeek_backend(self) -> str | None:
        if self._host_zeek_available():
            return "host"
        if self._docker_zeek_available():
            return "docker"
        return None

    def manifest_stub(self) -> Dict[str, Any]:
        zeek_backend = self._zeek_backend()
        return {
            "requested_backend": self._requested_backend,
            "capture_interface": self._capture_interface,
            "capture_filter": self._capture_filter,
            "pcap": {
                "planned_path": str(self._pcap_path.relative_to(ROOT)),
                "capture_tool": "tcpdump" if shutil.which("tcpdump") else None,
                "privilege_mode": "sudo" if self._capture_with_sudo else "user",
                "pcap_backed": True,
                "packet_limit": self._capture_packet_limit,
                "wait_seconds": self._capture_wait_seconds,
            },
            "zeek": {
                "requested": self._requested_backend == "zeek",
                "available": zeek_backend is not None,
                "backend": zeek_backend,
                "docker_image": self._zeek_image if zeek_backend == "docker" else None,
                "planned_log_dir": str(self._zeek_dir.relative_to(ROOT)),
            },
        }

    def start(self) -> None:
        self._capture_dir.mkdir(parents=True, exist_ok=True)
        if not shutil.which("tcpdump"):
            return
        cmd = [
            "tcpdump",
            "-i",
            self._capture_interface,
            "-U",
            "-n",
            "-c",
            str(self._capture_packet_limit),
            "-w",
            str(self._pcap_path),
            self._capture_filter,
        ]
        if self._capture_with_sudo:
            sudo_password = os.environ.get("ARMAGEDDON_SUDO_PASSWORD")
            if sudo_password:
                askpass_file = tempfile.NamedTemporaryFile(
                    mode="w",
                    prefix="armageddon-askpass-",
                    suffix=".sh",
                    dir=self._capture_dir,
                    delete=False,
                )
                askpass_file.write("#!/bin/sh\nprintf '%s\\n' \"$ARMAGEDDON_SUDO_PASSWORD\"\n")
                askpass_file.close()
                os.chmod(askpass_file.name, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
                self._sudo_askpass_path = Path(askpass_file.name)
        cmd, env = self._sudo_wrapped_cmd(cmd)
        self._pcap_proc = subprocess.Popen(
            cmd,
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setpgrp,
        )
        time.sleep(0.2)
        self._capture_pid = self._resolve_capture_pid()

    def _drain_capture_stderr(self) -> str:
        if self._pcap_proc is None or self._pcap_proc.stderr is None:
            return ""
        try:
            return self._pcap_proc.stderr.read().strip()
        except Exception:
            return ""

    def stop(self) -> Dict[str, Any]:
        metadata = self.manifest_stub()
        pcap_stderr = ""
        pcap_returncode = None
        try:
            if self._pcap_proc is not None:
                self._capture_pid = self._capture_pid or self._resolve_capture_pid()
                try:
                    self._pcap_proc.wait(timeout=self._capture_wait_seconds)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(self._pcap_proc.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    self._signal_capture_pid("-TERM")
                    self._terminate_capture_fallback("-TERM")
                    try:
                        os.killpg(self._pcap_proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    self._signal_capture_pid("-KILL")
                    self._terminate_capture_fallback("-KILL")
                    try:
                        self._pcap_proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        pcap_stderr = "capture teardown timed out"
                if not self._wait_for_capture_exit(timeout_seconds=5):
                    pcap_stderr = "\n".join(filter(None, [pcap_stderr, "capture child still running after teardown"]))
                pcap_stderr = "\n".join(filter(None, [pcap_stderr, self._drain_capture_stderr()]))
                pcap_returncode = self._pcap_proc.returncode
            pcap_exists = self._pcap_path.exists()
            pcap_status = "captured" if pcap_exists else "not_started"
            if not pcap_exists and pcap_stderr:
                if "Operation not permitted" in pcap_stderr:
                    pcap_status = "permission_denied"
                elif "a password is required" in pcap_stderr:
                    pcap_status = "sudo_password_required"
                else:
                    pcap_status = "capture_failed"
            metadata["pcap"].update({
                "status": pcap_status,
                "captured": pcap_exists,
                "path": str(self._pcap_path.relative_to(ROOT)) if pcap_exists else None,
                "sha256": _sha256_file(self._pcap_path),
                "size_bytes": self._pcap_path.stat().st_size if pcap_exists else 0,
                "returncode": pcap_returncode,
                "stdout": "",
                "stderr": pcap_stderr.strip(),
            })
            metadata["zeek"].update(self._run_zeek_analysis())
        finally:
            if self._sudo_askpass_path and self._sudo_askpass_path.exists():
                self._sudo_askpass_path.unlink()
        return metadata

    def _run_zeek_analysis(self) -> Dict[str, Any]:
        requested = self._requested_backend == "zeek"
        backend = self._zeek_backend()
        if not requested:
            return {"status": "disabled", "logs": []}
        if backend is None:
            return {"status": "not_installed", "logs": []}
        if not self._pcap_path.exists():
            return {"status": "pcap_missing", "logs": []}
        self._zeek_dir.mkdir(parents=True, exist_ok=True)
        if backend == "host":
            proc = subprocess.run(
                ["zeek", "-Cr", str(self._pcap_path)],
                cwd=self._zeek_dir,
                capture_output=True,
                text=True,
            )
        else:
            proc = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{self._capture_dir}:/capture",
                    "-w",
                    "/capture/zeek",
                    self._zeek_image,
                    "-Cr",
                    f"/capture/{self._pcap_path.name}",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
        logs = []
        for log_path in sorted(self._zeek_dir.glob("*.log")):
            logs.append({
                "path": str(log_path.relative_to(ROOT)),
                "sha256": _sha256_file(log_path),
                "size_bytes": log_path.stat().st_size,
            })
        return {
            "status": "completed" if proc.returncode == 0 else "failed",
            "backend": backend,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "logs": logs,
        }


def _compute_shared_state_proof(*, manifest: Dict[str, Any], execution: Dict[str, Any]) -> Dict[str, Any]:
    wave_proofs: List[Dict[str, Any]] = []
    all_leaf_hashes: List[str] = []
    for wave in execution["waves"]:
        leaves = []
        for run in wave["runs"]:
            summary = run.get("stdout") or {}
            artifact_rel = summary.get("last_chord_record")
            source_rel = summary.get("source_aab_record")
            artifact_hash = _sha256_file(ROOT / artifact_rel) if artifact_rel else None
            source_hash = _sha256_file(ROOT / source_rel) if source_rel else None
            if artifact_hash:
                all_leaf_hashes.append(artifact_hash)
            leaves.append({
                "run_id": run["plan"]["run_id"],
                "last_chord_record": artifact_rel,
                "last_chord_record_sha256": artifact_hash,
                "source_aab_record": source_rel,
                "source_aab_sha256": source_hash,
            })
        wave_root = _merkle_root([leaf["last_chord_record_sha256"] for leaf in leaves if leaf["last_chord_record_sha256"]])
        wave_proofs.append({
            "wave_index": wave["wave_index"],
            "leaf_count": len(leaves),
            "merkle_root": wave_root,
            "leaves": leaves,
        })
    shared_policy_hash = _json_sha256({
        "shared_live_url": manifest["shared_live_url"],
        "providers": manifest["providers"],
        "noise_profile": manifest["noise_profile"],
        "timing_profile": manifest["timing_profile"],
        "network_capture": manifest["network_capture"],
    })
    shared_world_state_hash = _json_sha256({
        "live_url": execution["live_url"],
        "waves": [
            {
                "wave_index": wave["wave_index"],
                "barrier_release_id": wave["barrier_release_id"],
                "run_ids": [run["plan"]["run_id"] for run in wave["runs"]],
                "returncodes": [run["returncode"] for run in wave["runs"]],
                "noise_event_count": sum(len(cycle.get("events", [])) for cycle in wave.get("noise_events", [])),
            }
            for wave in execution["waves"]
        ],
    })
    return {
        "algorithm": "sha256_merkle",
        "group_merkle_root": _merkle_root(all_leaf_hashes),
        "wave_merkle_roots": wave_proofs,
        "shared_policy_hash": shared_policy_hash,
        "shared_world_state_hash": shared_world_state_hash,
    }


def _select_agent_classes(selection: str) -> List[str]:
    if selection == "all":
        return [agent.value for agent in AgentClass]
    names = [name.strip() for name in selection.split(",") if name.strip()]
    valid = {agent.value for agent in AgentClass}
    unknown = sorted(set(names) - valid)
    if unknown:
        raise ValueError(f"Unknown agent classes: {', '.join(unknown)}")
    return names


def build_wave_plan(
    *,
    group_id: str,
    agent_classes: List[str],
    providers: List[ProviderConfig],
    wave_size: int,
    mutation: str,
    steps: int,
) -> List[List[RunPlan]]:
    if wave_size < 1:
        raise ValueError("wave_size must be >= 1")
    lc_module = _load_last_chord_module()
    live_aab = _load_live_aab_module()
    waves: List[List[RunPlan]] = []
    current_wave: List[RunPlan] = []
    for index, agent_class in enumerate(agent_classes):
        provider = providers[index % len(providers)]
        scenario = lc_module._scenario_metadata(agent_class, "EXEC_ISOLATE_HOST")
        attempted_action = scenario.get("attempted_action") or "EXEC_ISOLATE_HOST"
        scenario = lc_module._scenario_metadata(agent_class, attempted_action)
        wave_index = (index // wave_size) + 1
        slot_index = (index % wave_size) + 1
        run_id = f"{group_id}_w{wave_index:02d}_{provider.name}_{_slug(agent_class)}"
        plan = RunPlan(
            wave_index=wave_index,
            slot_index=slot_index,
            provider=provider.name,
            model=provider.model,
            agent_class=agent_class,
            aatr_id=live_aab._AATR_MAP.get(agent_class),
            attempted_action=attempted_action,
            scenario_id=scenario.get("scenario_id"),
            mutation=mutation,
            steps=steps,
            run_id=run_id,
        )
        if not current_wave or current_wave[0].wave_index == wave_index:
            current_wave.append(plan)
        else:
            waves.append(current_wave)
            current_wave = [plan]
    if current_wave:
        waves.append(current_wave)
    return waves


def _post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _wait_for_server(base_url: str, *, timeout_s: float = 30.0, poll_interval_s: float = 0.25) -> None:
    deadline = time.monotonic() + timeout_s
    url = f"{base_url.rstrip('/')}/openapi.json"
    while time.monotonic() < deadline:
        try:
            with request.urlopen(url, timeout=5):
                return
        except error.URLError:
            time.sleep(poll_interval_s)
    raise TimeoutError(f"Timed out waiting for shared server readiness at {url}")


def emit_noise_burst(base_url: str, *, cycle: int, controls_per_cycle: int) -> Dict[str, Any]:
    live_aab = _load_live_aab_module()
    controls = list(live_aab._BENIGN_CONTROLS.items())[:controls_per_cycle]
    events: List[Dict[str, Any]] = []
    for control_name, spec in controls:
        for path_index, path in enumerate(spec["paths"]):
            payload = {
                "ip": f"198.51.100.{cycle + path_index + 10}",
                "path": path,
                "session_id": f"noise-{control_name}-{cycle}",
                "headers": {
                    "user-agent": spec["user_agent"],
                    "accept": "application/json",
                    "accept-language": "en-US",
                },
                "timing_data": spec["timing_data"],
                "behavior_flags": {
                    "ai_behavior": False,
                    "agenticity_score": spec["agenticity"],
                    "autonomous_confidence": spec["agenticity"],
                    "machine_plausibility": spec["agenticity"],
                    "aatr_id": "BENIGN-CONTROL",
                    "control_persona": control_name,
                },
            }
            try:
                response = _post_json(f"{base_url.rstrip('/')}/deception/assess", payload)
                events.append({
                    "control": control_name,
                    "path": path,
                    "route": response.get("route"),
                    "maze_id": response.get("maze_id"),
                })
            except error.URLError as exc:
                events.append({
                    "control": control_name,
                    "path": path,
                    "error": str(exc),
                })
    return {
        "cycle": cycle,
        "generated_at": _now_utc(),
        "events": events,
    }


class NoiseEmitter:
    def __init__(self, *, base_url: str, controls_per_cycle: int, interval_s: float) -> None:
        self._base_url = base_url
        self._controls_per_cycle = controls_per_cycle
        self._interval_s = interval_s
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.events: List[Dict[str, Any]] = []

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        cycle = 1
        while not self._stop.is_set():
            self.events.append(
                emit_noise_burst(
                    self._base_url,
                    cycle=cycle,
                    controls_per_cycle=self._controls_per_cycle,
                )
            )
            cycle += 1
            self._stop.wait(self._interval_s)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(2.0, self._interval_s * 2))


def _start_shared_server(port: int) -> subprocess.Popen[bytes]:
    cmd = [
        str(ROOT / ".venv" / "bin" / "python"),
        "-m",
        "uvicorn",
        "backend.aab_server:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_server(base_url)
    except Exception:
        proc.terminate()
        raise
    return proc


def _build_manifest_payload(
    *,
    group_id: str,
    mutation: str,
    wave_size: int,
    providers: List[ProviderConfig],
    waves: List[List[RunPlan]],
    live_url: str,
    noise_controls_per_cycle: int,
    noise_interval_s: float,
    timing_profile: Dict[str, Any],
    network_capture: Dict[str, Any],
    execute: bool,
) -> Dict[str, Any]:
    return {
        "group_id": group_id,
        "generated_at": _now_utc(),
        "mutation": mutation,
        "wave_size": wave_size,
        "execute": execute,
        "shared_live_url": live_url,
        "providers": [asdict(provider) for provider in providers],
        "noise_profile": {
            "mode": "seraph_shared_background_noise",
            "controls_per_cycle": noise_controls_per_cycle,
            "interval_s": noise_interval_s,
            "source": "run_live_aab._BENIGN_CONTROLS",
        },
        "timing_profile": timing_profile,
        "network_capture": network_capture,
        "shared_state_proof": {
            "algorithm": "sha256_merkle",
            "status": "pending_execution" if execute else "not_generated",
        },
        "waves": [
            {
                "wave_index": wave[0].wave_index,
                "run_count": len(wave),
                "runs": [asdict(run) for run in wave],
            }
            for wave in waves
        ],
    }


def _provider_env(provider: ProviderConfig) -> Dict[str, str]:
    env = os.environ.copy()
    env["AAB_LIVE_PROVIDER"] = provider.name
    env["LAST_CHORD_PROVIDER"] = provider.name
    env["AAB_LIVE_MODEL"] = provider.model
    env["LAST_CHORD_MODEL"] = provider.model
    return env


def _launch_wave_run(
    run: RunPlan,
    *,
    base_url: str,
    provider: ProviderConfig,
    timing_entry: Dict[str, Any],
) -> Dict[str, Any]:
    env = _provider_env(provider)
    cmd = [
        str(ROOT / ".venv" / "bin" / "python"),
        str(LAST_CHORD_PROTOCOL_PATH),
        "--run-id",
        run.run_id,
        "--provider",
        run.provider,
        "--agent-class",
        run.agent_class,
        "--attempted-action",
        run.attempted_action,
        "--model",
        run.model,
        "--steps",
        str(run.steps),
        "--mutation",
        run.mutation,
        "--live-url",
        base_url,
    ]
    start_monotonic_ns = time.monotonic_ns()
    start_utc = _now_utc()
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return {
        "plan": asdict(run),
        "timing": timing_entry,
        "process": proc,
        "actual_start_utc": start_utc,
        "monotonic_start_ns": start_monotonic_ns,
    }


def execute_waves(
    *,
    group_id: str,
    waves: List[List[RunPlan]],
    providers: List[ProviderConfig],
    live_url: str,
    noise_controls_per_cycle: int,
    noise_interval_s: float,
    timing_profile: Dict[str, Any],
) -> Dict[str, Any]:
    provider_lookup = {provider.name: provider for provider in providers}
    timing_lookup = {
        wave["wave_index"]: {run["run_id"]: run for run in wave["runs"]}
        for wave in timing_profile["waves"]
    }
    wave_results: List[Dict[str, Any]] = []
    for wave in waves:
        wave_index = wave[0].wave_index
        noise = NoiseEmitter(
            base_url=live_url,
            controls_per_cycle=noise_controls_per_cycle,
            interval_s=noise_interval_s,
        )
        noise.start()
        launched = []
        wave_start_ns = time.monotonic_ns()
        for run in wave:
            timing_entry = timing_lookup[wave_index][run.run_id]
            target_ns = wave_start_ns + (timing_entry["scheduled_offset_ms"] * 1_000_000)
            remaining_ns = target_ns - time.monotonic_ns()
            if remaining_ns > 0:
                time.sleep(remaining_ns / 1_000_000_000)
            launched.append(
                _launch_wave_run(
                    run,
                    base_url=live_url,
                    provider=provider_lookup[run.provider],
                    timing_entry=timing_entry,
                )
            )
        completed_runs: List[Dict[str, Any]] = []
        for launched_run in launched:
            proc = launched_run.pop("process")
            stdout, stderr = proc.communicate()
            end_monotonic_ns = time.monotonic_ns()
            end_utc = _now_utc()
            summary = _extract_trailing_json(stdout)
            completed_runs.append({
                **launched_run,
                "returncode": proc.returncode,
                "actual_end_utc": end_utc,
                "monotonic_end_ns": end_monotonic_ns,
                "stdout": summary,
                "stderr": stderr.strip(),
            })
        noise.stop()
        wave_results.append({
            "wave_index": wave_index,
            "barrier_release_id": f"{group_id}-wave-{wave_index:02d}",
            "timing_jitter": timing_profile["waves"][wave_index - 1],
            "noise_events": noise.events,
            "runs": completed_runs,
        })
    return {
        "group_id": group_id,
        "generated_at": _now_utc(),
        "live_url": live_url,
        "timing_profile": timing_profile,
        "waves": wave_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch Last Chord Armageddon waves across Gemini, Claude, and Grok with shared Seraph background noise.")
    parser.add_argument("--group-id", default=DEFAULT_GROUP_ID)
    parser.add_argument("--classes", default="all", help="Comma-separated AATR classes to run, or 'all' for all 38.")
    parser.add_argument("--wave-size", type=int, default=12)
    parser.add_argument("--mutation", default="stealth_slow")
    parser.add_argument("--steps", type=int, default=6)
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument("--noise-controls-per-cycle", type=int, default=3)
    parser.add_argument("--noise-interval-s", type=float, default=0.75)
    parser.add_argument("--jitter-ms-min", type=int, default=25)
    parser.add_argument("--jitter-ms-max", type=int, default=250)
    parser.add_argument("--capture-backend", choices=["none", "tcpdump", "zeek"], default="zeek")
    parser.add_argument("--capture-interface", default="lo")
    parser.add_argument("--capture-with-sudo", action="store_true")
    parser.add_argument("--capture-packet-limit", type=int, default=int(os.environ.get("ARMAGEDDON_CAPTURE_PACKET_LIMIT", "32")))
    parser.add_argument("--capture-wait-seconds", type=float, default=float(os.environ.get("ARMAGEDDON_CAPTURE_WAIT_SECONDS", "10")))
    parser.add_argument("--execute", action="store_true", help="Actually launch the Armageddon waves. Without this flag the script only writes a manifest.")
    args = parser.parse_args()

    providers = _default_providers()
    agent_classes = _select_agent_classes(args.classes)
    waves = build_wave_plan(
        group_id=args.group_id,
        agent_classes=agent_classes,
        providers=providers,
        wave_size=args.wave_size,
        mutation=args.mutation,
        steps=args.steps,
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    live_url = f"http://127.0.0.1:{args.port}"
    jitter_profile = _build_jitter_plan(
        group_id=args.group_id,
        mutation=args.mutation,
        waves=waves,
        jitter_ms_min=args.jitter_ms_min,
        jitter_ms_max=args.jitter_ms_max,
    )
    capture_session = NetworkCaptureSession(
        group_id=args.group_id,
        port=args.port,
        requested_backend=args.capture_backend,
        capture_interface=args.capture_interface,
        capture_with_sudo=args.capture_with_sudo,
        capture_packet_limit=args.capture_packet_limit,
        capture_wait_seconds=args.capture_wait_seconds,
    )
    manifest = _build_manifest_payload(
        group_id=args.group_id,
        mutation=args.mutation,
        wave_size=args.wave_size,
        providers=providers,
        waves=waves,
        live_url=live_url,
        noise_controls_per_cycle=args.noise_controls_per_cycle,
        noise_interval_s=args.noise_interval_s,
        timing_profile=jitter_profile,
        network_capture=capture_session.manifest_stub(),
        execute=args.execute,
    )
    manifest_path = OUTPUT_DIR / f"{args.group_id}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    if not args.execute:
        print(json.dumps({
            "group_id": args.group_id,
            "manifest": str(manifest_path.relative_to(ROOT)),
            "waves": len(waves),
            "runs": sum(len(wave) for wave in waves),
            "execute": False,
        }, indent=2))
        return

    capture_session.start()
    server = _start_shared_server(args.port)
    try:
        execution = execute_waves(
            group_id=args.group_id,
            waves=waves,
            providers=providers,
            live_url=live_url,
            noise_controls_per_cycle=args.noise_controls_per_cycle,
            noise_interval_s=args.noise_interval_s,
            timing_profile=jitter_profile,
        )
    finally:
        server.terminate()

    execution["network_capture"] = capture_session.stop()
    execution["shared_state_proof"] = _compute_shared_state_proof(manifest=manifest, execution=execution)

    execution_path = OUTPUT_DIR / f"{args.group_id}_execution.json"
    execution_path.write_text(json.dumps(execution, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "group_id": args.group_id,
        "manifest": str(manifest_path.relative_to(ROOT)),
        "execution": str(execution_path.relative_to(ROOT)),
        "waves": len(waves),
        "runs": sum(len(wave) for wave in waves),
        "execute": True,
    }, indent=2))


if __name__ == "__main__":
    main()