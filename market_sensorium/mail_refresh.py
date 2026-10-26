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


def _run_pull(script: Path, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), "pull"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=180,
    )


def _pull_error(completed: subprocess.CompletedProcess[str]) -> str:
    return (completed.stderr or completed.stdout or "")[-3000:]


def _is_stale_delta_error(completed: subprocess.CompletedProcess[str]) -> bool:
    """Recognise a Graph delta cursor whose server-side sync generation is gone."""
    if completed.returncode == 0:
        return False
    text = (completed.stderr or completed.stdout or "").lower()
    return "syncstatenotfound" in text or (
        "failed (410)" in text and "sync state" in text and "generation" in text
    )


def _archive_stale_delta_state(delta_path: Path) -> str | None:
    """Preserve the obsolete cursor as evidence before starting a new delta epoch."""
    if not delta_path.is_file():
        return None
    stamp = utc_now().replace(":", "").replace("+", "_")
    archive = delta_path.with_name(f"{delta_path.stem}.stale-{stamp}{delta_path.suffix}")
    suffix = 1
    while archive.exists():
        archive = delta_path.with_name(
            f"{delta_path.stem}.stale-{stamp}-{suffix}{delta_path.suffix}"
        )
        suffix += 1
    delta_path.replace(archive)
    return str(archive)


def refresh_mail_ingress_with_coverage(root: Path) -> dict[str, Any]:
    """Refresh Graph ingress and establish prospective observation coverage.

    A successful initial delta snapshot establishes coverage *from that successful
    sync forward*. It does not prove historical no-reply before the coverage start.
    Subsequent successful delta pulls extend the same continuous observation window.

    If Microsoft rejects an old delta token with SyncStateNotFound/410, the obsolete
    local cursor is archived and one fresh baseline pull is attempted. That recovery
    starts a new observation epoch. Prior coverage is never silently bridged across
    the lost server-side sync generation.
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
    completed = _run_pull(script, root)

    delta_reset = False
    delta_reset_reason: str | None = None
    stale_delta_archive: str | None = None
    first_failure: str | None = None

    if completed.returncode != 0 and _is_stale_delta_error(completed):
        first_failure = _pull_error(completed)
        stale_delta_archive = _archive_stale_delta_state(delta_path)
        delta_reset = True
        delta_reset_reason = "GRAPH_SYNC_STATE_NOT_FOUND"
        completed = _run_pull(script, root)

    if completed.returncode != 0:
        return {
            "state": "failed_after_stale_delta_reset" if delta_reset else "failed",
            "returncode": completed.returncode,
            "error": _pull_error(completed),
            "readiness": readiness,
            "delta_recovery": {
                "attempted": delta_reset,
                "reason": delta_reset_reason,
                "stale_delta_archived_to": stale_delta_archive,
                "initial_error": first_failure,
                "recovered": False,
                "authority_created": False,
            },
            "coverage": {
                **prior_coverage,
                "state": "NOT_CONTINUOUS",
                "continuous_from": None,
                "last_failed_sync_at": utc_now(),
                "continuity_reset": delta_reset,
                "continuity_reset_reason": delta_reset_reason,
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
        not delta_reset
        and str(prior_coverage.get("state") or "").upper() == "CONTINUOUS"
        and bool(prior_coverage.get("continuous_from"))
        and bool(prior_delta.get("delta_link"))
    )
    continuous_from = str(prior_coverage.get("continuous_from")) if prior_continuous else finished_at
    coverage = {
        "schema": "dio.mail_observation_coverage.v1",
        "provider": "microsoft_graph",
        "mailbox_scope": "inbox",
        "state": "CONTINUOUS" if delta_continuity else "NOT_CONTINUOUS",
        "coverage_kind": "CONTINUOUS_INBOX_DELTA_FROM_CURRENT_SYNC_EPOCH",
        "continuous_from": continuous_from if delta_continuity else None,
        "coverage_epoch_started_at": continuous_from if delta_continuity else None,
        "first_successful_sync_at": prior_coverage.get("first_successful_sync_at") or finished_at,
        "last_successful_sync_at": finished_at,
        "sync_started_at": started_at,
        "delta_continuity": delta_continuity,
        "continuity_reset": delta_reset,
        "continuity_reset_reason": delta_reset_reason,
        "prior_delta_archived_to": stale_delta_archive,
        "historical_complete": False,
        "retroactive_no_reply_claim_allowed": False,
        "read_only_observation": True,
        "send_authority_created": False,
        "authority_created": False,
    }
    _write_json(coverage_path, coverage)
    return {
        "state": "refreshed_after_stale_delta_reset" if delta_reset else "refreshed",
        "receipt": receipt,
        "readiness": readiness,
        "delta_recovery": {
            "attempted": delta_reset,
            "reason": delta_reset_reason,
            "stale_delta_archived_to": stale_delta_archive,
            "initial_error": first_failure,
            "recovered": bool(delta_reset and delta_continuity),
            "authority_created": False,
        },
        "coverage": coverage,
        "coverage_path": str(COVERAGE_RELATIVE_PATH),
        "authority_created": False,
        "external_effects": False,
    }
