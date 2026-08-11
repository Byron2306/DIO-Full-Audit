#!/usr/bin/env python3
"""Shared deterministic authority primitives for DIO assessment products."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LEVEL_ALIASES = {
    "excellent": "excellent",
    "outstanding": "excellent",
    "good": "good",
    "competent": "good",
    "satisfactory": "satisfactory",
    "adequate": "satisfactory",
    "needs improvement": "needs improvement",
    "needs work": "needs improvement",
    "limited": "needs improvement",
}

def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()

def canonical_level(value: Any) -> str:
    raw = _norm(value).replace("_", " ").replace("-", " ")
    raw = re.sub(r"\s+", " ", raw).strip()
    return LEVEL_ALIASES.get(raw, raw)

def rubric_band(criterion: dict[str, Any], declared_level: Any) -> dict[str, Any]:
    levels = criterion.get("levels") or {}
    wanted = canonical_level(declared_level)
    if not wanted:
        return {"resolved": False, "declared_level": "", "canonical_level": "", "reason": "declared_rubric_level_missing"}
    for key, payload in levels.items():
        if canonical_level(key) != wanted:
            continue
        payload = payload if isinstance(payload, dict) else {}
        if payload.get("min_score") is None or payload.get("max_score") is None:
            return {"resolved": False, "declared_level": str(declared_level or ""), "canonical_level": wanted, "reason": "rubric_level_has_no_numeric_band"}
        low = float(payload["min_score"])
        high = float(payload["max_score"])
        if high < low:
            low, high = high, low
        return {
            "resolved": True,
            "declared_level": str(declared_level or ""),
            "canonical_level": wanted,
            "rubric_level_key": str(key),
            "min_score": low,
            "max_score": high,
            "reason": "governing_rubric_band_resolved",
        }
    return {
        "resolved": False,
        "declared_level": str(declared_level or ""),
        "canonical_level": wanted,
        "available_levels": [str(key) for key in levels],
        "reason": "declared_rubric_level_not_in_governing_rubric",
    }

def authorize_rubric_score(proposed_score: Any, declared_level: Any, criterion: dict[str, Any]) -> dict[str, Any]:
    try:
        proposed = float(proposed_score)
    except Exception:
        proposed = 0.0
    criterion_max = float(criterion.get("weight") or 0.0)
    proposed = max(0.0, min(proposed, criterion_max))
    band = rubric_band(criterion, declared_level)
    if not band.get("resolved"):
        return {
            **band,
            "model_proposed_score": round(proposed, 2),
            "authorized_score": round(proposed, 2),
            "adjusted": False,
            "within_band": False,
            "release_authority": False,
        }
    low = max(0.0, float(band["min_score"]))
    high = min(criterion_max, float(band["max_score"]))
    authorized = min(max(proposed, low), high)
    adjusted = abs(authorized - proposed) > 1e-9
    return {
        **band,
        "model_proposed_score": round(proposed, 2),
        "authorized_score": round(authorized, 2),
        "adjusted": adjusted,
        "within_band": low - 1e-9 <= authorized <= high + 1e-9,
        "release_authority": True,
        "adjustment_reason": "model_score_outside_declared_rubric_band" if adjusted else "model_score_inside_declared_rubric_band",
    }

def evidence_support_state(*, grounded_count: int, requested_count: int) -> str:
    if requested_count <= 0 or grounded_count <= 0:
        return "unsupported"
    if grounded_count < requested_count:
        return "partially_supported"
    return "supported"

def fold_release(*, child_passes: list[bool], authority_ok: bool, evidence_ok: bool, semantic_ok: bool, human_approval_required: bool = True) -> dict[str, Any]:
    children_ok = bool(child_passes) and all(bool(value) for value in child_passes)
    technical_ok = children_ok and authority_ok and evidence_ok and semantic_ok
    if not technical_ok:
        state = "blocked"
    elif human_approval_required:
        state = "needs_human_review"
    else:
        state = "release_eligible"
    return {
        "state": state,
        "children_ok": children_ok,
        "authority_ok": bool(authority_ok),
        "evidence_ok": bool(evidence_ok),
        "semantic_ok": bool(semantic_ok),
        "human_approval_required": bool(human_approval_required),
        "release_authority_granted": state == "release_eligible",
    }

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def human_decision_event(*, job_id: str, subject_id: str, decision: str, reason: str, artifact_paths: list[Path], actor: str = "human_educator") -> dict[str, Any]:
    allowed = {"approve", "adjust", "reject", "defer"}
    normalized = str(decision or "").strip().lower()
    if normalized not in allowed:
        raise ValueError(f"decision must be one of {sorted(allowed)}")
    artifacts = []
    for path in artifact_paths:
        resolved = path.expanduser().resolve()
        artifacts.append({
            "path": str(resolved),
            "exists": resolved.is_file(),
            "sha256": sha256_file(resolved) if resolved.is_file() else None,
        })
    return {
        "schema": "dio.homs_human_decision_event.v1",
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "job_id": str(job_id),
        "subject_id": str(subject_id),
        "actor": str(actor),
        "decision": normalized,
        "reason": str(reason).strip(),
        "artifacts": artifacts,
    }

# === DIO Epistemic Spine Wave 2 =================================================

_EPISTEMIC_STOPWORDS = {
    "the","a","an","and","or","of","to","in","on","for","with","by","from","as",
    "is","are","was","were","be","been","being","that","this","these","those",
    "it","its","their","they","them","we","our","you","your","can","could","may",
    "might","should","would","about","into","through","than","then","also",
}

def epistemic_tokens(value: Any) -> set[str]:
    words = re.findall(r"[a-z0-9][a-z0-9'-]+", str(value or "").casefold())
    return {word for word in words if len(word) >= 3 and word not in _EPISTEMIC_STOPWORDS}

def criticism_authority(
    criticism: str,
    rubric_authority_text: str,
    *,
    minimum_overlap: int = 1,
) -> dict[str, Any]:
    """Classify whether a criticism has lexical authority in the governing rubric.

    This is deliberately conservative. A low-overlap criticism is not declared
    false; it is declared non-penalizing until a human or stronger authority
    binding says otherwise.
    """
    criticism_tokens = epistemic_tokens(criticism)
    authority_tokens = epistemic_tokens(rubric_authority_text)
    overlap = sorted(criticism_tokens & authority_tokens)
    authorized = len(overlap) >= int(minimum_overlap)
    return {
        "schema": "dio.epistemic.criticism_authority.v1",
        "authorized_to_affect_score": authorized,
        "authority_state": "rubric_bound" if authorized else "enrichment_only_non_penalizing",
        "overlap_tokens": overlap,
        "criticism_token_count": len(criticism_tokens),
        "authority_token_count": len(authority_tokens),
    }

def claim_epistemic_state(
    *,
    support_count: int = 0,
    partial_support_count: int = 0,
    contradiction_count: int = 0,
    verification_required: bool = False,
    human_judgment: bool = False,
    outside_available_evidence: bool = False,
) -> str:
    """Return a typed scholarly/assessment epistemic state."""
    if human_judgment:
        return "AUTHOR_JUDGMENT"
    if outside_available_evidence:
        return "OUTSIDE_AVAILABLE_EVIDENCE"
    if contradiction_count > 0 and support_count > 0:
        return "CONTESTED"
    if contradiction_count > 0 and support_count <= 0:
        return "CONTRADICTED"
    if support_count > 0 and partial_support_count <= 0 and not verification_required:
        return "SUPPORTED"
    if support_count > 0 or partial_support_count > 0:
        return "PARTIALLY_SUPPORTED"
    return "UNVERIFIED"

def factual_assertion_risk(statement: str) -> dict[str, Any]:
    """Triage factual assertions for verification without pretending to prove truth."""
    text = re.sub(r"\s+", " ", str(statement or "")).strip()
    lower = text.casefold()
    score = 0
    reasons: list[str] = []

    if re.search(r"\b(?:18|19|20)\d{2}\b", text):
        score += 1
        reasons.append("dated_assertion")
    if re.search(r"\b\d+(?:\.\d+)?\s*%\b", text):
        score += 2
        reasons.append("quantified_percentage")
    if re.search(r"\b\d{2,}\b", text):
        score += 1
        reasons.append("material_number")
    if any(token in lower for token in [
        "always", "never", "all ", "none ", "completely", "entirely", "proved",
        "caused", "forced", "destroyed", "decisive", "single-handedly", "only reason",
    ]):
        score += 2
        reasons.append("strong_or_absolute_causal_language")
    if re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b", text):
        score += 1
        reasons.append("named_entity_assertion")

    if score >= 4:
        level = "HIGH"
    elif score >= 2:
        level = "MEDIUM"
    else:
        level = "LOW"
    return {
        "schema": "dio.epistemic.factual_risk.v1",
        "risk": level,
        "score": score,
        "reasons": reasons,
        "verification_required": level in {"HIGH", "MEDIUM"},
        "truth_determined": False,
    }

def curriculum_binding(
    item_text: str,
    curriculum_elements: list[str],
    *,
    minimum_overlap: int = 2,
) -> dict[str, Any]:
    """Bind an assessment item to resolved curriculum text by transparent overlap."""
    item_tokens = epistemic_tokens(item_text)
    best: dict[str, Any] | None = None
    for index, element in enumerate(curriculum_elements):
        element_tokens = epistemic_tokens(element)
        overlap = sorted(item_tokens & element_tokens)
        candidate = {
            "element_index": index,
            "element": str(element),
            "overlap_tokens": overlap,
            "overlap_count": len(overlap),
        }
        if best is None or candidate["overlap_count"] > best["overlap_count"]:
            best = candidate
    best = best or {"element_index": None, "element": None, "overlap_tokens": [], "overlap_count": 0}
    passed = int(best["overlap_count"]) >= int(minimum_overlap)
    return {
        "schema": "dio.epistemic.curriculum_binding.v1",
        "passed": passed,
        "state": "BOUND" if passed else "UNRESOLVED",
        "minimum_overlap": int(minimum_overlap),
        **best,
    }

def distribution_contract(
    observed: dict[str, float],
    required: dict[str, float],
    *,
    tolerance_percentage_points: float = 15.0,
) -> dict[str, Any]:
    """Check assessment-family distribution without claiming exact CAPS legality."""
    rows = []
    passed = True
    for key, target in (required or {}).items():
        obs = float((observed or {}).get(key, 0.0) or 0.0)
        target_f = float(target or 0.0)
        delta = round(obs - target_f, 2)
        ok = abs(delta) <= float(tolerance_percentage_points)
        passed = passed and ok
        rows.append({
            "dimension": key,
            "required_percent": target_f,
            "observed_percent": obs,
            "delta_percentage_points": delta,
            "within_tolerance": ok,
        })
    return {
        "schema": "dio.epistemic.distribution_contract.v1",
        "passed": passed,
        "tolerance_percentage_points": float(tolerance_percentage_points),
        "rows": rows,
    }

def hash_chained_event(
    *,
    event_type: str,
    subject_id: str,
    payload: dict[str, Any],
    previous_event_sha256: str = "",
) -> dict[str, Any]:
    """Create a tamper-evident append-only event node."""
    base = {
        "schema": "dio.epistemic.lineage_event.v1",
        "event_type": str(event_type),
        "subject_id": str(subject_id),
        "previous_event_sha256": str(previous_event_sha256 or ""),
        "payload": payload,
    }
    material = json.dumps(base, sort_keys=True, ensure_ascii=True, default=str)
    event_sha = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return {**base, "event_sha256": event_sha}

def append_hash_chained_event(path: Path, event_type: str, subject_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Append a lineage event whose hash commits to the prior event hash."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    previous = ""
    if target.exists():
        lines = [line for line in target.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
        if lines:
            try:
                previous = str(json.loads(lines[-1]).get("event_sha256") or "")
            except Exception:
                previous = ""
    event = hash_chained_event(
        event_type=event_type,
        subject_id=subject_id,
        payload=payload,
        previous_event_sha256=previous,
    )
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, ensure_ascii=True, default=str) + "\n")
    return event
