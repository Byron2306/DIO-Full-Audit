#!/usr/bin/env python3
"""
Inspect Arda veto-oriented forensic records from logs, status snapshots, and audit trails.
"""

import argparse
import json
import os
import sys
from pathlib import Path


DEFAULT_STATUS_SNAPSHOT = "/var/log/arda/status_snapshot.json"
DEFAULT_EGRESS_LEDGER = "/var/log/arda/accountability_ledger.jsonl"
DEFAULT_AUDIT_LOG = "/var/log/audit/audit.log"


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.os_enforcement_service import OsEnforcementService  # noqa: E402


def _read_json(path: str):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _tail_lines(path: str, limit: int):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        lines = handle.readlines()
    return [line.rstrip("\n") for line in lines[-limit:]]


def _extract_veto_lines(lines):
    needles = ("veto", "deny", "blocked", "red-line", "redline")
    lowered = []
    for line in lines:
        if any(needle in line.lower() for needle in needles):
            lowered.append(line)
    return lowered


def main() -> int:
    parser = argparse.ArgumentParser(description="Show Arda veto and deny forensic records")
    parser.add_argument("--status-snapshot", default=DEFAULT_STATUS_SNAPSHOT)
    parser.add_argument("--egress-ledger", default=DEFAULT_EGRESS_LEDGER)
    parser.add_argument("--audit-log", default=DEFAULT_AUDIT_LOG)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    status_snapshot = _read_json(args.status_snapshot)
    egress_lines = _tail_lines(args.egress_ledger, args.limit)
    audit_lines = _tail_lines(args.audit_log, args.limit * 10)
    veto_audit_lines = _extract_veto_lines(audit_lines)[-args.limit:]
    service = OsEnforcementService(arm=False)
    try:
        live_status = service.get_status()
    finally:
        service.shutdown()
    live_last_deny = live_status.get("last_deny_event")

    payload = {
        "cwd": os.getcwd(),
        "status_snapshot_path": os.path.abspath(args.status_snapshot),
        "egress_ledger_path": os.path.abspath(args.egress_ledger),
        "audit_log_path": os.path.abspath(args.audit_log),
        "deny_count": ((status_snapshot or {}).get("status") or {}).get("deny_count"),
        "loader_last_error": ((status_snapshot or {}).get("status") or {}).get("loader_last_error"),
        "status_last_error": ((status_snapshot or {}).get("status") or {}).get("last_error"),
        "live_last_deny_event": live_last_deny,
        "recent_egress_events": egress_lines,
        "recent_audit_veto_lines": veto_audit_lines,
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    lines = [
        "ARDA VETO LOG",
        f"status_snapshot_path: {payload['status_snapshot_path']}",
        f"egress_ledger_path: {payload['egress_ledger_path']}",
        f"audit_log_path: {payload['audit_log_path']}",
        f"deny_count: {payload['deny_count']}",
        f"loader_last_error: {payload['loader_last_error'] or '(none)'}",
        f"status_last_error: {payload['status_last_error'] or '(none)'}",
        (
            "live_last_deny_event: "
            f"reason={live_last_deny.get('deny_reason')} "
            f"mode={live_last_deny.get('enforcement_mode')} "
            f"generation={live_last_deny.get('active_generation')} "
            f"cgroup_id={live_last_deny.get('cgroup_id')} "
            f"inode={live_last_deny.get('inode')} "
            f"dev={live_last_deny.get('dev')}"
            if live_last_deny
            else "live_last_deny_event: (none)"
        ),
        "",
        "recent_egress_events:",
    ]
    if egress_lines:
        lines.extend(f"  {line}" for line in egress_lines)
    else:
        lines.append("  (none)")
    lines.append("")
    lines.append("recent_audit_veto_lines:")
    if veto_audit_lines:
        lines.extend(f"  {line}" for line in veto_audit_lines)
    else:
        lines.append("  (none)")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
