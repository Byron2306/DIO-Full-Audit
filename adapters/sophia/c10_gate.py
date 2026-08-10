from __future__ import annotations

from typing import Any


def require_lineage_clear_summary(c10: dict[str, Any], *, minimum_versions: int) -> None:
    """Fail closed unless the longitudinal Speculum is review-ready.

    This dependency-light gate proves the living lineage is structurally ready.
    It does not, by itself, certify that every material scholarly change has a
    recorded human decision. Use ``require_scholarly_release_clear_summary`` for
    the final C10 release boundary.
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


def require_scholarly_release_clear_summary(
    c10: dict[str, Any],
    *,
    minimum_versions: int,
    topology: dict[str, Any],
) -> None:
    """Final C10 release gate for lineage plus human scholarly obligations.

    A valid hash is not enough. If Sophia has surfaced a material revision
    question that requires human ownership, silence must not be interpreted as
    approval, intent, resolution, or scholarly judgment.
    """
    require_lineage_clear_summary(c10, minimum_versions=minimum_versions)
    if topology.get("state") != "scholarly_topology_ready":
        raise ValueError("C10 scholarly topology audit is not ready.")
    if len(str(topology.get("topology_audit_hash") or "")) != 64:
        raise ValueError("C10 scholarly topology audit hash is missing or invalid.")
    if len(str(topology.get("decision_queue_hash") or "")) != 64:
        raise ValueError("C10 scholarly decision-queue hash is missing or invalid.")
    blocking = int(topology.get("blocking_decision_queue") or 0)
    if blocking:
        raise ValueError(
            f"C10 has {blocking} unresolved scholarly decision obligation(s). "
            "Human decisions are required before release."
        )
