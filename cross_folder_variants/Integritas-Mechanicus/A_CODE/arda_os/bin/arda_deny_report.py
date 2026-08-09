#!/usr/bin/env python3
"""Summarize current ARDA denial telemetry for operator review."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.os_enforcement_service import OsEnforcementService  # noqa: E402


def _classify_deny(status: dict, last_deny: dict | None) -> list[str]:
    hints: list[str] = []
    deny_count = int(status.get("deny_count") or 0)
    if deny_count >= 25:
        hints.append("high_deny_volume")
    if last_deny:
        if str(last_deny.get("deny_reason") or "").startswith("unknown_"):
            hints.append("unknown_kernel_reason_code")
        if str(last_deny.get("enforcement_mode") or "") == "fsverity_strict":
            hints.append("strict_mode_denial")
    if not hints:
        hints.append("no_anomaly_hints")
    return hints


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize ARDA deny telemetry")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    service = OsEnforcementService(arm=False)
    try:
        status = service.get_status()
    finally:
        service.shutdown()

    last_deny = status.get("last_deny_event")
    payload = {
        "schema_version": "arda.deny_report.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "deny_count": int(status.get("deny_count") or 0),
        "live_enforcement_mode": status.get("enforcement_mode"),
        "arm_mode": status.get("arm_mode"),
        "last_deny_event": last_deny,
        "classification_hints": _classify_deny(status, last_deny),
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("ARDA DENY REPORT")
        print(f"deny_count: {payload['deny_count']}")
        print(f"live_enforcement_mode: {payload['live_enforcement_mode']}")
        print(f"arm_mode: {payload['arm_mode']}")
        if last_deny:
            print(
                "last_deny_event: "
                f"reason={last_deny.get('deny_reason')} "
                f"mode={last_deny.get('enforcement_mode')} "
                f"generation={last_deny.get('active_generation')} "
                f"inode={last_deny.get('inode')} "
                f"dev={last_deny.get('dev')}"
            )
        print("classification_hints: " + ", ".join(payload["classification_hints"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
