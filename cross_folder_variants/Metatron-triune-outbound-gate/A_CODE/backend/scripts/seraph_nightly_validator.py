#!/usr/bin/env python3
"""Nightly validator for Seraph/Arda containment.

Runs gauntlets repeatedly and appends compact results to JSONL history.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _run(cmd: List[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)


def _read_latest_verdict(report_path: Path) -> Dict[str, Any]:
    if not report_path.exists():
        return {"available": False}

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    events = payload.get("events") or []
    verdicts = [e for e in events if e.get("event_type") == "verdict"]
    if not verdicts:
        return {"available": False}

    v = verdicts[-1]
    return {
        "available": True,
        "status": v.get("status"),
        "details": v.get("details") or {},
    }


def _append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def run(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    py = str(repo_root / ".venv" / "bin" / "python")
    gauntlet = str(repo_root / "backend" / "scripts" / "e2e_dagor_dagorlach_gauntlet.py")
    report_path = repo_root / "backend" / "scripts" / "telemetry_logs" / "DAGOR_DAGORLACH_ULTIMATE_GAUNTLET_report.json"
    history_path = repo_root / "backend" / "scripts" / "telemetry_logs" / "seraph_nightly_history.jsonl"

    iterations = max(1, args.iterations)
    all_records: List[Dict[str, Any]] = []

    for idx in range(iterations):
        run_id = idx + 1
        start = datetime.now(timezone.utc).isoformat()

        std_cmd = [py, gauntlet, "--aab-replay-limit", str(args.aab_replay_limit)]
        std_proc = _run(std_cmd, repo_root)
        std_verdict = _read_latest_verdict(report_path)

        live_cmd = [
            py,
            gauntlet,
            "--live-harness",
            "--live-agent-class",
            args.live_agent_class,
            "--aab-replay-limit",
            str(args.aab_replay_limit),
        ]
        live_proc = _run(live_cmd, repo_root)
        live_verdict = _read_latest_verdict(report_path)

        record: Dict[str, Any] = {
            "timestamp": start,
            "iteration": run_id,
            "standard": {
                "exit_code": std_proc.returncode,
                "verdict": std_verdict,
            },
            "live": {
                "exit_code": live_proc.returncode,
                "verdict": live_verdict,
            },
        }

        _append_jsonl(history_path, record)
        all_records.append(record)

    failed = 0
    for r in all_records:
        for mode in ("standard", "live"):
            mode_data = r.get(mode) or {}
            if int(mode_data.get("exit_code", 1)) != 0:
                failed += 1
                continue
            status = ((mode_data.get("verdict") or {}).get("status") or "").lower()
            if status != "pass":
                failed += 1

    summary = {
        "iterations": iterations,
        "failed_runs": failed,
        "history_file": str(history_path),
    }
    print(json.dumps(summary, indent=2))
    return 1 if failed > 0 else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nightly Seraph/Arda validator")
    parser.add_argument("--repo-root", default=".", help="Repository root path")
    parser.add_argument("--iterations", type=int, default=1, help="How many nightly cycles to execute now")
    parser.add_argument("--aab-replay-limit", type=int, default=10, help="Replay limit for gauntlet runs")
    parser.add_argument("--live-agent-class", default="jailbroken", help="Agent class for live harness")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
