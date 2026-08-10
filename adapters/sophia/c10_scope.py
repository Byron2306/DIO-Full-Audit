from __future__ import annotations

import re
from typing import Any, Callable


STRONG_CAUSAL_PATTERNS = (
    r"\bcaus(?:e|es|ed|ing)\b",
    r"\bbecause\b",
    r"\blead(?:s|ing)?\s+to\b",
    r"\bresult(?:s|ed|ing)?\s+in\b",
    r"\beffect\s+of\b",
    r"\bimpact\s+of\b",
    r"\bproduc(?:e|es|ed|ing)\b",
)

ASSOCIATIONAL_PATTERNS = (
    r"\bassociat(?:e|es|ed|ion|ions|ing)\s+with\b",
    r"\bcorrelat(?:e|es|ed|ion|ions|ing)\s+with\b",
    r"\brelationship\s+between\b",
    r"\blink(?:ed|s)?\s+with\b",
)

OUTCOME_VERB_PATTERNS = (
    r"\bimprov(?:e|es|ed|ing)\b",
    r"\bincreas(?:e|es|ed|ing)\b",
    r"\breduc(?:e|es|ed|ing)\b",
    r"\bdecreas(?:e|es|ed|ing)\b",
    r"\benhanc(?:e|es|ed|ing)\b",
)

UNIVERSAL_PATTERNS = (
    r"\ball\b",
    r"\bevery\b",
    r"\balways\b",
    r"\bnever\b",
    r"\bproves?\b",
    r"\bguarantees?\b",
    r"\beliminates?\b",
    r"\bsolves?\b",
    r"\bdefinitively\b",
    r"\bacross\s+all\b",
    r"\bin\s+every\b",
    r"\bwithout\s+exception\b",
)

HEDGING_PATTERNS = (
    r"\bmay\b",
    r"\bmight\b",
    r"\bcould\b",
    r"\bsuggest(?:s|ed|ing)?\b",
    r"\bappears?\b",
    r"\bpreliminary\b",
    r"\bpossible\b",
    r"\bin\s+this\s+sample\b",
    r"\bin\s+this\s+context\b",
    *ASSOCIATIONAL_PATTERNS,
)


def _has(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def governed_scope_signature(text: str, claim_type: str, *, normalize: Callable[[Any], str] | None = None) -> dict[str, Any]:
    """Classify epistemic scope without treating an outcome adjective as causal syntax.

    The critical rule is contextual: ``associated with improved outcomes`` remains
    associational. Outcome verbs only imply causal scope when they operate as the
    proposition's causal predicate and are not subordinated to an explicit
    associational construction.
    """
    lowered = normalize(text) if normalize else re.sub(r"\s+", " ", str(text or "")).strip().lower()
    declared_causal = str(claim_type or "").lower() == "causal"
    strong_causal = _has(STRONG_CAUSAL_PATTERNS, lowered)
    associational = _has(ASSOCIATIONAL_PATTERNS, lowered)
    outcome_verb = _has(OUTCOME_VERB_PATTERNS, lowered)

    causal = bool(declared_causal or strong_causal or (outcome_verb and not associational))
    universal = _has(UNIVERSAL_PATTERNS, lowered)
    hedged = _has(HEDGING_PATTERNS, lowered)

    if universal and causal:
        strength = 4
    elif universal:
        strength = 3
    elif causal and not hedged:
        strength = 3
    elif causal or not hedged:
        strength = 2
    else:
        strength = 1

    return {
        "causal": causal,
        "universal": universal,
        "hedged": hedged,
        "associational": associational,
        "outcome_verb": outcome_verb,
        "strong_causal_syntax": strong_causal,
        "strength": strength,
    }


def install_longitudinal_scope_patch(module: Any) -> None:
    """Install the hardened classifier into the C10 longitudinal module.

    Kept as a tiny package-level hardening hook so the branch can correct the
    scope classifier without duplicating the large longitudinal engine.
    """
    module._scope_signature = lambda text, claim_type: governed_scope_signature(  # type: ignore[attr-defined]
        text,
        claim_type,
        normalize=module._normalize,
    )
