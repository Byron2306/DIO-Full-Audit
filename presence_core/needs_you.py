from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .state import read_json, safe, write_json


SCHEMA = "dio.presence_needs_you.v1"

DECISIONS = {
    "APPROVE",
    "REFUSE",
}


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
    )


def _path(root: Path, needs_you_id: str) -> Path:
    return (
        Path(root)
        / "needs_you"
        / f"{safe(needs_you_id)}.json"
    )


def load_needs_you(
    root: Path,
    needs_you_id: str,
) -> dict[str, Any] | None:
    path = _path(root, needs_you_id)

    if not path.is_file():
        return None

    value = read_json(path)

    if value.get("schema") != SCHEMA:
        raise ValueError(
            "unsupported Needs You schema"
        )

    return value


def resolve_needs_you(
    root: Path,
    needs_you_id: str,
    *,
    decision: str,
    resolved_by: str,
    evidence_ref: str,
    note: str | None = None,
) -> dict[str, Any]:
    decision = str(decision or "").strip().upper()

    if decision not in DECISIONS:
        raise ValueError(
            "decision must be APPROVE or REFUSE"
        )

    resolved_by = str(
        resolved_by or ""
    ).strip()

    evidence_ref = str(
        evidence_ref or ""
    ).strip()

    if not resolved_by:
        raise ValueError(
            "resolved_by is required"
        )

    if not evidence_ref:
        raise ValueError(
            "evidence_ref is required"
        )

    item = load_needs_you(
        root,
        needs_you_id,
    )

    if item is None:
        raise ValueError(
            f"Needs You item not found: {needs_you_id}"
        )

    state = str(
        item.get("state") or ""
    ).strip().lower()

    if state != "open":
        raise ValueError(
            "Needs You item is already resolved"
        )

    updated = dict(item)

    updated.update(
        {
            "state": "resolved",
            "decision": decision,
            "resolved_by": resolved_by,
            "resolved_at": _now(),
            "resolution_evidence_ref": evidence_ref,
            "resolution_note": (
                str(note)[:2000]
                if note
                else None
            ),
            "authority_created": False,
        }
    )

    write_json(
        _path(root, needs_you_id),
        updated,
    )

    return updated
