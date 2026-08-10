from __future__ import annotations

from typing import Any


def require_lineage_clear_summary(c10: dict[str, Any], *, minimum_versions: int) -> None:
    """Fail closed unless the longitudinal Speculum is review-ready.

    This function is intentionally dependency-light so the scholarly-memory gate
    can be tested without importing the commercial/payment stack.
    """
    if c10.get("state") != "longitudinal_speculum_ready":
        raise ValueError("C10 longitudinal Speculum is not ready.")
    if int(c10.get("version_count") or 0) < minimum_versions:
        raise ValueError(f"C10 needs at least {minimum_versions} bound draft version(s) for this gate.")
    if c10.get("unresolved_continuity_candidates"):
        raise ValueError("Resolve ambiguous claim-lineage candidates before C10 approval.")
    if len(str(c10.get("longitudinal_speculum_hash") or "")) != 64:
        raise ValueError("C10 longitudinal Speculum hash is missing or invalid.")
    if len(str(c10.get("native_integrity_record_hash") or "")) != 64:
        raise ValueError("Native Sophia integrity-record hash is missing or invalid.")
