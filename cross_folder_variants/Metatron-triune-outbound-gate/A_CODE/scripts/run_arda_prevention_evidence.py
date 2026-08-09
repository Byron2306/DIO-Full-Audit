#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_shell(cmd: str, *, check: bool = False, capture: bool = True, timeout: int | None = None) -> subprocess.CompletedProcess:
    kwargs = {"shell": True, "text": True, "timeout": timeout}
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    proc = subprocess.run(cmd, **kwargs)
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed rc={proc.returncode}: {cmd}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def _run_exec(argv: list[str], *, timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def _safe_run(argv: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except FileNotFoundError as e:
        return subprocess.CompletedProcess(args=argv, returncode=127, stdout="", stderr=str(e))
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(args=argv, returncode=124, stdout=e.stdout or "", stderr=str(e))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    data = path.read_bytes()
    return _sha256_bytes(data)


def _tail_file(path: Path, lines: int = 200) -> list[str]:
    if not path.exists():
        return []
    try:
        result = _run_shell(f"tail -n {lines} {shlex.quote(str(path))}", check=False, capture=True, timeout=10)
        return (result.stdout or "").splitlines()
    except Exception:
        return []


def _capture_dmesg_tail(lines: int = 120) -> dict[str, object]:
    try:
        result = _run_shell("dmesg -T | tail -n 120", check=False, capture=True, timeout=15)
        all_lines = (result.stdout or "").splitlines()
    except Exception:
        all_lines = []
    lsm_keywords = ("arda", "BPF LSM", "bpf_lsm", "lsm_bprm", "seraph_lsm", "EPERM", "Operation not permitted")
    lsm_matches = [ln for ln in all_lines if any(kw.lower() in ln.lower() for kw in lsm_keywords)]
    return {"tail": all_lines, "lsm_matches": lsm_matches, "lsm_match_count": len(lsm_matches)}


def _capture_docker_inspect(container_name: str) -> dict[str, object] | None:
    result = _run_shell(f"docker inspect {shlex.quote(container_name)}", check=False, capture=True, timeout=20)
    if result.returncode != 0 or not result.stdout:
        return None
    try:
        payload = json.loads(result.stdout)
        return payload[0] if isinstance(payload, list) and payload else payload
    except Exception:
        return None


def _capture_proc_maps(pid: int) -> list[str]:
    proc_map = Path(f"/proc/{pid}/maps")
    if not proc_map.exists():
        return []
    try:
        return proc_map.read_text(encoding="utf-8", errors="replace").splitlines()
    except PermissionError:
        return ["permission denied reading /proc/{pid}/maps"]
    except Exception:
        return []


def _parse_bpftool_enforcement_mode(dump_lines: list[str]) -> dict[str, object]:
    """
    Parse bpftool map dump output to derive enforcement mode.
    ARDA_STATE_KEY_ENFORCE = key 0; value 1 = enforcing, value 0 = audit/off.
    Supports three bpftool output formats:
      - JSON integer:  [{"key": 0, "value": 0}]           (bpftool >= 7 default)
      - JSON hex-arr:  [{"key": ["0x00"], "value": [...]}] (older bpftool)
      - text:          key: 00 00 00 00  value: 00 00 00 00
    NOTE: The map is read after the enforcement pulse ends so value=0 is the
    expected post-test state. Active enforcement during the test is proven by
    deny_count_delta > 0 in the enforcement section.
    """
    raw = "\n".join(dump_lines)
    enforcing = False
    parsed = False

    # Format 1: JSON integer — [{"key": 0, "value": 1}]
    try:
        records = json.loads(raw)
        if isinstance(records, list):
            for rec in records:
                if not isinstance(rec, dict):
                    continue
                k = rec.get("key")
                v = rec.get("value")
                if k == 0:
                    enforcing = bool(v == 1)
                    parsed = True
                    break
    except Exception:
        pass

    # Format 2: JSON hex-array — [{"key": ["0x00"], "value": ["0x01"]}]
    if not parsed:
        try:
            key0_value1 = re.search(r'"key"\s*:\s*\[\s*"0x00"\s*\].*?"value"\s*:\s*\[\s*"0x01"\s*\]', raw, re.DOTALL)
            key0_value0 = re.search(r'"key"\s*:\s*\[\s*"0x00"\s*\].*?"value"\s*:\s*\[\s*"0x00"\s*\]', raw, re.DOTALL)
            if key0_value1:
                enforcing = True
                parsed = True
            elif key0_value0:
                enforcing = False
                parsed = True
        except Exception:
            pass

    # Format 3: text — "key: 00 00 00 00  value: 01 00 00 00"
    if not parsed:
        for line in dump_lines:
            lo = line.lower()
            if "key" in lo and "value" in lo:
                m = re.search(r'key:\s*([\w ]+?)\s+value:\s*([\w ]+)', lo)
                if m:
                    k_bytes = m.group(1).split()
                    v_bytes = m.group(2).split()
                    if k_bytes and int(k_bytes[0], 16) == 0:
                        parsed = True
                        enforcing = bool(v_bytes and int(v_bytes[0], 16) == 1)
                    break

    return {
        "enforcing": enforcing,
        "parsed": parsed,
        "post_pulse_note": "value=0 is expected post-test; active enforcement proven by deny_count_delta > 0",
        "raw_hint": raw[:300] if not parsed else None,
    }


def _capture_bpftool_state() -> dict[str, object]:
    state: dict[str, object] = {}
    prog = _safe_run(["/usr/local/bin/bpftool", "prog", "show"], timeout=15)
    state["prog_show_rc"] = prog.returncode
    prog_lines = (prog.stdout or "").splitlines()
    state["prog_show_stdout"] = prog_lines
    state["prog_show_stderr"] = (prog.stderr or "").strip()

    # Identify attached LSM hook explicitly
    lsm_hook_lines = [ln for ln in prog_lines if "lsm" in ln.lower() or "bprm_check" in ln.lower() or "arda" in ln.lower()]
    state["lsm_hook_identified"] = bool(lsm_hook_lines)
    state["lsm_hook_lines"] = lsm_hook_lines

    maps = _safe_run(["/usr/local/bin/bpftool", "map", "show"], timeout=15)
    state["map_show_rc"] = maps.returncode
    state["map_show_stdout"] = (maps.stdout or "").splitlines()
    state["map_show_stderr"] = (maps.stderr or "").strip()

    map_id = None
    for line in state["map_show_stdout"]:
        if "arda_state" in line or "arda_state_map" in line:
            parts = line.split()
            if parts:
                try:
                    map_id = int(parts[0].rstrip(":"))
                except ValueError:
                    pass
                break

    if map_id is not None:
        dump = _safe_run(["/usr/local/bin/bpftool", "map", "dump", "id", str(map_id)], timeout=20)
        state["state_map_id"] = map_id
        state["state_map_dump_rc"] = dump.returncode
        dump_lines = (dump.stdout or "").splitlines()
        state["state_map_dump_stdout"] = dump_lines
        state["state_map_dump_stderr"] = (dump.stderr or "").strip()
        state["enforcement_mode"] = _parse_bpftool_enforcement_mode(dump_lines)
    else:
        state["state_map_id"] = None
        state["state_map_dump_stdout"] = []
        state["state_map_dump_stderr"] = "no arda_state map found"
        state["enforcement_mode"] = {"enforcing": None, "parsed": False, "raw_hint": None}

    return state


def _capture_auditd_events(audit_log_path: Path, payload_path: Path) -> dict[str, object]:
    if not audit_log_path.exists():
        return {
            "available": False,
            "path": str(audit_log_path),
            "matches": [],
            "eperm_denials": [],
            "eperm_denial_count": 0,
            "tail": [],
        }

    tail = _tail_file(audit_log_path, lines=500)
    payload_str = str(payload_path)
    matches = [ln for ln in tail if "syscall=59" in ln or "execve" in ln or payload_str in ln]
    # Kernel-level EPERM proof: syscall=59 AND (EPERM or result=-1 or result=-13 or result=denied)
    eperm_denials = [
        ln for ln in tail
        if ("syscall=59" in ln or "execve" in ln or payload_str in ln)
        and ("EPERM" in ln or "result=-1" in ln or "result=-13" in ln or "res=denied" in ln or "result=denied" in ln)
    ]
    return {
        "available": True,
        "path": str(audit_log_path),
        "matches": matches,
        "eperm_denials": eperm_denials,
        "eperm_denial_count": len(eperm_denials),
        "tail": tail[-200:],
    }


def _capture_sigma_correlation(repo_root: Path, technique_id: str | None, started_at: str) -> dict[str, object]:
    """
    Read analytics/sigma_matches.json (if present) and return matches that overlap
    the test time window and relate to the technique under test.
    """
    sigma_path = repo_root / "analytics" / "sigma_matches.json"
    result: dict[str, object] = {
        "available": False,
        "path": str(sigma_path),
        "hits": [],
        "hit_count": 0,
        "technique_hits": [],
        "technique_hit_count": 0,
        "window_start": started_at,
    }
    if not sigma_path.exists():
        return result

    try:
        data = json.loads(sigma_path.read_text(encoding="utf-8"))
    except Exception as e:
        result["error"] = str(e)
        return result

    result["available"] = True
    records = data if isinstance(data, list) else data.get("matches", []) if isinstance(data, dict) else []

    # Parse window start
    try:
        window_start_dt = datetime.fromisoformat(started_at)
        if window_start_dt.tzinfo is None:
            window_start_dt = window_start_dt.replace(tzinfo=timezone.utc)
    except Exception:
        window_start_dt = None

    hits = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        # Check time overlap — accept any of these timestamp keys
        ts_raw = rec.get("timestamp") or rec.get("captured_at") or rec.get("matched_at") or rec.get("ts")
        in_window = True
        if ts_raw and window_start_dt:
            try:
                ts_dt = datetime.fromisoformat(str(ts_raw))
                if ts_dt.tzinfo is None:
                    ts_dt = ts_dt.replace(tzinfo=timezone.utc)
                in_window = ts_dt >= window_start_dt
            except Exception:
                pass
        if in_window:
            hits.append(rec)

    technique_hits = [
        h for h in hits
        if technique_id and technique_id.upper() in str(h.get("techniques") or h.get("technique") or h.get("mitre_technique") or "").upper()
    ]
    result["hits"] = hits
    result["hit_count"] = len(hits)
    result["technique_hits"] = technique_hits
    result["technique_hit_count"] = len(technique_hits)
    return result


def _payload_source_for_technique(technique_id: str, payload_path: Path) -> tuple[str, str]:
    tid = str(technique_id or "").strip().upper()
    payload_path = payload_path.resolve()
    if tid == "T1485":
        return (
            "#!/usr/bin/env bash\nset -euo pipefail\n" +
            f"touch {shlex.quote(str(payload_path.parent / 'target.txt'))}\n" +
            f"echo 'destroy-me' > {shlex.quote(str(payload_path.parent / 'target.txt'))}\n" +
            f"shred -u {shlex.quote(str(payload_path.parent / 'target.txt'))}\n",
            "Impact: script attempts to shred a local file before exiting."
        )
    if tid == "T1003":
        return (
            "#!/usr/bin/env bash\nset -euo pipefail\n" +
            "[ -r /etc/shadow ] && cat /etc/shadow || true\n",
            "Credential Access: script attempts to read /etc/shadow."
        )
    if tid == "T1041":
        return (
            "#!/usr/bin/env bash\nset -euo pipefail\n" +
            "python3 - <<'PY'\nimport socket, os\ntry:\n    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n    s.settimeout(1)\n    s.connect(('127.0.0.1', 9))\nexcept Exception:\n    pass\nfinally:\n    s.close()\nPY\n",
            "Exfiltration: script attempts an outbound socket connection to simulate data exfiltration."
        )
    if tid == "T1071":
        return (
            "#!/usr/bin/env bash\nset -euo pipefail\n" +
            "python3 - <<'PY'\nimport urllib.request\ntry:\n    urllib.request.urlopen('http://127.0.0.1:9', timeout=1)\nexcept Exception:\n    pass\nPY\n",
            "Command and Control: script attempts a network callback to simulate C2."
        )
    if tid == "T1547":
        return (
            "#!/usr/bin/env bash\nset -euo pipefail\n" +
            f"echo 'export PATH=$PATH:{shlex.quote(str(payload_path.parent))}' >> {shlex.quote(str(Path.home() / '.bashrc'))}\n",
            "Persistence: script attempts to add a startup entry to ~/.bashrc."
        )
    if tid == "T1068":
        return (
            "#!/usr/bin/env bash\nset -euo pipefail\n" +
            "sudo -n true 2>/dev/null || true\n",
            "Privilege Escalation: script attempts to use sudo without a password."
        )
    if tid == "T1027":
        return (
            "#!/usr/bin/env bash\nset -euo pipefail\n" +
            f"mv {shlex.quote(str(payload_path))} {shlex.quote(str(payload_path.parent / ('.' + payload_path.name)))} 2>/dev/null || true\n",
            "Defense Evasion: script attempts to hide itself by renaming to a dotfile."
        )
    if tid == "T1082":
        return (
            "#!/usr/bin/env bash\nset -euo pipefail\n" +
            "uname -a\nls -la /proc\n",
            "Discovery: script collects local system information."
        )
    if tid == "T1021":
        return (
            "#!/usr/bin/env bash\nset -euo pipefail\n" +
            "ssh -o BatchMode=yes -o ConnectTimeout=1 127.0.0.1 true 2>/dev/null || true\n",
            "Lateral Movement: script attempts an SSH connection to a local host."
        )
    if tid == "T1595":
        return (
            "#!/usr/bin/env bash\nset -euo pipefail\n" +
            "whois example.com 2>/dev/null || true\n",
            "Reconnaissance: script attempts a whois lookup."
        )
    if tid == "T1583":
        return (
            "#!/usr/bin/env bash\nset -euo pipefail\n" +
            "python3 - <<'PY'\nimport urllib.request\ntry:\n    urllib.request.urlopen('http://example.com', timeout=1)\nexcept Exception:\n    pass\nPY\n",
            "Resource Development: script attempts to fetch a remote resource."
        )
    if tid == "T1005":
        return (
            "#!/usr/bin/env bash\nset -euo pipefail\n" +
            "tar czf /tmp/arda_prevention_payload/collection.tar /etc/passwd 2>/dev/null || true\n",
            "Collection: script attempts to archive local data."
        )
    return (
        "#!/usr/bin/env bash\nset -euo pipefail\n" +
        "echo 'hello'\n",
        "Execution: benign shell script payload."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ARDA exec-prevention evidence (safe harness).")
    parser.add_argument("--technique-id", default="", help="Optional MITRE technique ID (e.g. T1059).")
    parser.add_argument("--test-id", default="arda_exec_prevention_smoke", help="Evidence test identifier.")
    parser.add_argument("--out-dir", default="artifacts/evidence/arda_prevention", help="Where to write evidence JSON.")
    parser.add_argument("--enforce-delay-seconds", type=int, default=1, help="Seconds to wait before enabling enforcement.")
    parser.add_argument("--enforce-seconds", type=int, default=5, help="How long to enable enforcement.")
    parser.add_argument("--attempt-offset-seconds", type=float, default=2.0, help="When to attempt exec after starting loader.")
    parser.add_argument("--loader-start-script", default="scripts/arda_lsm_start.sh")
    parser.add_argument("--loader-stop-script", default="scripts/arda_lsm_stop.sh")
    parser.add_argument("--container-name", default=os.environ.get("ARDA_LSM_CONTAINER_NAME", "arda-lsm-loader"))
    parser.add_argument("--audit-log-path", default=os.environ.get("ARDA_AUDIT_LOG_PATH", "/var/log/audit/audit.log"), help="Path to the audited kernel log file.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    out_dir = (repo_root / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # A safe, benign "atomic-style" executable under /tmp.
    # This should NOT be in the seeded allowlist (seed dirs are /host/* system bins).
    payload_dir = Path("/tmp/arda_prevention_payload")
    payload_dir.mkdir(parents=True, exist_ok=True)
    technique_slug = (args.technique_id or "").strip().upper() or "NO_TECHNIQUE"
    payload_path = payload_dir / f"{technique_slug}.sh"
    payload_source, payload_intent = _payload_source_for_technique(technique_slug, payload_path)
    payload_path.write_text(payload_source, encoding="utf-8")
    payload_path.chmod(0o755)
    payload_hash = _sha256_file(payload_path)

    started_at = _iso_now()

    # Start loader with enforcement pulse.
    env = os.environ.copy()
    env["ARDA_ENFORCE_DELAY_SECONDS"] = str(args.enforce_delay_seconds)
    env["ARDA_ENFORCE_SECONDS"] = str(args.enforce_seconds)
    env["ARDA_LSM_CONTAINER_NAME"] = args.container_name

    start_cmd = f"cd {shlex.quote(str(repo_root))} && {shlex.quote(args.loader_start_script)}"
    stop_cmd = f"cd {shlex.quote(str(repo_root))} && {shlex.quote(args.loader_stop_script)}"

    start_proc = subprocess.run(start_cmd, shell=True, text=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Give the loader time to attach/seed and enter the pulse window.
    time.sleep(max(0.0, float(args.attempt_offset_seconds)))

    exec_exception = None
    try:
        # IMPORTANT: do not use shell=True here; it would exec /bin/sh and can be vetoed,
        # masking whether the payload itself is blocked.
        exec_proc = _run_exec([str(payload_path)])
    except Exception as e:
        # Enforcement may prevent the exec path entirely (PermissionError). Treat as denied.
        exec_exception = repr(e)
        exec_proc = subprocess.CompletedProcess(args=[str(payload_path)], returncode=126, stdout="", stderr=str(e))

    # Wait until enforcement is definitely over so DENY_COUNT_END is printed.
    time.sleep(max(0.0, float(args.enforce_delay_seconds + args.enforce_seconds + 1)))

    logs = _run_shell(f"docker logs {shlex.quote(args.container_name)}", check=False, capture=True)
    container_inspect = _capture_docker_inspect(args.container_name)
    loader_pid = None
    if isinstance(container_inspect, dict):
        loader_pid = container_inspect.get("State", {}).get("Pid") if isinstance(container_inspect.get("State"), dict) else None
    proc_maps = _capture_proc_maps(int(loader_pid)) if loader_pid else []
    bpftool_state = _capture_bpftool_state()
    audit_events = _capture_auditd_events(Path(args.audit_log_path), payload_path)
    dmesg_info = _capture_dmesg_tail()
    sigma_correlation = _capture_sigma_correlation(repo_root, technique_slug if technique_slug != "NO_TECHNIQUE" else None, started_at)

    subprocess.run(stop_cmd, shell=True, text=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    deny_start = None
    deny_end = None
    deny_map_id = None
    for line in (logs.stdout or "").splitlines():
        if line.startswith("DENY_COUNT_MAP_ID="):
            deny_map_id = line.split("=", 1)[1].strip()
        if line.startswith("DENY_COUNT_START="):
            try:
                deny_start = int(line.split("=", 1)[1].strip())
            except Exception:
                pass
        if line.startswith("DENY_COUNT_END="):
            try:
                deny_end = int(line.split("=", 1)[1].strip())
            except Exception:
                pass

    denied = exec_proc.returncode != 0
    evidence = {
        "schema": "arda_prevention_evidence.v2",
        "captured_at": _iso_now(),
        "started_at": started_at,
        "technique_id": (args.technique_id or "").strip().upper() or None,
        "test_id": args.test_id,
        "control_plane": {
            "loader_container": args.container_name,
            "start_rc": start_proc.returncode,
            "start_stdout_tail": (start_proc.stdout or "").splitlines()[-30:],
            "start_stderr_tail": (start_proc.stderr or "").splitlines()[-30:],
            "docker_inspect": container_inspect,
            "loader_pid": loader_pid,
            "proc_maps": proc_maps,
            "lsm_hook_identified": bpftool_state.get("lsm_hook_identified", False),
            "lsm_hook_lines": bpftool_state.get("lsm_hook_lines", []),
        },
        "enforcement": {
            "delay_seconds": args.enforce_delay_seconds,
            "enforce_seconds": args.enforce_seconds,
            "deny_count_map_id": deny_map_id,
            "deny_count_start": deny_start,
            "deny_count_end": deny_end,
            "deny_count_delta": (deny_end - deny_start) if isinstance(deny_start, int) and isinstance(deny_end, int) else None,
            "enforcement_mode": bpftool_state.get("enforcement_mode"),
        },
        "exec_attempt": {
            "path": str(payload_path),
            "expected": "deny",
            "denied": denied,
            "rc": exec_proc.returncode,
            "stdout": (exec_proc.stdout or "").strip(),
            "stderr": (exec_proc.stderr or "").strip(),
            "exception": exec_exception,
            "payload_sha256": payload_hash,
            "payload_intent": payload_intent,
            "payload_content_lines": payload_source.splitlines(),
        },
        "system_state": {
            "bpftool": bpftool_state,
            "audit_log": audit_events,
            "dmesg": dmesg_info,
            "sigma_correlation": sigma_correlation,
        },
        "loader_logs_tail": (logs.stdout or "").splitlines()[-120:],
    }

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    technique_slug = (args.technique_id or "").strip().upper() or "NO_TECHNIQUE"
    out_path = out_dir / f"arda_prevention_{technique_slug}_{ts}.json"
    out_path.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
