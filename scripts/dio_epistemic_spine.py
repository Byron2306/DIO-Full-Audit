from __future__ import annotations

from typing import Any


SUPPORTED = "SUPPORTED"
PARTIAL = "PARTIAL"
UNVERIFIED = "UNVERIFIED"
CONTESTED = "CONTESTED"
STALE = "STALE"
OUTSIDE_AVAILABLE_EVIDENCE = "OUTSIDE_AVAILABLE_EVIDENCE"

_EPISTEMIC_TOKENS = (
    SUPPORTED,
    PARTIAL,
    UNVERIFIED,
    CONTESTED,
    STALE,
    OUTSIDE_AVAILABLE_EVIDENCE,
)


def epistemic_tokens() -> tuple[str, ...]:
    """Return the stable DIO epistemic-state vocabulary.

    This module is intentionally tiny. It is a shared deterministic primitive used
    by product adapters such as Evidex and VAMP; it does not create evidence,
    authority, confidence, or release permission.
    """

    return _EPISTEMIC_TOKENS


def _count(value: Any, name: str) -> int:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer-like non-negative count") from exc
    if parsed < 0:
        raise ValueError(f"{name} cannot be negative")
    return parsed


def claim_epistemic_state(
    *,
    support_count: int = 0,
    partial_support_count: int = 0,
    contradiction_count: int = 0,
    stale_count: int = 0,
    outside_available_evidence: bool = False,
    **_: Any,
) -> str:
    """Classify a claim from explicit evidence-state counts only.

    Ordering is conservative and deterministic:
    - any contradiction -> CONTESTED;
    - stale-only evidence -> STALE;
    - complete positive support -> SUPPORTED;
    - mixed/partial positive support -> PARTIAL;
    - no available evidence by construction -> OUTSIDE_AVAILABLE_EVIDENCE;
    - otherwise -> UNVERIFIED.

    The function deliberately ignores confidence scores and never upgrades a claim
    merely because an upstream model or matcher is confident.
    """

    support = _count(support_count, "support_count")
    partial = _count(partial_support_count, "partial_support_count")
    contradictions = _count(contradiction_count, "contradiction_count")
    stale = _count(stale_count, "stale_count")

    if contradictions:
        return CONTESTED
    if stale and not support and not partial:
        return STALE
    if support and not partial:
        return SUPPORTED
    if support or partial:
        return PARTIAL
    if bool(outside_available_evidence):
        return OUTSIDE_AVAILABLE_EVIDENCE
    return UNVERIFIED


__all__ = [
    "SUPPORTED",
    "PARTIAL",
    "UNVERIFIED",
    "CONTESTED",
    "STALE",
    "OUTSIDE_AVAILABLE_EVIDENCE",
    "epistemic_tokens",
    "claim_epistemic_state",
]
