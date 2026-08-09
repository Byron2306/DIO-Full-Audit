#!/usr/bin/env python3
"""Force ARDA's live runtime state into audit during early boot."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT / "arda_os") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "arda_os"))

from backend.services.os_enforcement_service import OsEnforcementService  # noqa: E402


OUTPUT_PATH = Path("/var/lib/arda/postboot/boot-audit-reset.json")


def main() -> int:
    os.environ.setdefault("ARDA_SOVEREIGN_MODE", "1")
    os.environ["ARDA_ENFORCEMENT_MODE"] = OsEnforcementService.ENFORCEMENT_MODE_AUDIT
    service = OsEnforcementService()
    try:
        before = service.get_status()
        applied_mode = service._project_state_mode(OsEnforcementService.ENFORCEMENT_MODE_AUDIT)
        after = service.get_status()
        payload = {
            "ok": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "before": {
                "arm_mode": before.get("arm_mode"),
                "enforcement_mode": before.get("enforcement_mode"),
                "is_authoritative": before.get("is_authoritative"),
            },
            "after": {
                "arm_mode": after.get("arm_mode"),
                "enforcement_mode": after.get("enforcement_mode"),
                "is_authoritative": after.get("is_authoritative"),
            },
            "applied_mode": applied_mode,
        }
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    finally:
        service.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
