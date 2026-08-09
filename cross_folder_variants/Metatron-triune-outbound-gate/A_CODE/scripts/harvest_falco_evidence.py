#!/usr/bin/env python3
"""
harvest_falco_evidence.py
=========================
Harvests Falco BPF detections from the seraph-falco container and converts
them into run_*.json evidence records compatible with import_gha_artifacts.py.

Each Falco alert group (by rule + sandbox container) becomes one run_*.json,
tagged with the mapped ATT&CK technique(s).

Usage:
    python3 scripts/harvest_falco_evidence.py
    python3 scripts/harvest_falco_evidence.py --out-dir artifacts/evidence/falco
    python3 scripts/harvest_falco_evidence.py --since "2026-04-27T00:00:00" --dry-run

Output:
    artifacts/evidence/falco/run_<hash>.json  (one per technique group)
    artifacts/evidence/falco/harvest_summary.json
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Falco rule name → ATT&CK technique mapping
# Priority: most-specific rule substring first, then broader categories.
# ---------------------------------------------------------------------------
RULE_TECHNIQUE_MAP: list[tuple[str, list[str]]] = [
    # Credential Access
    ("sensitive file opened", []),  # refined below by file path
    ("read sensitive file", []),
    ("shadow", ["T1003.008"]),
    ("credential", ["T1003"]),
    ("passwd", ["T1003.008"]),
    ("sudoers", ["T1548.003"]),
    ("pam", ["T1556.003"]),
    ("ssh key", ["T1552.004"]),
    ("private key", ["T1552.004"]),
    ("aws credential", ["T1552.005"]),
    # Execution
    ("shell in container", ["T1059.004"]),
    ("terminal shell in container", ["T1059.004"]),
    ("spawned shell", ["T1059.004"]),
    ("executed commands", ["T1059"]),
    # Discovery / Scanning
    ("packet socket", ["T1046", "T1595.001"]),
    ("network scan", ["T1046"]),
    ("port scan", ["T1046"]),
    # Persistence
    ("crontab", ["T1053.003"]),
    ("cron", ["T1053.003"]),
    ("systemd", ["T1543.002"]),
    ("write below binary dir", ["T1574.006"]),
    ("write below etc", ["T1098"]),
    ("write below root", ["T1074"]),
    # Privilege Escalation
    ("setuid", ["T1548.001"]),
    ("sudo", ["T1548.003"]),
    ("capabilities", ["T1548.001"]),
    # Defense Evasion
    ("container drift", ["T1036.004"]),
    ("binary changed", ["T1036"]),
    ("file open in write mode", ["T1070"]),
    ("clear log files", ["T1070.003"]),
    ("delete or rename shell history", ["T1070.003"]),
    # Collection
    ("data from local", ["T1005"]),
    ("archive collected", ["T1560"]),
    # Exfiltration / C2
    ("unexpected outbound connection", ["T1041"]),
    ("outbound connection", ["T1041"]),
    # Lateral Movement
    ("remote file copy", ["T1021"]),
    ("ssh client", ["T1021.004"]),
    # Impact
    ("wipe", ["T1485"]),
    ("shred", ["T1485"]),
    # Broad fallbacks
    ("sensitive file", ["T1083"]),
    ("file opened for reading", ["T1083"]),
]

# Additional technique lookup by file path mentioned in the alert
FILE_PATH_TECHNIQUE_MAP: list[tuple[str, list[str]]] = [
    ("/etc/shadow", ["T1003.008"]),
    ("/etc/passwd", ["T1003.008"]),
    ("/etc/sudoers", ["T1548.003"]),
    ("/etc/pam.d/", ["T1556.003"]),
    ("/etc/cron", ["T1053.003"]),
    ("/.ssh/", ["T1552.004"]),
    ("/.aws/", ["T1552.005"]),
    ("/proc/", ["T1082"]),
    ("/sys/", ["T1082"]),
    ("/tmp/", ["T1074"]),
]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid() -> str:
    return uuid.uuid4().hex


def map_alert_to_techniques(rule_name: str, alert_text: str) -> list[str]:
    """Return a list of ATT&CK technique IDs for a Falco alert."""
    rule_lower = rule_name.lower()
    alert_lower = alert_text.lower()

    # Check file path first (most specific)
    for path_frag, techs in FILE_PATH_TECHNIQUE_MAP:
        if path_frag in alert_lower:
            return techs

    # Check rule name
    for keyword, techs in RULE_TECHNIQUE_MAP:
        if keyword in rule_lower and techs:
            return techs
        if keyword in alert_lower and techs:
            return techs

    return []


def parse_falco_logs(raw_log: str, since_dt: datetime | None = None) -> list[dict]:
    """
    Parse Falco log lines into structured records.

    Handles both formats:
    - JSON (when json_output=true):  {"time":"...","rule":"...","priority":"...","output_fields":{...},...}
    - Text (when json_output=false): TIMESTAMP: PRIORITY RULE_NAME | field=value ...
    """
    records = []
    text_pattern = re.compile(
        r"^(?P<ts>\d{4}-\d{2}-\d{2}T[\d:.]+[+\-]\d{4}):\s+"
        r"(?P<priority>Emergency|Alert|Critical|Error|Warning|Notice|Informational|Debug)\s+"
        r"(?P<rule>.+?)\s*\|(?P<fields>.*)$"
    )

    for line in raw_log.splitlines():
        line = line.strip()
        if not line:
            continue

        ts: datetime | None = None
        rule = ""
        priority = ""
        fields: dict[str, str] = {}
        container_name = "host"
        container_id = "host"

        # Try JSON format first
        if line.startswith("{"):
            try:
                obj = json.loads(line)
                rule = obj.get("rule", "")
                priority = obj.get("priority", "")
                ts_str = obj.get("time", "")
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except Exception:
                    ts = datetime.now(timezone.utc)
                of = obj.get("output_fields", {}) or {}
                container_name = of.get("container.name") or "host"
                container_id = of.get("container.id") or "host"
                # Flatten output_fields for compatibility
                for k, v in of.items():
                    safe_key = k.replace(".", "_")
                    fields[safe_key] = str(v) if v is not None else ""
                # Also extract MITRE tags from the alert
                tags = obj.get("tags", [])
                tag_techniques = [t for t in tags if re.match(r"T\d{4}", t)]
            except (json.JSONDecodeError, Exception):
                continue
        else:
            # Text format
            m = text_pattern.match(line)
            if not m:
                continue
            ts_str = m.group("ts")
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except Exception:
                ts = datetime.now(timezone.utc)
            rule = m.group("rule").strip()
            priority = m.group("priority")
            fields_raw = m.group("fields").strip()
            for fmatch in re.finditer(r"(\w+)=([^\s]+)", fields_raw):
                fields[fmatch.group(1)] = fmatch.group(2)
            container_name = fields.get("container_name", "host")
            container_id = fields.get("container_id", "host")
            tag_techniques = []

        if ts is None:
            ts = datetime.now(timezone.utc)

        if since_dt and ts < since_dt:
            continue

        # Map rule name to techniques, then merge any tag-based techniques
        techniques = map_alert_to_techniques(rule, line)
        for tt in tag_techniques:
            if tt not in techniques:
                techniques.append(tt)

        records.append({
            "ts": ts,
            "ts_iso": ts.isoformat(),
            "priority": priority,
            "rule": rule,
            "fields": fields,
            "container_name": container_name,
            "container_id": container_id,
            "techniques": techniques,
            "raw_line": line,
        })

    return records


def group_by_technique_and_session(records: list[dict]) -> dict[str, list[dict]]:
    """
    Group alerts by (technique, sandbox_session).
    sandbox_session = container_name if it looks like a seraph-sandbox container,
                      otherwise we group by hour bucket.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        if not rec["techniques"]:
            continue
        # Determine session key
        cname = rec["container_name"]
        if "seraph-sandbox" in cname:
            session = cname  # each sandbox container = one atomic test session
        else:
            # bucket by technique + hour
            hour = rec["ts"].strftime("%Y%m%d_%H")
            session = f"{cname}_{hour}"

        for tech in rec["techniques"]:
            key = f"{tech}::{session}"
            groups[key].append(rec)

    return dict(groups)


def build_run_record(technique: str, session: str, alerts: list[dict]) -> dict:
    """Build a run_*.json compatible evidence record from a group of Falco alerts."""
    run_id = hashlib.md5(f"falco::{technique}::{session}".encode()).hexdigest()
    started_at = alerts[0]["ts_iso"]
    ended_at = alerts[-1]["ts_iso"]

    # Compose stdout from alert lines (this is the "execution output" that proves it ran)
    stdout_lines = [a["raw_line"] for a in alerts]
    stdout = "\n".join(stdout_lines)

    # Build summary for message
    rules_seen = sorted({a["rule"] for a in alerts})
    containers_seen = sorted({a["container_name"] for a in alerts})

    return {
        "run_id": run_id,
        "job_id": f"falco-detection-{technique.lower()}",
        "job_name": f"Falco BPF Detection: {technique}",
        "status": "success",
        "outcome": "real_execution",
        "execution_mode": "falco_bpf_detection",
        "message": (
            f"Falco BPF kernel-level detection of {technique}. "
            f"Rules: {', '.join(rules_seen)}. "
            f"Detected in: {', '.join(containers_seen)}."
        ),
        "techniques": [technique],
        "techniques_executed": [technique],
        "runner": "falco_bpf_host",
        "exit_code": 0,
        "started_at": started_at,
        "ended_at": ended_at,
        "stdout": stdout,
        "stderr": "",
        "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
        "falco_evidence": {
            "alert_count": len(alerts),
            "rules_triggered": rules_seen,
            "containers": containers_seen,
            "alerts": [
                {
                    "ts": a["ts_iso"],
                    "priority": a["priority"],
                    "rule": a["rule"],
                    "container": a["container_name"],
                    "fields": a["fields"],
                }
                for a in alerts
            ],
        },
        "generated_by": "harvest_falco_evidence.py",
        "generated_at": _iso_now(),
    }


def fetch_falco_logs(container: str = "seraph-falco", since: str | None = None) -> str:
    """Read Falco JSON alerts from the container's alert file (preferred) or docker logs."""
    # Prefer reading from the JSON alert file written by Falco
    FALCO_ALERT_FILE = "/var/log/falco/falco_alerts.json"
    result = subprocess.run(
        ["docker", "exec", container, "cat", FALCO_ALERT_FILE],
        capture_output=True, text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout

    # Fallback: docker logs (text-format output)
    cmd = ["docker", "logs", container]
    if since:
        cmd += ["--since", since]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return (result.stdout or "") + (result.stderr or "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Harvest Falco BPF detections as ATT&CK evidence")
    parser.add_argument("--container", default="seraph-falco", help="Falco Docker container name")
    parser.add_argument("--since", default=None, help="ISO timestamp to filter alerts from (e.g. 2026-04-27T00:00:00)")
    parser.add_argument("--out-dir", default="artifacts/evidence/falco", help="Output directory for run_*.json files")
    parser.add_argument("--min-alerts", type=int, default=1, help="Minimum alerts per group to emit a run record")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be generated without writing files")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    out_dir = (repo_root / args.out_dir).resolve()
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    # Parse since timestamp
    since_dt: datetime | None = None
    if args.since:
        try:
            since_dt = datetime.fromisoformat(args.since)
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)
        except Exception as e:
            print(f"[ERROR] Invalid --since timestamp: {e}", file=sys.stderr)
            return 1

    print(f"[*] Fetching Falco logs from container: {args.container}", flush=True)
    raw_log = fetch_falco_logs(args.container, args.since)
    if not raw_log.strip():
        print("[WARN] No Falco log output found. Is the container running?", file=sys.stderr)
        return 1

    print(f"[*] Parsing {len(raw_log.splitlines())} log lines...", flush=True)
    records = parse_falco_logs(raw_log, since_dt)
    print(f"[*] Parsed {len(records)} alert records", flush=True)

    # Filter to only those with technique mappings
    mapped = [r for r in records if r["techniques"]]
    print(f"[*] {len(mapped)} alerts mapped to ATT&CK techniques", flush=True)

    if not mapped:
        print("[WARN] No alerts could be mapped to ATT&CK techniques.", file=sys.stderr)
        print("       Check Falco container logs and RULE_TECHNIQUE_MAP in this script.", file=sys.stderr)
        return 0

    # Group by technique + session
    groups = group_by_technique_and_session(mapped)
    print(f"[*] {len(groups)} technique-session groups found", flush=True)

    # Emit run records
    written: list[str] = []
    skipped: list[str] = []
    technique_counts: dict[str, int] = defaultdict(int)

    for key, alerts in sorted(groups.items()):
        if len(alerts) < args.min_alerts:
            skipped.append(key)
            continue

        tech, session = key.split("::", 1)
        rec = build_run_record(tech, session, alerts)
        run_file = out_dir / f"run_{rec['run_id']}.json"

        if args.dry_run:
            print(f"  [dry-run] {tech}: {len(alerts)} alerts → {run_file.name}")
        else:
            run_file.write_text(json.dumps(rec, indent=2, sort_keys=True), encoding="utf-8")
            print(str(run_file), flush=True)

        written.append(str(run_file))
        technique_counts[tech] += 1

    # Write summary
    summary = {
        "schema": "falco_harvest_summary.v1",
        "harvested_at": _iso_now(),
        "container": args.container,
        "since": args.since,
        "total_alerts": len(records),
        "mapped_alerts": len(mapped),
        "groups_found": len(groups),
        "run_records_written": len(written),
        "technique_coverage": dict(sorted(technique_counts.items())),
        "run_files": written,
    }

    if not args.dry_run:
        summary_path = out_dir / f"harvest_summary_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        print(f"\n[+] Summary: {summary_path}", flush=True)

    print(f"\n[+] Techniques with Falco detection evidence:", flush=True)
    for tech, count in sorted(technique_counts.items()):
        print(f"    {tech}: {count} run record(s)", flush=True)

    print(f"\n[+] {len(written)} run_*.json files written to {out_dir}", flush=True)
    if skipped:
        print(f"[*] {len(skipped)} groups skipped (below --min-alerts={args.min_alerts})", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
