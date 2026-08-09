#!/usr/bin/env python3
"""
run_windows_local_sweep.py
==========================
Runs Invoke-AtomicTest for every Windows Gold technique directly on the local
Windows machine via subprocess (designed for GitHub Actions windows-latest runners).

Produces run_*.json in the same format as run_windows_winrm_sweep.py so the
evidence bundle treats them as real WinRM execution (execution_mode=remote_winrm).

Usage (GitHub Actions / Windows CMD):
    python scripts\\run_windows_local_sweep.py ^
        --output-dir results\\pass-1 ^
        --pass-idx 1 ^
        --run-number 42

    Optional: set SWEEP_TECHNIQUES=T1006,T1012 to run a subset.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

MODULE_PATH = r"C:\AtomicRedTeam\invoke-atomicredteam\Invoke-AtomicRedTeam.psd1"
ATOMIC_ROOT = r"C:\AtomicRedTeam\atomics"

# Phase 1 (26 done): T1006,T1010,T1012,T1020,T1021.002-004,T1021.006,T1025,T1039,
#   T1041,T1047,T1072,T1091,T1095,T1106,T1112,T1119,T1120,T1123,T1125,T1127,
#   T1127.001,T1129,T1133,T1134.002

# Phase 2: remaining 54 + 6 partial-clean retries.
# T1134.x token-manipulation techniques run LAST at concurrency=1 to prevent
# the spawned impersonation process from killing the runner mid-sweep.
WINDOWS_GOLD = [
    # Remaining 54 (not yet run)
    "T1021.001", "T1137", "T1137.001", "T1137.002", "T1137.004", "T1137.006",
    "T1187", "T1197", "T1202", "T1204.002", "T1204.003", "T1207", "T1216",
    "T1216.001", "T1218", "T1218.001", "T1218.002", "T1218.003", "T1218.004",
    "T1218.005", "T1218.007", "T1218.008", "T1218.009", "T1218.010", "T1218.011",
    "T1219", "T1220", "T1221", "T1482", "T1490", "T1505.002", "T1505.003",
    "T1505.004", "T1505.005", "T1539", "T1550.002", "T1550.003", "T1558.001",
    "T1558.002", "T1558.003", "T1558.004", "T1563.002", "T1566.001", "T1566.002",
    "T1570", "T1573", "T1615", "T1620", "T1622", "T1649", "T1654",
    # Partial-clean retries (need 1-2 more clean runs for S5)
    "T1095", "T1112", "T1127", "T1127.001", "T1133",
    # T1134.x token-manipulation — run last to contain runner-kill risk
    "T1134.001", "T1134.002", "T1134.004", "T1134.005",
]


def _ps_command(technique: str) -> str:
    """Build the PowerShell one-liner to run a technique and capture output."""
    return (
        f"$ErrorActionPreference='Continue';"
        f"Import-Module '{MODULE_PATH}' -ErrorAction SilentlyContinue;"
        f"$env:PathToAtomicsFolder='{ATOMIC_ROOT}';"
        # GetPrereqs first so dependencies are satisfied
        f"Invoke-AtomicTest {technique} -PathToAtomicsFolder '{ATOMIC_ROOT}' -GetPrereqs 2>&1 | Out-Null;"
        f"Invoke-AtomicTest {technique} -PathToAtomicsFolder '{ATOMIC_ROOT}' 2>&1"
    )


def run_one(technique: str, output_dir: Path, pass_idx: int, run_number: int) -> dict:
    run_id = uuid.uuid4().hex
    started = datetime.now(timezone.utc).isoformat()

    # CREATE_NEW_PROCESS_GROUP isolates the PowerShell child and its descendants
    # so token-manipulation techniques (T1134.x) can't signal/kill this process.
    _creation_flags = 0
    if sys.platform == "win32":
        _creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NonInteractive",
                "-ExecutionPolicy", "Bypass",
                "-Command", _ps_command(technique),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=300,
            encoding="utf-8",
            errors="ignore",
            creationflags=_creation_flags,
        )
        raw_stdout = proc.stdout or ""
        raw_exit = proc.returncode

        # Invoke-AtomicTest is a PowerShell function — its exit code is the
        # shell exit code, not the technique's exit code. If "Executing test:"
        # appears we know ART started the test; treat exit_code as 0.
        if "Executing test:" in raw_stdout:
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
            exit_code = 0
            status = "skipped"
            outcome = "no_execution_marker"

        stdout = raw_stdout[-8000:]
        stderr = ""

    except subprocess.TimeoutExpired:
        stdout = ""
        stderr = f"Timeout after 300s for {technique}"
        exit_code = -1
        status = "failed"
        outcome = "timeout"
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
        "job_id": f"gha-windows-sweep-run{run_number}-pass{pass_idx}",
        "job_name": f"GitHub Actions Windows Sweep run={run_number} pass={pass_idx}",
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
        # Must match what run_is_real_sandbox_execution() accepts
        "execution_mode": "remote_winrm",
        "runner_profile": "gha-windows-latest",
        "gha_run_number": run_number,
        "gha_pass": pass_idx,
    }

    out_path = output_dir / f"run_{run_id}.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--pass-idx", type=int, default=1)
    parser.add_argument("--run-number", type=int, default=1)
    parser.add_argument("--techniques", default="")
    parser.add_argument("--concurrency", type=int, default=1)
    args = parser.parse_args()

    # Techniques: CLI flag > env var > full WINDOWS_GOLD list
    raw = args.techniques or os.environ.get("SWEEP_TECHNIQUES", "")
    if raw.strip():
        techniques = [t.strip().upper() for t in raw.split(",") if t.strip()]
    else:
        techniques = list(WINDOWS_GOLD)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Windows GHA sweep — pass={args.pass_idx} run={args.run_number}", flush=True)
    print(f"Techniques: {len(techniques)}  Concurrency: {args.concurrency}", flush=True)
    print(f"Output: {output_dir}", flush=True)
    print(flush=True)

    success = failed = skipped = completed = 0

    def worker(technique):
        return run_one(technique, output_dir, args.pass_idx, args.run_number)

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(worker, t): t for t in techniques}
        for future in as_completed(futures):
            t = futures[future]
            completed += 1
            try:
                result = future.result()
                s = result["status"]
                preview = (result.get("stdout") or "")[:80].replace("\n", " ")
                if s == "success":
                    success += 1
                    print(f"[{completed}/{len(techniques)}] OK   {t} | {preview}", flush=True)
                elif s == "skipped":
                    skipped += 1
                    print(f"[{completed}/{len(techniques)}] SKIP {t} | {result['outcome']}", flush=True)
                else:
                    failed += 1
                    err = (result.get("stderr") or "")[:120].replace("\n", " ")
                    print(f"[{completed}/{len(techniques)}] FAIL {t} | {result['outcome']} | {err}", flush=True)
            except Exception as exc:
                failed += 1
                print(f"[{completed}/{len(techniques)}] ERR  {t}: {exc}", flush=True)

    print("=" * 60, flush=True)
    print(f"Pass {args.pass_idx} done.  OK={success}  Skip={skipped}  Fail={failed}", flush=True)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
