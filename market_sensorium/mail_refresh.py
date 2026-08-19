from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .core import utc_now
from .mail_readiness import audit_mail_observation_readiness

COVERAGE_RELATIVE_PATH = Path("state/microsoft_graph/mail_observation_coverage.json")
DELTA_RELATIVE_PATH = Path("state/microsoft_graph/mail_delta.json")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def refresh_mail_ingress_with_coverage(root: Path) -> dict[str, Any]:
    """Refresh Graph ingress and establish prospective observation coverage.

    A successful initial delta snapshot establishes coverage *from that successful
    sync forward*. It does not prove historical no-reply before the coverage start.
    Subsequent successful delta pulls extend the same continuous observation window.
    """
    root = Path(root).resolve()
    script = root / "scripts" / "sync_outlook_mail.py"
    coverage_path = root / COVERAGE_RELATIVE_PATH
    delta_path = root / DELTA_RELATIVE_PATH

    readiness = audit_mail_observation_readiness(root, python_executable=sys.executable)
    if not readiness.get("ready_for_silent_pull"):
        return {
            "state": readiness.get("refresh_state") or "not_configured",
            "readiness": readiness,
            "coverage": {
                "state": "NOT_CONFIGURED_OR_NOT_YET_OBSERVED",
                "authority_created": False,
            },
            "authority_created": False,
        }

    prior_coverage = _read_json(coverage_path)
    prior_delta = _read_json(delta_path)
    started_at = utc_now()
    completed = subprocess.run(
        [sys.executable, str(script), "pull"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if completed.returncode != 0:
        return {
            "state": "failed",
            "returncode": completed.returncode,
            "error": (completed.stderr or completed.stdout)[-3000:],
            "readiness": readiness,
            "coverage": {
                **prior_coverage,
                "state": prior_coverage.get("state") or "NOT_CONTINUOUS",
                "last_failed_sync_at": utc_now(),
                "authority_created": False,
            },
            "authority_created": False,
        }
    try:
        receipt = json.loads(completed.stdout)
    except json.JSONDecodeError:
        receipt = {"stdout": completed.stdout[-3000:]}

    finished_at = utc_now()
    new_delta = _read_json(delta_path)
    delta_continuity = bool(new_delta.get("delta_link"))
    prior_continuous = (
        str(prior_coverage.get("state") or "").upper() == "CONTINUOUS"
        and bool(prior_coverage.get("continuous_from"))
        and bool(prior_delta.get("delta_link"))
    )
    continuous_from = str(prior_coverage.get("continuous_from")) if prior_continuous else finished_at
    coverage = {
        "schema": "dio.mail_observation_coverage.v1",
        "provider": "microsoft_graph",
        "mailbox_scope": "inbox",
        "state": "CONTINUOUS" if delta_continuity else "NOT_CONTINUOUS",
        "coverage_kind": "CONTINUOUS_INBOX_DELTA_FROM_FIRST_SUCCESSFUL_SYNC",
        "continuous_from": continuous_from if delta_continuity else None,
        "first_successful_sync_at": prior_coverage.get("first_successful_sync_at") or finished_at,
        "last_successful_sync_at": finished_at,
        "sync_started_at": started_at,
        "delta_continuity": delta_continuity,
        "historical_complete": False,
        "retroactive_no_reply_claim_allowed": False,
        "read_only_observation": True,
        "send_authority_created": False,
        "authority_created": False,
    }
    _write_json(coverage_path, coverage)
    return {
        "state": "refreshed",
        "receipt": receipt,
        "readiness": readiness,
        "coverage": coverage,
        "coverage_path": str(COVERAGE_RELATIVE_PATH),
        "authority_created": False,
        "external_effects": False,
    }
