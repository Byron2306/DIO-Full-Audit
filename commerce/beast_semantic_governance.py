from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

from .mandos import active_negative_capabilities_for as mandos_negative_capabilities_for


ROOT = Path(__file__).resolve().parents[1]

BLAST_RADIUS = {
    "outlook_draft": 0.25,
    "mail_send": 0.55,
    "public_publish": 0.8,
    "paid_media_publish": 0.9,
    "invoice_send": 0.75,
    "delivery_send": 0.8,
}

SEVERITY = {
    "outlook_draft": "low",
    "mail_send": "medium",
    "public_publish": "high",
    "paid_media_publish": "high",
    "invoice_send": "high",
    "delivery_send": "high",
}


def _scorer_path() -> Path:
    configured = os.getenv("DIO_BEAST_ROOT", "").strip()
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser() / "app/kernel/storage/evidence_scoring.py")
    candidates.append(
        ROOT
        / "cross_folder_variants"
        / "EdgeK-BEAST"
        / "A_CODE"
        / "app"
        / "kernel"
        / "storage"
        / "evidence_scoring.py"
    )
    return next((path for path in candidates if path.is_file()), candidates[-1])


def load_evidence_scorer() -> tuple[Any, str]:
    """Load the real BEAST EvidenceScorer without making the DIO package depend on BEAST imports."""
    path = _scorer_path()
    if not path.is_file():
        raise RuntimeError(f"BEAST EvidenceScorer unavailable at {path}")
    module_name = "dio_beast_evidence_scoring"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load BEAST EvidenceScorer module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.EvidenceScorer, str(path)


def _semantic_value(cso: dict[str, Any], section: str, field: str) -> Any:
    item = (cso.get(section) or {}).get(field)
    if isinstance(item, dict):
        return item.get("value")
    return item


def _expression_selector_scope(cso: dict[str, Any], expression: dict[str, Any]) -> dict[str, Any]:
    """Return only failure-memory selectors the current expression can actually prove."""
    plan = expression.get("plan") or {}
    contract = plan.get("contract") or {}
    verified_context = plan.get("verified_context") or {}
    tactic_context = verified_context.get("tactic_id")
    tactic_id = expression.get("tactic_id") or plan.get("tactic_id")
    if not tactic_id and isinstance(tactic_context, dict):
        tactic_id = tactic_context.get("value")
    return {
        "product": _semantic_value(cso, "commercial", "product"),
        "offer": _semantic_value(cso, "commercial", "offer"),
        "communicative_act": expression.get("communicative_act"),
        "channel": contract.get("channel") or _semantic_value(cso, "strategy", "channel"),
        "tactic_id": tactic_id,
    }


def _strict_remembered_matches(
    rows: list[dict[str, Any]],
    current_scope: dict[str, Any],
) -> list[dict[str, Any]]:
    """Never broaden a stored failure when a selector is absent from current proof scope."""
    matches: list[dict[str, Any]] = []
    for row in rows:
        selectors = row.get("selectors") or {}
        required = {key: value for key, value in selectors.items() if value not in {None, ""}}
        if not required:
            continue
        proven = True
        for key, expected in required.items():
            actual = current_scope.get(key)
            if actual in {None, ""} or str(actual) != str(expected):
                proven = False
                break
        if proven:
            matches.append(row)
    return matches


def assess_expression_evidence(
    cso: dict[str, Any],
    expression: dict[str, Any],
    *,
    execution_kind: str,
    repeat_count: int = 1,
    active_negative_capabilities: list[dict[str, Any]] | None = None,
    memory_root: Path | None = None,
) -> dict[str, Any]:
    """Apply BEAST evidence scoring and Mandos failure memory to semantic dependencies.

    The scorer never infers claims from prose. Mandos contributes only typed, repeated,
    verified failure patterns that have already earned `active` negative-capability state.
    Positive Mandos patterns never expand execution authority through this path.
    """
    dependencies = list(expression.get("claim_sources") or [])
    total = len(dependencies)
    verified = 0
    inferred = 0
    invalid = 0
    missing_refs = 0
    for row in dependencies:
        status = str(row.get("status") or "")
        refs = [str(ref).strip() for ref in (row.get("source_refs") or []) if str(ref).strip()]
        if status == "verified":
            verified += 1
        elif status == "inferred":
            inferred += 1
        else:
            invalid += 1
        if not refs:
            missing_refs += 1

    denominator = max(1, total)
    verification_strength = max(0.0, min(1.0, (verified + 0.45 * inferred) / denominator))
    confidence = max(
        0.0,
        min(
            1.0,
            1.0
            - (0.45 * inferred / denominator)
            - (0.8 * missing_refs / denominator)
            - (invalid / denominator),
        ),
    )
    relevance = 1.0 if expression.get("semantic_object_id") == cso.get("object_id") else 0.0

    EvidenceScorer, scorer_source = load_evidence_scorer()
    score = EvidenceScorer().score(
        relevance=relevance,
        confidence=confidence,
        severity=SEVERITY.get(execution_kind, "medium"),
        freshness=1.0,
        repeat_count=max(1, int(repeat_count or 1)),
        verification_strength=verification_strength,
        blast_radius=BLAST_RADIUS.get(execution_kind, 0.5),
    ).to_dict()

    supplied = list(active_negative_capabilities or [])
    remembered_candidates = mandos_negative_capabilities_for(
        (memory_root or ROOT).resolve(),
        cso,
        expression,
        execution_kind=execution_kind,
    )
    current_scope = _expression_selector_scope(cso, expression)
    remembered = _strict_remembered_matches(remembered_candidates, current_scope)
    merged: dict[str, dict[str, Any]] = {}
    for row in [*supplied, *remembered]:
        key = str(row.get("capability_id") or row.get("pattern_key") or repr(row))
        merged[key] = row
    active_negative_capabilities = list(merged.values())

    blockers: list[dict[str, Any]] = []
    cautions: list[dict[str, Any]] = []
    if not dependencies:
        blockers.append({"code": "CLAIM_MANIFEST_MISSING", "message": "Expression declared no semantic claim dependencies."})
    if missing_refs:
        blockers.append({"code": "CLAIM_SOURCE_MISSING", "message": f"{missing_refs} declared claim dependencies have no source reference."})
    if invalid:
        blockers.append({"code": "CLAIM_STATUS_INVALID", "message": f"{invalid} declared claim dependencies have an invalid epistemic status."})
    if relevance < 1.0:
        blockers.append({"code": "SEMANTIC_OBJECT_MISMATCH", "message": "Expression is bound to a different Commercial Semantic Object."})
    if active_negative_capabilities:
        blockers.append({
            "code": "ACTIVE_NEGATIVE_CAPABILITY",
            "message": "BEAST has an active repeated failure pattern matching this expression/execution route.",
            "matches": active_negative_capabilities,
        })
    if inferred:
        cautions.append({
            "code": "INFERRED_DEPENDENCIES_PRESENT",
            "message": f"Expression carries {inferred} inferred semantic dependencies; they must remain visibly non-factual.",
        })
    unknowns = list(((expression.get("plan") or {}).get("unknowns")) or [])
    if unknowns:
        cautions.append({
            "code": "EXPLICIT_UNKNOWNS_RETAINED",
            "message": f"The semantic plan retains {len(unknowns)} explicit unknown fields.",
            "fields": unknowns,
        })

    if blockers:
        status = "BLOCK"
    elif cautions or float(score.get("uncertainty") or 0.0) >= 0.35:
        status = "CAUTION"
    else:
        status = "PASS"
    return {
        "schema": "dio.beast_semantic_evidence_assessment.v2",
        "status": status,
        "scorer": {
            "organ": "EdgeK-BEAST EvidenceScorer",
            "source": scorer_source,
            "score": score,
        },
        "dependency_summary": {
            "total": total,
            "verified": verified,
            "inferred": inferred,
            "invalid": invalid,
            "missing_source_refs": missing_refs,
            "verification_strength": round(verification_strength, 5),
            "confidence": round(confidence, 5),
        },
        "active_negative_capabilities": active_negative_capabilities,
        "mandos_memory": {
            "root": str((memory_root or ROOT).resolve()),
            "remembered_candidates": len(remembered_candidates),
            "remembered_matches": len(remembered),
            "selector_scope": current_scope,
            "positive_memory_may_expand_authority": False,
            "unprovable_selector_may_broaden_veto": False,
        },
        "blockers": blockers,
        "cautions": cautions,
        "principles": {
            "unbound_prose_never_becomes_evidence": True,
            "source_change_requires_rejudgement": True,
            "reuse_does_not_expand_authority": True,
            "negative_capability_can_veto_execution": True,
            "mandos_does_not_forget_verified_failure": True,
            "unprovable_selector_never_broadens_failure_scope": True,
        },
    }
