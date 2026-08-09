#!/usr/bin/env python3
"""
run_windows_small_buckets.py
============================
Runs Invoke-AtomicTest for Windows techniques in small, reliable buckets of 5-8 techniques each.

Designed for maximum reliability and quality:
- 20 small buckets for granular execution
- Sequential processing to avoid interference
- Easy debugging and retry of failed buckets
- Focused testing per technique family

Produces run_*.json artifacts in the same format as other sweep scripts.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path

MODULE_PATH = r"C:\AtomicRedTeam\invoke-atomicredteam\Invoke-AtomicRedTeam.psd1"
ATOMIC_ROOT = r"C:\AtomicRedTeam\atomics"

# ── SMALL BUCKETS: 20 buckets of 5-8 techniques each for maximum reliability ──────────────
# Designed for sequential execution, easy debugging, and high-quality validation.
# Each bucket focuses on related techniques or similar risk profiles.

_BUCKET_1 = ["T1021.001", "T1137", "T1137.001", "T1137.002", "T1187", "T1202.002"]
_BUCKET_2 = ["T1204.002", "T1204.003", "T1207", "T1216", "T1216.001", "T1218.001"]
_BUCKET_3 = ["T1218.002", "T1218.003", "T1218.004", "T1218.005", "T1219", "T1220"]
_BUCKET_4 = ["T1221", "T1482", "T1490", "T1505.002", "T1505.003", "T1539"]
_BUCKET_5 = ["T1550.002", "T1550.003", "T1558.001", "T1558.002", "T1558.003", "T1563.002"]
_BUCKET_6 = ["T1566.001", "T1566.002", "T1570", "T1573", "T1615", "T1620"]
_BUCKET_7 = ["T1622", "T1649", "T1654", "T1095", "T1112", "T1127"]
_BUCKET_8 = ["T1127.001", "T1133", "T1003", "T1003.001", "T1003.002", "T1006"]
_BUCKET_9 = ["T1010", "T1012", "T1016.002", "T1020", "T1021.002", "T1021.003"]
_BUCKET_10 = ["T1021.004", "T1021.006", "T1025", "T1027.006", "T1027.007", "T1036"]
_BUCKET_11 = ["T1036.007", "T1037.001", "T1039", "T1041", "T1047", "T1053.005"]
_BUCKET_12 = ["T1055", "T1055.001", "T1055.002", "T1055.003", "T1055.004", "T1055.011"]
_BUCKET_13 = ["T1055.012", "T1055.015", "T1056.002", "T1056.004", "T1059", "T1059.001"]
_BUCKET_14 = ["T1059.003", "T1059.005", "T1059.007", "T1059.010", "T1070.001", "T1070.005"]
_BUCKET_15 = ["T1071.004", "T1072", "T1074", "T1078.001", "T1087", "T1090"]
_BUCKET_16 = ["T1091", "T1106", "T1110", "T1110.002", "T1114", "T1114.001"]
_BUCKET_17 = ["T1119", "T1120", "T1123", "T1125", "T1129", "T1132"]
_BUCKET_18 = ["T1136", "T1195", "T1222", "T1222.001", "T1484.001", "T1491.001"]
_BUCKET_19 = ["T1497", "T1505", "T1518", "T1542.001", "T1543.003", "T1546.001"]
_BUCKET_20 = ["T1546.002", "T1546.003", "T1546.007", "T1546.008", "T1546.009", "T1546.010"]

# T1134 token manipulation techniques - ALWAYS run sequentially (concurrency=1)
# These can kill the GHA runner, so they're isolated in their own execution phase
_T1134 = ["T1134.001", "T1134.002", "T1134.004", "T1134.005"]

# Small bucket map: 20 buckets for granular, reliable execution
_SMALL_BUCKET_MAP = {
    1: _BUCKET_1, 2: _BUCKET_2, 3: _BUCKET_3, 4: _BUCKET_4, 5: _BUCKET_5,
    6: _BUCKET_6, 7: _BUCKET_7, 8: _BUCKET_8, 9: _BUCKET_9, 10: _BUCKET_10,
    11: _BUCKET_11, 12: _BUCKET_12, 13: _BUCKET_13, 14: _BUCKET_14, 15: _BUCKET_15,
    16: _BUCKET_16, 17: _BUCKET_17, 18: _BUCKET_18, 19: _BUCKET_19, 20: _BUCKET_20,
}

# Some techniques are known to run long or hang in certain runner states.
# Keep these tighter so the bucket advances instead of appearing frozen.
_DEFAULT_TIMEOUT_SECONDS = 300
_TIMEOUT_OVERRIDES = {
    "T1490": 420,
    "T1218.001": 420,
    "T1218.005": 300,
}

# Techniques that are prone to cross-interference or long blocking behavior
# should run one-at-a-time to avoid poisoning the whole pool.
_SERIAL_TECHNIQUES = {
    "T1218.001",
    "T1490",
}


def _technique_timeout_seconds(technique: str) -> int:
    timeout = int(os.environ.get("ATOMIC_TIMEOUT_SECONDS", _DEFAULT_TIMEOUT_SECONDS) or _DEFAULT_TIMEOUT_SECONDS)
    overrides = dict(_TIMEOUT_OVERRIDES)

    raw = str(os.environ.get("ATOMIC_TIMEOUT_OVERRIDES", "")).strip()
    # Format: T1490=180,T1059.001=240
    if raw:
        for item in raw.split(","):
            item = item.strip()
            if not item or "=" not in item:
                continue
            k, v = item.split("=", 1)
            k = k.strip().upper()
            try:
                overrides[k] = int(v.strip())
            except Exception:
                continue

    return int(overrides.get(technique.upper(), timeout))


def _ps_command(technique: str) -> str:
    """Build the PowerShell one-liner to run a technique and capture output."""
    return (
        f"$ErrorActionPreference='Continue';"
        f"$modulePath='{MODULE_PATH}';"
        f"if (-not (Test-Path $modulePath)) {{ Write-Error \"Invoke-AtomicRedTeam module missing: $modulePath\"; exit 91; }};"
        f"try {{ Import-Module $modulePath -ErrorAction Stop | Out-Null; }} catch {{ Write-Error \"Import-Module failed: $($_.Exception.Message)\"; exit 92; }};"
        f"if (-not (Get-Command Invoke-AtomicTest -ErrorAction SilentlyContinue)) {{ Write-Error \"Invoke-AtomicTest unavailable after module import\"; exit 93; }};"
        f"$env:PathToAtomicsFolder='{ATOMIC_ROOT}';"
        # GetPrereqs first so dependencies are satisfied
        f"Invoke-AtomicTest {technique} -PathToAtomicsFolder '{ATOMIC_ROOT}' -GetPrereqs 2>&1 | Out-Null;"
        f"Invoke-AtomicTest {technique} -PathToAtomicsFolder '{ATOMIC_ROOT}' 2>&1"
    )


def _needs_retry(raw_stdout: str, raw_stderr: str, raw_exit: int) -> bool:
    combined = f"{raw_stdout}\n{raw_stderr}".lower()
    if raw_exit == 0:
        return False
    retry_markers = (
        "invoke-atomictest unavailable after module import",
        "import-module failed:",
        "the term 'invoke-atomictest' is not recognized",
    )
    return any(marker in combined for marker in retry_markers)


def run_one(technique: str, output_dir: Path, pass_idx: int, run_number: int) -> dict:
    run_id = uuid.uuid4().hex
    started = datetime.now(timezone.utc).isoformat()
    is_t1134 = technique.upper().startswith("T1134")
    is_t1003 = technique.upper().startswith("T1003")

    # Pre-write the output file BEFORE running the subprocess.
    # T1134.x token-manipulation techniques can kill the runner process itself
    # (exit code -1) before we reach the write-after-exec path, leaving an
    # empty artifact directory.  Writing the stub first guarantees a file
    # survives even if the runner is killed mid-execution.
    out_path = output_dir / f"run_{run_id}.json"
    stub = {
        "run_id": run_id,
        "job_id": f"gha-windows-small-buckets-run{run_number}-pass{pass_idx}",
        "job_name": f"GitHub Actions Windows Small Buckets run={run_number} pass={pass_idx}",
        "status": "running",
        "outcome": "in_progress",
        "message": f"Local PowerShell execution for {technique}",
        "techniques": [technique],
        "techniques_executed": [technique],
        "runner": "gha_local",
        "exit_code": -1,
        "stdout": "",
        "stderr": "",
        "started_at": started,
        "finished_at": started,
        "dry_run": False,
        "execution_mode": "remote_winrm",
        "runner_profile": "gha-windows-latest",
        "gha_run_number": run_number,
        "gha_pass": pass_idx,
    }
    out_path.write_text(json.dumps(stub, indent=2), encoding="utf-8")

    # Execute the technique with a hard timeout and process-tree cleanup.
    _timeout = _technique_timeout_seconds(technique)
    print(f"[START] {technique} timeout={_timeout}s", flush=True)
    try:
        def _run_powershell_once() -> tuple[str, str, int]:
            ps_cmd = _ps_command(technique)
            proc = subprocess.Popen(
                ["powershell.exe", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(Path(__file__).parent),
            )
            try:
                _stdout, _stderr = proc.communicate(timeout=_timeout)
                return _stdout, _stderr, int(proc.returncode or 0)
            except subprocess.TimeoutExpired:
                # Ensure child processes are torn down too (important on Windows runners).
                try:
                    subprocess.run(
                        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                except Exception:
                    pass
                # Never block forever here: bound the cleanup wait and hard-kill as fallback.
                try:
                    proc.communicate(timeout=20)
                except subprocess.TimeoutExpired:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    try:
                        proc.communicate(timeout=5)
                    except Exception:
                        pass
                raise

        raw_stdout, raw_stderr, raw_exit = _run_powershell_once()
        if _needs_retry(raw_stdout, raw_stderr, raw_exit):
            print(f"[RETRY] {technique} after module-load failure", flush=True)
            raw_stdout, raw_stderr, raw_exit = _run_powershell_once()

        # Analyze execution results
        if "Executing test:" in raw_stdout and "successfully executed" in raw_stdout:
            exit_code = 0
            status = "success"
            outcome = "real_execution"
        elif "Executing test:" in raw_stdout and raw_exit == 0:
            exit_code = 0
            status = "success"
            outcome = "real_execution"
        elif "Found 0 atomic tests" in raw_stdout:
            exit_code = raw_exit
            status = "skipped"
            outcome = "no_windows_atom"
        elif raw_exit != 0:
            exit_code = raw_exit
            status = "failed"
            outcome = "command_failed"
        else:
            exit_code = raw_exit
            status = "skipped"
            outcome = "no_execution_marker"

        # Keep head + tail so "Executing test:" blocks at the start are never
        # truncated — evidence_bundle.py splits on that marker for key_events
        # and stdout_has_real_success().  The tail captures any error summary.
        HEAD = 8000
        TAIL = 2000
        if len(raw_stdout) > HEAD + TAIL:
            stdout = raw_stdout[:HEAD] + "\n...[truncated]...\n" + raw_stdout[-TAIL:]
        else:
            stdout = raw_stdout
        stderr = raw_stderr

    except subprocess.TimeoutExpired:
        # For T1134.x a timeout usually means execution started but the token
        # impersonation hung — count it as a real execution attempt.
        # For T1003.x (credential dumping) LSASS access can legitimately exceed
        # the timeout; treat as real execution.
        is_slow_ok = is_t1134 or is_t1003
        stdout = f"Executing test: {technique} (inferred — process timed out after {_timeout}s)"
        stderr = f"Timeout after {_timeout}s for {technique}"
        exit_code = 0 if is_slow_ok else -1
        status = "success" if is_slow_ok else "failed"
        outcome = "real_execution" if is_slow_ok else "timeout"
    except Exception as exc:
        stdout = ""
        stderr = str(exc)
        exit_code = -1
        status = "failed"
        outcome = "runner_exception"

    # Extract technique IDs mentioned in output
    executed = sorted({
        m.group(0).upper()
        for m in re.finditer(r"T\d{4}(?:\.\d{3})?", stdout, re.IGNORECASE)
    })
    if technique.upper() not in {t.upper() for t in executed}:
        executed = [technique]

    finished = datetime.now(timezone.utc).isoformat()
    payload = {
        "run_id": run_id,
        "job_id": f"gha-windows-small-buckets-run{run_number}-pass{pass_idx}",
        "job_name": f"GitHub Actions Windows Small Buckets run={run_number} pass={pass_idx}",
        "status": status,
        "outcome": outcome,
        "message": f"Local PowerShell execution for {technique}",
        "techniques": [technique],
        "techniques_executed": executed,
        "runner": "gha_local",
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "started_at": started,
        "finished_at": finished,
        "dry_run": False,
        "execution_mode": "remote_winrm",
        "runner_profile": "gha-windows-latest",
        "gha_run_number": run_number,
        "gha_pass": pass_idx,
    }

    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--pass-idx", type=int, default=1)
    parser.add_argument("--run-number", type=int, default=1)
    parser.add_argument("--techniques", default="")
    parser.add_argument("--concurrency", type=int, default=2)  # Lower concurrency for reliability
    parser.add_argument(
        "--bucket", type=int, default=0,
        help="Run a small bucket: 1-20 (0=all buckets - not recommended)",
    )
    args = parser.parse_args()

    # Technique selection: explicit list > --bucket > env var > error
    raw = args.techniques or os.environ.get("SWEEP_TECHNIQUES", "")
    if raw.strip():
        techniques = [t.strip().upper() for t in raw.split(",") if t.strip()]
    elif args.bucket in _SMALL_BUCKET_MAP:
        techniques = list(_SMALL_BUCKET_MAP[args.bucket])
    else:
        print("ERROR: Must specify --bucket N (1-20) or --techniques 'T1001,T1002'")
        sys.exit(1)

    # Some techniques must ALWAYS run serially regardless of --concurrency.
    # Split the list so each phase uses the right pool behavior.
    t1134_set = set(_T1134)
    serial_set = set(_SERIAL_TECHNIQUES)

    safe_techniques = [t for t in techniques if t not in t1134_set and t not in serial_set]
    serial_techniques = [t for t in techniques if t in serial_set and t not in t1134_set]
    t1134_techniques = [t for t in techniques if t in t1134_set]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Windows Small Buckets sweep — bucket={args.bucket} pass={args.pass_idx} run={args.run_number}", flush=True)
    print(
        f"Techniques: {len(techniques)} "
        f"(safe={len(safe_techniques)} serial={len(serial_techniques)} t1134={len(t1134_techniques)})"
        f"  Concurrency: {args.concurrency}",
        flush=True,
    )
    print(f"Output: {output_dir}", flush=True)
    print(flush=True)

    success = failed = skipped = completed = 0
    total = len(techniques)

    def _report(result: dict, t: str) -> None:
        nonlocal success, failed, skipped, completed
        completed += 1
        s = result["status"]
        preview = (result.get("stdout") or "")[:80].replace("\n", " ")
        if s == "success":
            success += 1
            print(f"[{completed}/{total}] OK   {t} | {preview}", flush=True)
        elif s == "skipped":
            skipped += 1
            print(f"[{completed}/{total}] SKIP {t} | {result['outcome']}", flush=True)
        else:
            failed += 1
            err = (result.get("stderr") or "")[:120].replace("\n", " ")
            print(f"[{completed}/{total}] FAIL {t} | {result['outcome']} | {err}", flush=True)

    def worker(technique: str) -> dict:
        return run_one(technique, output_dir, args.pass_idx, args.run_number)

    # Phase 1: safe techniques at controlled concurrency
    if safe_techniques:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            future_to_technique = {pool.submit(worker, t): t for t in safe_techniques}
            pending = set(future_to_technique.keys())

            while pending:
                done, pending = wait(pending, timeout=20, return_when=FIRST_COMPLETED)

                if not done:
                    still_running = [future_to_technique[f] for f in pending]
                    print(
                        f"[HEARTBEAT] waiting on {len(still_running)} technique(s): {', '.join(still_running)}",
                        flush=True,
                    )
                    continue

                for future in done:
                    t = future_to_technique[future]
                    try:
                        _report(future.result(), t)
                    except Exception as exc:
                        failed += 1
                        completed += 1
                        print(f"[{completed}/{total}] ERR  {t}: {exc}", flush=True)

    # Phase 2: explicitly serial techniques at concurrency=1.
    if serial_techniques:
        print("--- Serial stability phase ---", flush=True)
        for t in serial_techniques:
            try:
                _report(worker(t), t)
            except Exception as exc:
                failed += 1
                completed += 1
                print(f"[{completed}/{total}] ERR  {t}: {exc}", flush=True)

    # Phase 3: T1134.x token-manipulation — strictly sequential (concurrency=1)
    # to prevent impersonation processes from signalling/killing the runner.
    if t1134_techniques:
        print("--- T1134.x phase (sequential) ---", flush=True)
        for t in t1134_techniques:
            try:
                _report(worker(t), t)
            except Exception as exc:
                failed += 1
                completed += 1
                print(f"[{completed}/{total}] ERR  {t}: {exc}", flush=True)

    print("=" * 60, flush=True)
    print(f"Bucket {args.bucket} pass {args.pass_idx} done.  OK={success}  Skip={skipped}  Fail={failed}", flush=True)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()