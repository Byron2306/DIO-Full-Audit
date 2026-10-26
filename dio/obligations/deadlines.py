from __future__ import annotations

from typing import Any

from .models import parse_time, stable_id, utc_now


def _deadline_state(due_at: str, *, now: str, kind: str) -> str:
    current = parse_time(now)
    due = parse_time(due_at)
    assert current is not None and due is not None
    if kind == "expiry" and current >= due:
        return "expired"
    if kind != "expiry" and current > due:
        return "overdue"
    seconds = (due - current).total_seconds()
    return "due" if seconds <= 86400 else "open"


def identify_deadlines(bundle: dict[str, Any], *, now: str | None = None) -> list[dict[str, Any]]:
    """Derive deadline records only from explicit normalized date fields."""
    observed_now = now or utc_now()
    deadlines: list[dict[str, Any]] = []
    seen: set[str] = set()

    for obligation in bundle.get("obligations") or []:
        for kind, field in (("response", "due_at"), ("expiry", "expires_at")):
            due_at = obligation.get(field)
            if not due_at:
                continue
            parse_time(str(due_at))
            deadline_id = stable_id("ODEAD", obligation["obligation_id"], kind, due_at)
            if deadline_id in seen:
                continue
            seen.add(deadline_id)
            deadlines.append(
                {
                    "deadline_id": deadline_id,
                    "obligation_id": obligation["obligation_id"],
                    "kind": kind,
                    "due_at": str(due_at),
                    "state": _deadline_state(str(due_at), now=observed_now, kind=kind),
                }
            )

    bundle["deadlines"] = deadlines
    return deadlines
