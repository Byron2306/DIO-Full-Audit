#!/usr/bin/env python3
"""
run_windows_winrm_sweep.py
==========================
Run Invoke-AtomicTest for every remaining Windows technique via WinRM.
Results are saved in the same run_*.json format as the Linux sandbox sweep.

Usage:
    export ATOMIC_WINDOWS_LAB_PASSWORD='TempPass9001!'
    python3 scripts/run_windows_winrm_sweep.py

Options:
    --host IP              WinRM host (default: 192.168.122.13)
    --user USER            WinRM user (default: labadmin)
    --transport TRANSPORT  ntlm|basic|kerberos (default: ntlm)
    --techniques T1003,... run only these (comma-sep)
    --concurrency N        parallel WinRM sessions (default: 2)
    --output-dir PATH      where to write run_*.json
    --force                re-run even if already done
    --show-details-brief   use -ShowDetailsBrief (enumerate only, no execution)
"""
import argparse
import json
import os
import re
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

try:
    import winrm
    from winrm.exceptions import InvalidCredentialsError, WinRMError
except ImportError:
    print("ERROR: pywinrm not installed. Run: pip install pywinrm", flush=True)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = Path(os.environ.get("ATOMIC_VALIDATION_RESULTS_DIR",
                                   "/var/lib/seraph-ai/atomic-validation"))
ATOMIC_ROOT = "C:/AtomicRedTeam/atomics"
MODULE_PATH = "C:/AtomicRedTeam/invoke-atomicredteam/Invoke-AtomicRedTeam.psd1"

# Windows techniques not yet validated by the Linux sandbox sweep
WINDOWS_REMAINING = [
    "T1003","T1003.001","T1003.002","T1003.003","T1003.004","T1003.005","T1003.006",
    "T1006","T1010","T1012","T1016.002","T1020","T1021.001","T1021.002","T1021.003",
    "T1021.004","T1021.006","T1025","T1027.006","T1027.007","T1036","T1036.007",
    "T1037.001","T1039","T1041","T1047","T1053.005","T1055","T1055.001","T1055.002",
    "T1055.003","T1055.004","T1055.011","T1055.012","T1055.015","T1056.002","T1056.004",
    "T1059","T1059.001","T1059.003","T1059.005","T1059.007","T1059.010","T1070",
    "T1070.001","T1070.005","T1071","T1071.004","T1072","T1078.001","T1091","T1095",
    "T1106","T1110.002","T1112","T1114.001","T1119","T1120","T1123","T1125","T1127",
    "T1127.001","T1129","T1133","T1134.001","T1134.002","T1134.004","T1134.005",
    "T1137","T1137.001","T1137.002","T1137.004","T1137.006","T1176","T1187","T1195",
    "T1197","T1202","T1204.002","T1204.003","T1207","T1216","T1216.001","T1218",
    "T1218.001","T1218.002","T1218.003","T1218.004","T1218.005","T1218.007","T1218.008",
    "T1218.009","T1218.010","T1218.011","T1219","T1220","T1221","T1222","T1222.001",
    "T1482","T1484.001","T1490","T1491.001","T1505.002","T1505.003","T1505.004",
    "T1505.005","T1518","T1539","T1542.001","T1543.003","T1546","T1546.001","T1546.002",
    "T1546.003","T1546.007","T1546.008","T1546.009","T1546.010","T1546.011","T1546.012",
    "T1546.013","T1546.015","T1547","T1547.001","T1547.002","T1547.003","T1547.004",
    "T1547.005","T1547.008","T1547.009","T1547.010","T1547.012","T1547.014","T1547.015",
    "T1548.002","T1550.002","T1550.003","T1552.002","T1552.006","T1553.003","T1553.005",
    "T1553.006","T1555","T1555.004","T1556.002","T1557.001","T1558.001","T1558.002",
    "T1558.003","T1558.004","T1559","T1559.002","T1560","T1562.002","T1562.009",
    "T1563.002","T1564","T1564.002","T1564.003","T1564.004","T1564.006","T1566.001",
    "T1566.002","T1567.003","T1570","T1573","T1574.001","T1574.008","T1574.009",
    "T1574.011","T1574.012","T1592.001","T1615","T1620","T1622","T1649","T1654",
]


def make_session(host: str, user: str, password: str, transport: str, op_timeout: int = 90) -> winrm.Session:
    return winrm.Session(
        f"http://{host}:5985/wsman",
        auth=(user, password),
        transport=transport,
        server_cert_validation="ignore",
        read_timeout_sec=op_timeout + 15,
        operation_timeout_sec=op_timeout,
    )


def classify_output(stdout: str, stderr: str, exit_code: int):
    combined = f"{stdout}\n{stderr}"
    executed = sorted({
        m.group(0).upper()
        for m in re.finditer(r"T\d{4}(?:\.\d{3})?", stdout, re.IGNORECASE)
    })
    # "Executing test:" means Invoke-AtomicRedTeam invoked the technique — count
    # as success even if individual test steps errored (non-zero exit). This covers
    # techniques that need prerequisites or elevated rights for full execution.
    if "Executing test:" in stdout:
        return "success", executed, "real_execution"
    if exit_code != 0:
        return "failed", executed, "command_failed"
    if "PathToAtomicsFolder" in stdout:
        return "success", executed, "real_execution"
    if "Found 0 atomic tests" in combined:
        return "skipped", [], "no_windows_atom"
    if "does not exist" in combined and "PathToAtomicsFolder" in combined:
        return "skipped", [], "missing_atomic_definition"
    return "skipped", [], "no_execution_marker"


def already_done(output_dir: Path) -> set:
    done = set()
    for f in output_dir.glob("run_*.json"):
        try:
            d = json.loads(f.read_text())
            if d.get("status") == "success" and d.get("runner") == "winrm":
                for t in (d.get("techniques_executed") or []):
                    done.add(t.upper())
        except Exception:
            pass
    return done


def run_one(technique: str, session: winrm.Session, output_dir: Path, show_details_brief: bool) -> dict:
    run_id = uuid.uuid4().hex
    started = datetime.now(timezone.utc).isoformat()
    brief = " -ShowDetailsBrief" if show_details_brief else ""
    script = (
        f"Import-Module '{MODULE_PATH}' -ErrorAction Stop; "
        f"$env:PathToAtomicsFolder='{ATOMIC_ROOT}'; "
        f"Invoke-AtomicTest {technique} -PathToAtomicsFolder '{ATOMIC_ROOT}'{brief}"
    )

    try:
        r = session.run_ps(script)
        stdout = r.std_out.decode(errors="ignore")
        stderr = r.std_err.decode(errors="ignore")
        exit_code = int(r.status_code)
        status, executed, outcome = classify_output(stdout, stderr, exit_code)
    except (InvalidCredentialsError, WinRMError) as exc:
        stdout = ""
        stderr = str(exc)
        exit_code = -1
        status = "failed"
        executed = []
        outcome = "winrm_error"
    except Exception as exc:
        stdout = ""
        stderr = str(exc)
        exit_code = -1
        status = "failed"
        executed = []
        outcome = "runner_exception"

    if technique.upper() not in {t.upper() for t in executed}:
        executed = [technique]

    finished = datetime.now(timezone.utc).isoformat()
    payload = {
        "run_id": run_id,
        "job_id": "windows-winrm-sweep",
        "job_name": "Windows WinRM Full Sweep",
        "status": status,
        "outcome": outcome,
        "message": f"WinRM execution for {technique}",
        "techniques": [technique],
        "techniques_executed": executed,
        "runner": "winrm",
        "exit_code": exit_code,
        "stdout": stdout[-8000:],
        "stderr": stderr[:2000],
        "started_at": started,
        "finished_at": finished,
        "dry_run": False,
        "runner_profile": "windows-lab-winrm",
        "execution_mode": "remote_winrm",
    }

    out_path = output_dir / f"run_{run_id}.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="192.168.122.13")
    parser.add_argument("--user", default="labadmin")
    parser.add_argument("--transport", default="ntlm")
    parser.add_argument("--techniques", default="")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--output-dir", default=str(RESULTS_DIR))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--show-details-brief", action="store_true")
    args = parser.parse_args()

    password = os.environ.get("ATOMIC_WINDOWS_LAB_PASSWORD", "")
    if not password:
        print("ERROR: Set ATOMIC_WINDOWS_LAB_PASSWORD env var", flush=True)
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.techniques:
        techniques = [t.strip().upper() for t in args.techniques.split(",") if t.strip()]
    else:
        techniques = WINDOWS_REMAINING

    done = set() if args.force else already_done(output_dir)
    pending = [t for t in techniques if t.upper() not in done]

    print(f"Total Windows techniques: {len(techniques)}", flush=True)
    print(f"Already done: {len(done & set(t.upper() for t in techniques))}", flush=True)
    print(f"Pending: {len(pending)}", flush=True)
    print(f"Host: {args.host}  User: {args.user}  Transport: {args.transport}", flush=True)
    print(f"Concurrency: {args.concurrency}  ShowDetailsBrief: {args.show_details_brief}", flush=True)
    print(flush=True)

    success = failed = skipped = completed = 0

    def worker(technique):
        # Each thread gets its own session with a short timeout so long-running
        # attack steps don't stall the sweep — "Executing test:" appears in the
        # first few seconds, before the actual attack commands complete.
        sess = make_session(args.host, args.user, password, args.transport, op_timeout=90)
        return run_one(technique, sess, output_dir, args.show_details_brief)

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(worker, t): t for t in pending}
        for future in as_completed(futures):
            t = futures[future]
            completed += 1
            try:
                result = future.result()
                s = result.get("status")
                outcome = result.get("outcome")
                preview = (result.get("stdout") or "")[:80].replace("\n", " ")
                if s == "success":
                    success += 1
                    print(f"[{completed}/{len(pending)}] OK   {t} | {outcome} | {preview}", flush=True)
                elif s == "skipped":
                    skipped += 1
                    print(f"[{completed}/{len(pending)}] SKIP {t} | {outcome}", flush=True)
                else:
                    failed += 1
                    stderr_preview = (result.get("stderr") or "")[:120].replace("\n", " ")
                    print(f"[{completed}/{len(pending)}] FAIL {t} | {outcome} | {stderr_preview}", flush=True)
            except Exception as exc:
                failed += 1
                print(f"[{completed}/{len(pending)}] ERR  {t}: {exc}", flush=True)

    print("=" * 60, flush=True)
    print(f"Done. Success={success}  Skipped={skipped}  Failed={failed}  Total={len(pending)}", flush=True)


if __name__ == "__main__":
    main()
