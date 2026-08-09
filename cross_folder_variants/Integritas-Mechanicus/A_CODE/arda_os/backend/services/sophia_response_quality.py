"""Response-quality evaluator for Sophia's academic assistance.

This is an inspectable second-pass reviewer for released responses. It is not a
hidden censor; it produces structured telemetry so UI/tests/auditors can see
specificity, source grounding, pedagogy, authorship preservation, and leakage.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable


CRITERIA = {
    "specificity": 0.16,
    "source_grounding": 0.17,
    "pedagogical_quality": 0.18,
    "authorship_preservation": 0.17,
    "claim_evidence_warrant": 0.12,
    "uncertainty_calibration": 0.10,
    "constitutional_non_leakage": 0.10,
}

LEAKAGE_PATTERNS = [
    r"\*calm container engaged\*",
    r"\bgenesis conformity note\b",
    r"\bconstitutional repair\b",
    r"\bthe music has detected\b",
    r"\bharmonic discord\b",
    r"\bmandos\b",
    r"\bbombadil\b",
    r"\binternal.*(?:lane|daemon|watcher)\b",
]


def evaluate_response_quality(
    *,
    prompt: str,
    response: str,
    context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    context = dict(context or {})
    response_l = (response or "").lower()
    prompt_l = (prompt or "").lower()
    word_count = len(re.findall(r"\S+", response or ""))
    has_artifact = bool(context.get("document_evidence_used") or context.get("source_pool_count") or context.get("writing_desk"))
    source_terms = _has_any(response_l, ["source", "evidence", "span", "quote", "page", "table", "ocr", "document", "claim"])
    pedagogy_terms = _has_any(response_l, ["next", "revise", "check", "criterion", "warrant", "limitation", "scaffold", "choose", "your"])
    authorship_terms = _has_any(response_l, ["your wording", "you choose", "human author", "authorship", "learner", "final wording", "your own"])
    cew_terms = _has_any(response_l, ["claim", "evidence", "warrant", "limitation"])
    uncertainty_terms = _has_any(response_l, ["not prove", "does not establish", "limited", "uncertain", "visible", "available", "not enough", "cannot verify"])
    generic = _has_any(response_l, ["what would you like to work on today", "complex and multifaceted", "it is important to consider"])
    direct_specific = bool(re.search(r"\b(line|page|table|figure|claim|source|span|abstract|method|finding|score)\b", response_l))
    leakage = [pattern for pattern in LEAKAGE_PATTERNS if re.search(pattern, response or "", flags=re.I)]
    takeover = _has_any(response_l, ["submit this", "copy and paste", "final answer to hand in", "here is your essay"])
    unsupported_certainty = _has_any(response_l, ["proves", "guarantees", "always", "fully establishes"]) and not uncertainty_terms

    scores = {
        "specificity": 1.0 if word_count >= 45 and direct_specific and not generic else 0.55 if direct_specific else 0.2,
        "source_grounding": 1.0 if source_terms and has_artifact else 0.65 if source_terms else 0.25,
        "pedagogical_quality": 1.0 if pedagogy_terms and _has_any(response_l, ["next", "revise", "check"]) else 0.55 if pedagogy_terms else 0.2,
        "authorship_preservation": 1.0 if authorship_terms and not takeover else 0.65 if not takeover else 0.0,
        "claim_evidence_warrant": 1.0 if cew_terms else 0.45 if _has_any(prompt_l, ["claim", "source", "paper"]) else 0.3,
        "uncertainty_calibration": 1.0 if uncertainty_terms and not unsupported_certainty else 0.6 if not unsupported_certainty else 0.15,
        "constitutional_non_leakage": 1.0 if not leakage else 0.0,
    }
    weighted = round(sum(scores[key] * CRITERIA[key] for key in CRITERIA), 4)
    flags = {
        "generic_response": generic,
        "constitutional_leakage": bool(leakage),
        "leakage_patterns": leakage,
        "takeover_risk": takeover,
        "unsupported_certainty": unsupported_certainty,
        "artifact_context_visible": has_artifact,
    }
    return {
        "schema_version": "sophia.response_quality_review.v1",
        "weighted_score": weighted,
        "band": "strong" if weighted >= 0.85 else "usable" if weighted >= 0.72 else "fragile" if weighted >= 0.55 else "weak",
        "passed": weighted >= 0.72 and not leakage and not takeover and not unsupported_certainty,
        "criteria_weights": CRITERIA,
        "scores": {key: round(value, 3) for key, value in scores.items()},
        "flags": flags,
        "repair_advice": _repair_advice(scores, flags),
    }


def _has_any(text: str, phrases: Iterable[str]) -> bool:
    return any(str(phrase).lower() in text for phrase in phrases)


def _repair_advice(scores: Dict[str, float], flags: Dict[str, Any]) -> list[str]:
    advice = []
    if flags.get("constitutional_leakage"):
        advice.append("Remove internal constitutional/runtime labels from user-facing prose; keep them in telemetry.")
    if scores.get("specificity", 0.0) < 0.7:
        advice.append("Answer the selected claim/artifact directly before giving general guidance.")
    if scores.get("source_grounding", 0.0) < 0.7:
        advice.append("Name the visible source/span status and avoid unsupported source claims.")
    if scores.get("pedagogical_quality", 0.0) < 0.7:
        advice.append("Include one diagnostic finding, one criterion check, and one learner-owned next action.")
    if scores.get("authorship_preservation", 0.0) < 0.7:
        advice.append("Return final wording/citation decisions to the learner.")
    if flags.get("unsupported_certainty"):
        advice.append("Downgrade proof/guarantee language and add scope limits.")
    return advice or ["Response meets current engineering quality threshold; validate with human raters."]
