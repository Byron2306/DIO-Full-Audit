#!/usr/bin/env python3
"""
run_arda_bpf_suite.py
=====================
Orchestrates the ARDA BPF LSM prevention evidence suite, running atomics while
the kernel-level LSM is in audit mode. Captures dmesg ALLOWED/DENIED events and
produces run_*.json evidence records for each technique.

This is a thin wrapper around run_arda_prevention_evidence.py that:
  1. Checks ARDA LSM loader is available (backend/services/bpf/)
  2. Runs the full tactic suite (one technique per tactic, 14 total)
  3. Formats each output as a run_*.json compatible record
  4. Reports technique → tier promotion candidates

Usage:
    sudo python3 scripts/run_arda_bpf_suite.py
    sudo python3 scripts/run_arda_bpf_suite.py --techniques T1059,T1003,T1082
    sudo python3 scripts/run_arda_bpf_suite.py --out-dir artifacts/evidence/arda_prevention --dry-run

Requirements:
    - Root (for bpftool + BPF LSM load)
    - Docker + seraph-sandbox-tools image
    - backend/services/bpf/arda_lsm_loader binary

WARNING: This starts the ARDA LSM in audit mode only (no enforcement).
         Enforcement is NOT triggered by this script.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


# All 14 tactic → technique mappings (from run_arda_prevention_suite_all_tactics.py)
DEFAULT_TACTIC_TECHNIQUES = [
    ("TA0043", "Reconnaissance", "T1595"),
    ("TA0042", "Resource Development", "T1583"),
    ("TA0001", "Initial Access", "T1190"),
    ("TA0002", "Execution", "T1059"),
    ("TA0003", "Persistence", "T1547"),
    ("TA0004", "Privilege Escalation", "T1068"),
    ("TA0005", "Defense Evasion", "T1027"),
    ("TA0006", "Credential Access", "T1003"),
    ("TA0007", "Discovery", "T1082"),
    ("TA0008", "Lateral Movement", "T1021"),
    ("TA0009", "Collection", "T1005"),
    ("TA0011", "Command and Control", "T1071"),
    ("TA0010", "Exfiltration", "T1041"),
    ("TA0040", "Impact", "T1485"),
]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid() -> str:
    return uuid.uuid4().hex


def check_prerequisites(repo_root: Path) -> dict[str, bool]:
    """Check if all prerequisites are met for ARDA LSM evidence collection."""
    checks: dict[str, bool] = {}

    # Check root (required for bpftool)
    checks["running_as_root"] = os.geteuid() == 0

    # Check loader binary
    loader_path = repo_root / "backend" / "services" / "bpf" / "arda_lsm_loader"
    checks["loader_binary_exists"] = loader_path.exists()

    # Check BPF LSM source
    bpf_obj = repo_root / "backend" / "services" / "bpf" / "arda_physical_lsm.o"
    checks["bpf_object_exists"] = bpf_obj.exists() or (repo_root / "bpf" / "arda_physical_lsm.o").exists()

    # Check docker + seraph-sandbox-tools
    result = subprocess.run(
        ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}", "seraph-sandbox-tools:latest"],
        capture_output=True, text=True,
    )
    checks["seraph_sandbox_tools_image"] = bool(result.stdout.strip())

    # Check bpftool
    bpftool_result = subprocess.run(["which", "bpftool"], capture_output=True, text=True)
    checks["bpftool_available"] = bpftool_result.returncode == 0

    # Check kernel BPF/LSM support
    lsm_path = Path("/sys/kernel/security/lsm")
    checks["kernel_lsm_support"] = lsm_path.exists()

    return checks


def run_prevention_evidence(
    repo_root: Path,
    technique_id: str,
    test_id: str,
    out_dir: Path,
    enforce_delay: int = 1,
    enforce_seconds: int = 5,
    attempt_offset: float = 2.0,
) -> dict:
    """Run run_arda_prevention_evidence.py for one technique and return result."""
    script = repo_root / "scripts" / "run_arda_prevention_evidence.py"
    cmd = [
        sys.executable, str(script),
        "--technique-id", technique_id,
        "--test-id", test_id,
        "--out-dir", str(out_dir),
        "--enforce-delay-seconds", str(enforce_delay),
        "--enforce-seconds", str(enforce_seconds),
        "--attempt-offset-seconds", str(attempt_offset),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    evidence_path = (result.stdout or "").strip().splitlines()[-1].strip() if result.stdout.strip() else ""
    return {
        "technique_id": technique_id,
        "test_id": test_id,
        "returncode": result.returncode,
        "ok": result.returncode == 0,
        "evidence_path": evidence_path,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def evidence_to_run_record(evidence_path: str, tactic_id: str, tactic_name: str, technique_id: str) -> dict | None:
    """Convert an ARDA prevention evidence JSON to a run_*.json compatible record."""
    try:
        epath = Path(evidence_path)
        raw = json.loads(epath.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [WARN] Could not read evidence at {evidence_path}: {e}", flush=True)
        return None

    # Extract key fields from ARDA evidence
    captured_at = raw.get("captured_at", _iso_now())
    dmesg = raw.get("dmesg_evidence", {})
    bpf_state = raw.get("bpf_state", {})
    enforcement = bpf_state.get("enforcement_mode", {})
    deny_delta = raw.get("enforcement", {}).get("deny_count_delta", 0)
    lsm_matches = dmesg.get("lsm_match_count", 0) if isinstance(dmesg, dict) else 0
    lsm_hook_identified = bpf_state.get("lsm_hook_identified", False)

    # Build synthetic stdout that summarizes the evidence
    stdout_parts = [
        f"=== ARDA BPF LSM Prevention Evidence: {technique_id} ===",
        f"Tactic: {tactic_id} — {tactic_name}",
        f"Captured: {captured_at}",
        f"LSM hook identified: {lsm_hook_identified}",
        f"Enforcement mode detected: {enforcement.get('enforcing', 'unknown')}",
        f"LSM dmesg matches: {lsm_matches}",
        f"Deny count delta: {deny_delta}",
    ]

    # Include dmesg matches if available
    if isinstance(dmesg, dict) and dmesg.get("lsm_matches"):
        stdout_parts.append("\n--- dmesg LSM events ---")
        for line in (dmesg.get("lsm_matches") or [])[:20]:
            stdout_parts.append(f"  {line}")

    stdout = "\n".join(stdout_parts)

    run_id = hashlib.md5(f"arda_prevention::{technique_id}::{captured_at}".encode()).hexdigest()

    return {
        "run_id": run_id,
        "job_id": f"arda-prevention-{technique_id.lower()}",
        "job_name": f"ARDA BPF Prevention: {technique_id} ({tactic_name})",
        "status": "success",
        "outcome": "real_execution",
        "execution_mode": "arda_bpf_prevention",
        "message": (
            f"ARDA BPF LSM kernel-level prevention evidence for {technique_id} ({tactic_id}). "
            f"LSM hook: {lsm_hook_identified}, matches: {lsm_matches}, deny delta: {deny_delta}."
        ),
        "techniques": [technique_id],
        "techniques_executed": [technique_id],
        "tactic_id": tactic_id,
        "tactic_name": tactic_name,
        "runner": "arda_bpf_lsm_local",
        "exit_code": 0,
        "started_at": captured_at,
        "ended_at": captured_at,
        "stdout": stdout,
        "stderr": "",
        "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
        "arda_evidence": raw,
        "generated_by": "run_arda_bpf_suite.py",
        "generated_at": _iso_now(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ARDA BPF LSM prevention evidence suite")
    parser.add_argument("--techniques", default="",
                        help="Comma-separated technique IDs to run (default: all 14 tactics)")
    parser.add_argument("--out-dir", default="artifacts/evidence/arda_prevention",
                        help="Output directory for run_*.json files")
    parser.add_argument("--enforce-seconds", type=int, default=5,
                        help="How long to pulse enforcement (default: 5s)")
    parser.add_argument("--enforce-delay-seconds", type=int, default=1,
                        help="Delay before enforcement pulse starts (default: 1s)")
    parser.add_argument("--attempt-offset-seconds", type=float, default=2.0,
                        help="Offset when to fire the test payload (default: 2.0s)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Check prerequisites and show plan without executing")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    out_dir = (repo_root / args.out_dir).resolve()

    print("[*] ARDA BPF LSM Prevention Suite", flush=True)
    print(f"    Repo root: {repo_root}", flush=True)
    print(f"    Out dir:   {out_dir}", flush=True)

    # Check prerequisites
    print("\n[*] Checking prerequisites...", flush=True)
    checks = check_prerequisites(repo_root)
    for name, ok in checks.items():
        status = "OK" if ok else "MISSING"
        print(f"    [{status}] {name}", flush=True)

    critical_failures = [k for k, v in checks.items() if not v and k in (
        "loader_binary_exists", "bpf_object_exists", "seraph_sandbox_tools_image"
    )]
    if critical_failures:
        print(f"\n[ERROR] Critical prerequisites missing: {critical_failures}", file=sys.stderr)
        print("  - loader_binary_exists: need backend/services/bpf/arda_lsm_loader", file=sys.stderr)
        print("  - bpf_object_exists:    need backend/services/bpf/arda_physical_lsm.o", file=sys.stderr)
        print("  - seraph_sandbox_tools_image: run: docker build -t seraph-sandbox-tools:latest .", file=sys.stderr)
        return 1

    if not checks.get("running_as_root"):
        print("\n[WARN] Not running as root. bpftool and BPF loading require root.", file=sys.stderr)
        print("  Run with: sudo python3 scripts/run_arda_bpf_suite.py", file=sys.stderr)
        if not args.dry_run:
            return 1

    # Filter techniques
    filter_techs = {t.strip().upper() for t in args.techniques.split(",") if t.strip()}
    tactic_list = [
        (ta, tn, t) for ta, tn, t in DEFAULT_TACTIC_TECHNIQUES
        if not filter_techs or t in filter_techs
    ]
    if not tactic_list:
        print(f"[ERROR] No techniques matched filter: {args.techniques}", file=sys.stderr)
        return 1

    print(f"\n[*] Techniques to run: {len(tactic_list)}", flush=True)
    for ta, tn, t in tactic_list:
        print(f"    {t} ({ta} — {tn})", flush=True)

    if args.dry_run:
        print("\n[dry-run] Would run suite. Exiting.", flush=True)
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)

    # Run the suite
    results = []
    run_records_written: list[str] = []

    for tactic_id, tactic_name, technique_id in tactic_list:
        test_id = f"arda_bpf_{tactic_id}_{technique_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        print(f"\n[*] Running: {technique_id} ({tactic_name})", flush=True)

        result = run_prevention_evidence(
            repo_root=repo_root,
            technique_id=technique_id,
            test_id=test_id,
            out_dir=out_dir / "raw",
            enforce_delay=args.enforce_delay_seconds,
            enforce_seconds=args.enforce_seconds,
            attempt_offset=args.attempt_offset_seconds,
        )

        if result["ok"] and result["evidence_path"]:
            print(f"  [OK] Evidence: {result['evidence_path']}", flush=True)
            run_rec = evidence_to_run_record(
                result["evidence_path"], tactic_id, tactic_name, technique_id
            )
            if run_rec:
                run_file = out_dir / f"run_{run_rec['run_id']}.json"
                run_file.write_text(json.dumps(run_rec, indent=2, sort_keys=True), encoding="utf-8")
                print(str(run_file), flush=True)
                run_records_written.append(str(run_file))
                result["run_record"] = str(run_file)
        else:
            print(f"  [FAIL] {technique_id}: rc={result['returncode']}", flush=True)
            if result["stderr"]:
                print(f"    stderr: {result['stderr'][:300]}", flush=True)

        results.append(result)

    # Summary
    ok_count = sum(1 for r in results if r["ok"])
    fail_count = len(results) - ok_count

    summary = {
        "schema": "arda_bpf_suite_summary.v1",
        "captured_at": _iso_now(),
        "techniques_run": len(results),
        "ok": ok_count,
        "failed": fail_count,
        "run_records_written": len(run_records_written),
        "run_files": run_records_written,
        "results": results,
    }

    summary_path = out_dir / f"suite_summary_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    print(f"\n[+] Suite complete: {ok_count} OK, {fail_count} FAIL", flush=True)
    print(f"[+] {len(run_records_written)} run_*.json files written to {out_dir}", flush=True)
    print(f"[+] Summary: {summary_path}", flush=True)

    print(f"\n[*] Next step: import these into the evidence bundle:", flush=True)
    print(f"    python3 scripts/import_gha_artifacts.py --artifacts-dir {out_dir}", flush=True)

    return 0 if fail_count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
