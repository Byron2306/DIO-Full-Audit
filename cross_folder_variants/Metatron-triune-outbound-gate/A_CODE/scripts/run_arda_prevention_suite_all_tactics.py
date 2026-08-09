#!/usr/bin/env python3
"""
Run a small ARDA prevention evidence suite: one technique per tactic.

This wraps scripts/run_arda_prevention_evidence.py (which is already lockout-safe
because it always disables enforcement and detaches the loader container).
"""

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


TACTIC_TECHNIQUES = [
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


def _run(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--enforce-delay-seconds", type=int, default=1)
    parser.add_argument("--enforce-seconds", type=int, default=3)
    parser.add_argument("--attempt-offset-seconds", type=float, default=2.0)
    parser.add_argument("--out-dir", default="artifacts/evidence/arda_prevention")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    out_dir = (repo_root / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    for tactic_id, tactic_name, technique_id in TACTIC_TECHNIQUES:
        test_id = f"arda_suite_{tactic_id}_{technique_id}"
        proc = _run(
            [
                str(repo_root / "scripts" / "run_arda_prevention_evidence.py"),
                "--technique-id",
                technique_id,
                "--test-id",
                test_id,
                "--out-dir",
                str(out_dir),
                "--enforce-delay-seconds",
                str(args.enforce_delay_seconds),
                "--enforce-seconds",
                str(args.enforce_seconds),
                "--attempt-offset-seconds",
                str(args.attempt_offset_seconds),
            ]
        )
        if proc.returncode != 0:
            results.append(
                {
                    "tactic_id": tactic_id,
                    "tactic_name": tactic_name,
                    "technique_id": technique_id,
                    "ok": False,
                    "stderr": (proc.stderr or "").strip(),
                    "stdout": (proc.stdout or "").strip(),
                }
            )
            continue

        evidence_path = (proc.stdout or "").strip().splitlines()[-1].strip()
        row = {
            "tactic_id": tactic_id,
            "tactic_name": tactic_name,
            "technique_id": technique_id,
            "ok": True,
            "evidence_path": evidence_path,
        }
        # Add tactic metadata into the evidence JSON (non-breaking).
        try:
            p = Path(evidence_path)
            payload = json.loads(p.read_text(encoding="utf-8"))
            payload.setdefault("tactic_id", tactic_id)
            payload.setdefault("tactic_name", tactic_name)
            p.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        except Exception:
            pass

        results.append(row)
        print(evidence_path)

    summary_path = out_dir / f"arda_prevention_suite_summary_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    summary = {"schema": "arda_prevention_suite_summary.v1", "captured_at": _iso_now(), "results": results}
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(str(summary_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

