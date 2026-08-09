#!/usr/bin/env python3
"""
harvest_unified_agent_monitors.py
===================================
Harvests real detection evidence from the Seraph unified agent's 24 running
monitors and converts them into run_*.json evidence records compatible with
import_gha_artifacts.py.

How it works:
  1. POSTs /api/agent/start to ensure monitoring is active
  2. Waits for monitors to complete initial scans
  3. GETs /api/dashboard to collect threat_history + telemetry
  4. Groups detections by technique, one run_*.json per technique
  5. Writes summary JSON

Usage:
    python3 scripts/harvest_unified_agent_monitors.py
    python3 scripts/harvest_unified_agent_monitors.py --out-dir artifacts/evidence/unified_agent
    python3 scripts/harvest_unified_agent_monitors.py --container seraph-unified-agent --wait 30
    python3 scripts/harvest_unified_agent_monitors.py --dry-run
"""

import argparse
import hashlib
import json
import subprocess
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


CONTAINER = "seraph-unified-agent"
AGENT_URL = "http://localhost:5000"
DEFAULT_OUT = "artifacts/evidence/unified_agent"
WAIT_SECS = 25  # seconds to wait for monitors to scan after start


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _curl(container: str, method: str, path: str, body: dict | None = None) -> dict | list | None:
    """Run curl inside the container and return parsed JSON."""
    cmd = ["docker", "exec", container, "curl", "-s", "--max-time", "30"]
    if method == "POST":
        cmd += ["-X", "POST", "-H", "Content-Type: application/json"]
        if body:
            cmd += ["-d", json.dumps(body)]
    cmd.append(f"{AGENT_URL}{path}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def ensure_monitoring(container: str) -> bool:
    status = _curl(container, "GET", "/api/status")
    if not status:
        print("[ERROR] Cannot reach unified agent dashboard at port 5000", flush=True)
        return False
    if status.get("monitoring_active"):
        print(f"[OK] Monitoring already active ({status.get('monolithic_monitor_count', '?')} monitors)", flush=True)
        return True
    print("[INFO] Starting monitoring...", flush=True)
    resp = _curl(container, "POST", "/api/agent/start")
    if resp and resp.get("status") in ("starting", "already_running"):
        print("[OK] Monitoring started", flush=True)
        return True
    print(f"[WARN] Unexpected start response: {resp}", flush=True)
    return False


def collect_threats(container: str) -> list[dict]:
    dashboard = _curl(container, "GET", "/api/dashboard")
    if not dashboard:
        return []
    return dashboard.get("threats", [])


def collect_monitor_stats(container: str) -> dict:
    monitors = _curl(container, "GET", "/api/monitors")
    if not monitors:
        return {}
    return monitors.get("monitors", {})


def build_run_record(
    techniques: list[str],
    threats: list[dict],
    monitor_stats: dict,
    collected_at: str,
) -> dict:
    run_id = uuid.uuid4().hex
    techs_str = ", ".join(techniques)
    sources = sorted({t.get("source", "unknown") for t in threats})

    threat_lines = []
    for t in threats:
        threat_lines.append(
            f"[{t.get('severity','?').upper()}] {t.get('title','unknown')} "
            f"(source={t.get('source','?')} threat_id={t.get('threat_id','?')} "
            f"mitre={t.get('mitre_techniques',[])})"
        )
    stdout_text = (
        f"=== Unified Agent Monitor Detections: {techs_str} ===\n"
        f"Collected at: {collected_at}\n"
        f"Container: {CONTAINER}\n"
        f"Monitors fired: {', '.join(sources)}\n\n"
        + "\n".join(threat_lines)
    )

    return {
        "run_id": run_id,
        "job_id": f"unified-agent-monitor-{'_'.join(techniques[:2])}",
        "job_name": f"Unified Agent Monitors — {techs_str}",
        "techniques": techniques,
        "techniques_executed": techniques,
        "started_at": collected_at,
        "ended_at": collected_at,
        "generated_at": collected_at,
        "generated_by": "harvest_unified_agent_monitors.py",
        "runner": "seraph_unified_agent_local",
        "execution_mode": "unified_agent_live_detection",
        "outcome": "real_execution",
        "status": "success",
        "exit_code": 0,
        "message": (
            f"Unified agent monitors detected {len(threats)} threat(s) "
            f"across {len(techniques)} technique(s): {techs_str}. "
            f"Sources: {', '.join(sources)}."
        ),
        "stdout": stdout_text,
        "stderr": "",
        "stdout_sha256": hashlib.sha256(stdout_text.encode()).hexdigest(),
        "unified_agent_evidence": {
            "monitor_count": len(monitor_stats),
            "threat_count": len(threats),
            "sources": sources,
            "threats": threats,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Harvest unified agent monitor detections as evidence")
    parser.add_argument("--container", default=CONTAINER, help="Docker container name")
    parser.add_argument("--out-dir", default=DEFAULT_OUT, help="Output directory for run_*.json files")
    parser.add_argument("--wait", type=int, default=WAIT_SECS, help="Seconds to wait for monitors to scan")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no files written")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    collected_at = _iso_now()

    print(f"=== Seraph Unified Agent Monitor Harvester ===", flush=True)
    print(f"Container: {args.container}", flush=True)
    print(f"Output:    {out_dir}", flush=True)
    print(f"Dry-run:   {args.dry_run}", flush=True)
    print(flush=True)

    # Step 1: Ensure monitoring is active
    if not ensure_monitoring(args.container):
        print("[ERROR] Could not start monitoring. Is seraph-unified-agent running?", flush=True)
        return 1

    # Step 2: Wait for scans
    print(f"[INFO] Waiting {args.wait}s for monitor scans to complete...", flush=True)
    for i in range(args.wait, 0, -5):
        time.sleep(5)
        threats = collect_threats(args.container)
        print(f"  ...{i-5}s remaining, {len(threats)} threats so far", flush=True)
        if i <= 5:
            break

    # Step 3: Collect threats and stats
    threats = collect_threats(args.container)
    monitor_stats = collect_monitor_stats(args.container)
    print(f"\n[OK] Collected {len(threats)} threats from {len(monitor_stats)} monitors", flush=True)

    if not threats:
        print("[WARN] No threats detected — no run files to write", flush=True)
        return 0

    # Step 4: Group by technique
    tech_threats: dict[str, list[dict]] = defaultdict(list)
    for t in threats:
        for tech in t.get("mitre_techniques", []):
            tech_threats[tech].append(t)

    print(f"\nTechniques detected ({len(tech_threats)}):", flush=True)
    for tech, tlist in sorted(tech_threats.items()):
        sources = {t.get("source", "?") for t in tlist}
        print(f"  {tech}: {len(tlist)} detection(s) from {sorted(sources)}", flush=True)

    # Step 5: Write run files (one per technique)
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    run_files = []
    for tech, tlist in sorted(tech_threats.items()):
        record = build_run_record([tech], tlist, monitor_stats, collected_at)
        filename = f"run_{record['run_id']}.json"
        if not args.dry_run:
            out_path = out_dir / filename
            out_path.write_text(json.dumps(record, indent=2, default=str))
            run_files.append(str(out_path))
            print(f"  [WRITTEN] {out_path}", flush=True)
        else:
            print(f"  [DRY-RUN] Would write {out_dir / filename} for {tech}", flush=True)

    # Step 6: Write summary
    summary = {
        "schema": "unified_agent_harvest_summary.v1",
        "harvested_at": collected_at,
        "container": args.container,
        "dry_run": args.dry_run,
        "monitor_count": len(monitor_stats),
        "threat_count": len(threats),
        "techniques_covered": sorted(tech_threats.keys()),
        "run_records_written": len(run_files),
        "run_files": run_files,
    }
    if not args.dry_run:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        summary_path = out_dir / f"harvest_summary_{ts}.json"
        summary_path.write_text(json.dumps(summary, indent=2))
        print(f"\n[OK] Summary: {summary_path}", flush=True)

    print(f"\n=== Done: {len(run_files)} run files written ===", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
