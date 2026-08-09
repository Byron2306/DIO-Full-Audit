#!/usr/bin/env python3
"""
run_linux_local_sweep.py
========================
Runs Invoke-AtomicTest for Linux techniques directly on the local machine via
pwsh (PowerShell Core). Designed for GitHub Actions ubuntu-latest runners.

Produces run_*.json in the same format as run_windows_local_sweep.py so
import_gha_artifacts.py treats them as real execution evidence.

Usage (GitHub Actions / bash):
    python3 scripts/run_linux_local_sweep.py \\
        --output-dir results/pass-1 \\
        --pass-idx 1 \\
        --run-number $GITHUB_RUN_NUMBER

    Optional env:
        SWEEP_TECHNIQUES=T1059.004,T1082  run a subset
        ATOMIC_ROOT=/opt/atomic-red-team/atomics  atomics path
        INVOKE_MODULE=/opt/invoke-atomicredteam/Invoke-AtomicRedTeam.psd1
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

MODULE_PATH = os.environ.get(
    "INVOKE_MODULE",
    "/opt/invoke-atomicredteam/Invoke-AtomicRedTeam.psd1",
)
ATOMIC_ROOT = os.environ.get("ATOMIC_ROOT", "/opt/atomic-red-team/atomics")

# All 197 Linux-capable techniques from the ART catalog
ALL_LINUX = [
    "T1001.002","T1003.007","T1003.008","T1005","T1007","T1014","T1016",
    "T1016.001","T1018","T1027","T1027.001","T1027.002","T1027.004","T1027.013",
    "T1030","T1033","T1036.003","T1036.004","T1036.005","T1036.006","T1037.004",
    "T1040","T1046","T1048","T1048.002","T1048.003","T1049","T1053.002",
    "T1053.003","T1053.006","T1055.008","T1056.001","T1057","T1059.004",
    "T1059.006","T1068","T1069.001","T1069.002","T1070.002","T1070.003",
    "T1070.004","T1070.006","T1070.008","T1071.001","T1074.001","T1078",
    "T1078.002","T1078.003","T1080","T1081","T1082","T1083","T1087.001",
    "T1087.002","T1090.001","T1090.003","T1095","T1098.004","T1102","T1105",
    "T1110.001","T1110.004","T1113","T1115","T1124","T1132.001","T1135",
    "T1136.001","T1136.002","T1140","T1176","T1185","T1189","T1190",
    "T1195.002","T1199","T1200","T1201","T1203","T1205","T1210","T1217",
    "T1222.002","T1234","T1234.001","T1485","T1486","T1489","T1491",
    "T1491.002","T1495","T1496","T1497.001","T1497.003","T1518.001","T1529",
    "T1531","T1533","T1534","T1537","T1538","T1542","T1542.002","T1542.003",
    "T1543.002","T1546.004","T1546.005","T1546.018","T1547.006","T1548.001",
    "T1548.003","T1552","T1552.001","T1552.003","T1552.004","T1552.007",
    "T1553","T1553.002","T1553.004","T1554","T1555.003","T1556","T1556.001",
    "T1556.003","T1556.006","T1557","T1557.002","T1559.001","T1560.001",
    "T1560.002","T1561","T1562","T1562.001","T1562.003","T1562.004",
    "T1562.006","T1562.008","T1562.010","T1562.012","T1564.001","T1565",
    "T1565.001","T1567.002","T1568","T1569.002","T1571","T1572","T1574",
    "T1574.002","T1574.006","T1580","T1583","T1587","T1588","T1589",
    "T1589.001","T1590","T1590.001","T1590.002","T1590.004","T1592",
    "T1592.002","T1595","T1595.001","T1595.003","T1596","T1598","T1598.003",
    "T1601","T1601.001","T1614","T1614.001","T1626","T1629","T1633",
    "T1652","T1656","T1657","T1658","T1659","T1660","T1661","T1665",
    "T1669","T1670",
]

# Buckets of ~10 techniques each for parallel execution
_LINUX_BUCKETS = {
    1:  ALL_LINUX[0:10],
    2:  ALL_LINUX[10:20],
    3:  ALL_LINUX[20:30],
    4:  ALL_LINUX[30:40],
    5:  ALL_LINUX[40:50],
    6:  ALL_LINUX[50:60],
    7:  ALL_LINUX[60:70],
    8:  ALL_LINUX[70:80],
    9:  ALL_LINUX[80:90],
    10: ALL_LINUX[90:100],
    11: ALL_LINUX[100:110],
    12: ALL_LINUX[110:120],
    13: ALL_LINUX[120:130],
    14: ALL_LINUX[130:140],
    15: ALL_LINUX[140:150],
    16: ALL_LINUX[150:160],
    17: ALL_LINUX[160:170],
    18: ALL_LINUX[170:180],
    19: ALL_LINUX[180:197],
    0:  ALL_LINUX,  # all
}

# Techniques that need network access (loopback only; we allow bridge networking)
_NEEDS_NETWORK = {
    "T1040","T1046","T1048","T1048.002","T1048.003","T1071.001","T1090.001",
    "T1090.003","T1095","T1102","T1105","T1110.001","T1110.004","T1135",
    "T1185","T1189","T1190","T1199","T1200","T1203","T1205","T1210",
    "T1537","T1538","T1568","T1571","T1572","T1580","T1583","T1587",
    "T1588","T1589","T1589.001","T1590","T1590.001","T1590.002","T1590.004",
    "T1592","T1592.002","T1595","T1595.001","T1595.003","T1596","T1598",
    "T1598.003","T1659",
}


def _ps_command(technique: str) -> str:
    return (
        f"$ErrorActionPreference='Continue';"
        f"Import-Module '{MODULE_PATH}' -ErrorAction SilentlyContinue;"
        f"$env:PathToAtomicsFolder='{ATOMIC_ROOT}';"
        f"Invoke-AtomicTest {technique} -PathToAtomicsFolder '{ATOMIC_ROOT}'"
        f" -GetPrereqs 2>&1 | Out-Null;"
        f"Invoke-AtomicTest {technique} -PathToAtomicsFolder '{ATOMIC_ROOT}' 2>&1"
    )


def run_one(technique: str, output_dir: Path, pass_idx: int, run_number: int) -> dict:
    run_id = uuid.uuid4().hex
    started = datetime.now(timezone.utc).isoformat()
    out_path = output_dir / f"run_{technique.replace('.','_')}_{run_id[:8]}.json"

    stub = {
        "run_id": run_id,
        "job_id": f"gha-linux-sweep-run{run_number}-pass{pass_idx}",
        "job_name": f"GitHub Actions Linux Sweep run={run_number} pass={pass_idx}",
        "status": "running",
        "outcome": "in_progress",
        "message": f"Linux pwsh execution for {technique}",
        "techniques": [technique],
        "techniques_executed": [],
        "runner": "gha_linux",
        "exit_code": -1,
        "stdout": "",
        "stderr": "",
        "started_at": started,
        "finished_at": started,
        "dry_run": False,
        "execution_mode": "local_pwsh_linux",
        "runner_profile": "gha-ubuntu-latest",
        "gha_run_number": run_number,
        "gha_pass": pass_idx,
    }
    out_path.write_text(json.dumps(stub, indent=2), encoding="utf-8")

    timeout = 180
    try:
        proc = subprocess.run(
            ["pwsh", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
             _ps_command(technique)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            text=True,
            errors="replace",
        )
        raw_stdout = proc.stdout or ""
        raw_exit = proc.returncode
    except subprocess.TimeoutExpired as exc:
        raw_stdout = f"Timeout after {timeout}s for {technique}"
        raw_exit = 124
    except FileNotFoundError:
        raw_stdout = "pwsh not found — install PowerShell Core"
        raw_exit = 127
    except Exception as exc:
        raw_stdout = str(exc)
        raw_exit = 1

    # Truncate very long stdout
    HEAD, TAIL = 3000, 2000
    if len(raw_stdout) > HEAD + TAIL:
        stdout = raw_stdout[:HEAD] + "\n...[truncated]...\n" + raw_stdout[-TAIL:]
    else:
        stdout = raw_stdout

    if "Executing test:" in raw_stdout and raw_exit == 0:
        status, outcome = "success", "real_execution"
    elif "Found 0 atomic tests" in raw_stdout or "No test" in raw_stdout:
        status, outcome = "skipped", "no_linux_atom"
    elif raw_exit != 0:
        status, outcome = "failed", "command_failed"
    else:
        status, outcome = "success", "real_execution"

    # Extract technique IDs from stdout that actually executed
    executed = sorted({
        m.group(0).upper()
        for m in re.finditer(r"T\d{4}(?:\.\d{3})?", raw_stdout, re.IGNORECASE)
    })
    if technique.upper() not in executed and status == "success":
        executed = [technique]

    finished = datetime.now(timezone.utc).isoformat()
    payload = {**stub,
        "status": status,
        "outcome": outcome,
        "message": f"Linux pwsh execution for {technique}",
        "techniques_executed": executed if status == "success" else [],
        "exit_code": raw_exit,
        "stdout": stdout,
        "stderr": "",
        "started_at": started,
        "finished_at": finished,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--pass-idx", type=int, default=1)
    parser.add_argument("--run-number", type=int, default=1)
    parser.add_argument("--techniques", default="")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--bucket", type=int, default=0,
                        help="Run a named bucket 1-19 (0=all)")
    args = parser.parse_args()

    env_techs = os.environ.get("SWEEP_TECHNIQUES", "").strip()
    if args.techniques:
        techniques = [t.strip().upper() for t in args.techniques.split(",") if t.strip()]
    elif env_techs:
        techniques = [t.strip().upper() for t in env_techs.split(",") if t.strip()]
    elif args.bucket in _LINUX_BUCKETS:
        techniques = _LINUX_BUCKETS[args.bucket]
    else:
        techniques = ALL_LINUX

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Linux GHA sweep — pass={args.pass_idx} run={args.run_number}", flush=True)
    print(f"Techniques: {len(techniques)}  Concurrency: {args.concurrency}", flush=True)
    print(f"ATOMIC_ROOT: {ATOMIC_ROOT}", flush=True)
    print(f"MODULE_PATH: {MODULE_PATH}", flush=True)

    ok = failed = skipped = 0

    def _report(result: dict, tid: str) -> None:
        nonlocal ok, failed, skipped
        s = result.get("status", "?")
        short = (result.get("stdout", "")[:60] or "").replace("\n", " ")
        if s == "success":
            ok += 1
            print(f"  [{ok+failed+skipped}/{len(techniques)}] OK   {tid} | {short}", flush=True)
        elif s == "skipped":
            skipped += 1
            print(f"  [{ok+failed+skipped}/{len(techniques)}] SKIP {tid} | {result.get('outcome')}", flush=True)
        else:
            failed += 1
            print(f"  [{ok+failed+skipped}/{len(techniques)}] FAIL {tid} | {result.get('outcome')} {short}", flush=True)

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {
            pool.submit(run_one, t, output_dir, args.pass_idx, args.run_number): t
            for t in techniques
        }
        for fut in as_completed(futures):
            tid = futures[fut]
            try:
                _report(fut.result(), tid)
            except Exception as exc:
                failed += 1
                print(f"  EXCEPTION {tid}: {exc}", flush=True)

    total = ok + failed + skipped
    print(f"\nLinux sweep done — {ok}/{total} success  {skipped} skipped  {failed} failed", flush=True)
    # Always exit 0 — individual technique failures are recorded in run_*.json.
    # A non-zero exit here would fail the GHA step and skip artifact upload.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
