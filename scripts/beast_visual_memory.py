from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.lingua_beast_bridge import (
    CHAIN_PATH,
    canonical_digest,
    load_beast,
    load_beast_organs,
    record_learning_event,
    write_memory_residue,
)

ROOT = Path(__file__).resolve().parents[1]
VISUAL_STORAGE_ROOT = ROOT / "state" / "visual" / "beast_credits"
VISUAL_NEGATIVE_PATH = ROOT / "state" / "visual" / "beast_negative_capabilities.json"
VISUAL_TASK_CLASS = "dio_visual_design_crystal"
VISUAL_CAPABILITY_ID = "dio_visual_projection"


def _storage() -> Any:
    DurableInferenceStorage, _ = load_beast()
    return DurableInferenceStorage(VISUAL_STORAGE_ROOT)


def resolve_visual_memory(*, audience_archetype: str, surface: str, visual_grammar: str) -> dict[str, Any]:
    """Resolve only human-approved visual memory as representational context.

    BEAST may inform style projection but may not create semantic or release authority.
    Absence of an approved crystal is a normal miss; Document Studio's governed base
    art language remains the fallback.
    """
    try:
        storage = _storage()
    except Exception as exc:
        return {
            "schema": "dio.visual.beast_resolution.v1",
            "state": "beast_unavailable",
            "approved_crystal_refs": [],
            "approved_patterns": [],
            "negative_patterns": [],
            "memory_hull_refs": [],
            "error": str(exc),
            "authority": "representational_context_only",
            "semantic_authority_created": False,
            "release_authority_created": False,
        }

    approved: list[dict[str, Any]] = []
    for credit in storage.credits.values():
        try:
            reusable = credit.is_reusable()
        except Exception:
            reusable = False
        if not reusable or credit.task_class != VISUAL_TASK_CLASS:
            continue
        metadata = credit.metadata or {}
        if metadata.get("human_approved") is not True:
            continue
        if str(metadata.get("audience_archetype") or "*") not in {"*", audience_archetype}:
            continue
        if str(metadata.get("surface") or "*") not in {"*", surface}:
            continue
        grammar = str(metadata.get("visual_grammar") or "*")
        if grammar not in {"*", visual_grammar}:
            continue
        approved.append({
            "credit_id": credit.credit_id,
            "design_pattern": metadata.get("design_pattern") or {},
            "audience_archetype": metadata.get("audience_archetype"),
            "surface": metadata.get("surface"),
            "visual_grammar": metadata.get("visual_grammar"),
            "reviewer": metadata.get("reviewer"),
        })

    negative_patterns: list[dict[str, Any]] = []
    try:
        organs = load_beast_organs()
        negative_store = organs["NegativeCapabilityStore"](VISUAL_NEGATIVE_PATH)
        matches = negative_store.active_matches({
            "capability_id": VISUAL_CAPABILITY_ID,
            "task_class": "visual_projection_quality",
            "scope": {
                "route": audience_archetype,
                "transform_type": surface,
            },
        })
        for row in matches:
            negative_patterns.append(dict(row) if isinstance(row, dict) else {"pattern": str(row)})
    except Exception:
        negative_patterns = []

    state = "approved_visual_crystal_hit" if approved else "no_approved_visual_crystal"
    result = {
        "schema": "dio.visual.beast_resolution.v1",
        "state": state,
        "approved_crystal_refs": [row["credit_id"] for row in approved],
        "approved_patterns": approved,
        "negative_patterns": negative_patterns,
        "memory_hull_refs": [],
        "authority": "representational_context_only",
        "semantic_authority_created": False,
        "release_authority_created": False,
    }
    try:
        record_learning_event(
            event_type="visual_crystal_reused" if approved else "visual_crystal_missed",
            capability_type="visual_projection_memory",
            capability_id=f"visual:{audience_archetype}:{surface}",
            lifecycle_state="reused" if approved else "observed",
            authority="representational_context_only",
            evidence={
                "audience_archetype": audience_archetype,
                "surface": surface,
                "visual_grammar": visual_grammar,
            },
            receipt=result,
            provider_calls_avoided=0,
            reuse_hits=len(approved),
            metadata={"visual_grammar": visual_grammar},
        )
    except Exception:
        pass
    return result


def record_visual_rejection(
    *,
    audience_archetype: str,
    surface: str,
    failure_category: str,
    detail: str,
    artifact_id: str,
    reviewer: str,
) -> dict[str, Any]:
    """Feed an explicit human visual rejection into BEAST negative capability memory.

    One rejection is evidence, not an active prohibition. BEAST's own repetition
    threshold decides when the pattern becomes an active negative capability.
    """
    if not reviewer.strip():
        raise ValueError("A named human reviewer is required for visual feedback.")
    if not detail.strip():
        raise ValueError("Visual rejection detail is required.")
    organs = load_beast_organs()
    negative_store = organs["NegativeCapabilityStore"](VISUAL_NEGATIVE_PATH)
    scope = {"route": audience_archetype, "transform_type": surface}
    outcome = organs["OutcomeEvidence"].create(
        capability_id=VISUAL_CAPABILITY_ID,
        task_class="visual_projection_quality",
        outcome="failure",
        failure_category=failure_category,
        failure_code="human_reject",
        detail=detail,
        scope=scope,
        confidence_before=1.0,
        selected_capabilities=("document_studio_art_direction", "gamma_visual_generation", "nichefoundry_motion"),
    )
    record = negative_store.record(outcome)
    repeat_count = record.failure_count if record else 1
    result = {
        "schema": "dio.visual.rejection_receipt.v1",
        "state": "recorded",
        "artifact_id": artifact_id,
        "reviewer": reviewer,
        "audience_archetype": audience_archetype,
        "surface": surface,
        "failure_category": failure_category,
        "detail": detail,
        "repeat_count": repeat_count,
        "negative_capability_active": bool(record and getattr(record, "state", "") == "active"),
        "authority": "negative_evidence_only",
        "semantic_authority_created": False,
        "release_authority_created": False,
    }
    try:
        residue = write_memory_residue(
            task=f"Visual rejection for {audience_archetype}/{surface}",
            decision=f"Human rejected visual projection: {failure_category}",
            evidence={"artifact_id": artifact_id, "detail": detail, "repeat_count": repeat_count},
            tags=["visual-design", "document-studio", "human-rejected", "negative-capability"],
        )
        result["memory_residue"] = residue
    except Exception:
        result["memory_residue"] = None
    try:
        record_learning_event(
            event_type="visual_projection_rejected",
            capability_type="visual_projection_quality",
            capability_id=f"visual:{audience_archetype}:{surface}",
            lifecycle_state="rejected",
            authority="human_visual_feedback",
            evidence={"artifact_id": artifact_id, "failure_category": failure_category, "detail": detail},
            receipt=result,
            refusal_reason=failure_category,
            metadata={"reviewer": reviewer, "repeat_count": repeat_count},
        )
    except Exception:
        pass
    return result


def crystallize_human_approved_pattern(
    *,
    audience_archetype: str,
    surface: str,
    visual_grammar: str,
    design_pattern: dict[str, Any],
    reviewer: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Create a reusable visual crystal only from explicit human approval."""
    if not reviewer.strip():
        raise ValueError("A named human reviewer is required to crystallize visual design memory.")
    if not design_pattern:
        raise ValueError("A non-empty design_pattern is required.")

    storage = _storage()
    DurableInferenceStorage, CrystalChainLedger = load_beast()
    metadata = {
        "human_approved": True,
        "audience_archetype": audience_archetype,
        "surface": surface,
        "visual_grammar": visual_grammar,
        "design_pattern": design_pattern,
        "reviewer": reviewer,
        "authority": "representational_context_only",
        "semantic_authority_created": False,
        "release_authority_created": False,
    }
    fingerprint = canonical_digest({"task_class": VISUAL_TASK_CLASS, **metadata})
    existing = next(
        (
            credit for credit in storage.credits.values()
            if credit.task_class == VISUAL_TASK_CLASS
            and credit.repo_fingerprint == fingerprint
            and credit.reuse_state == "active"
        ),
        None,
    )
    if existing is None:
        credit = storage.store_semantic_result(
            task_class=VISUAL_TASK_CLASS,
            repo_fingerprint=fingerprint,
            policy_version="dio_visual_design_memory_v1",
            verified_tests=["human_visual_approval"],
            avoided_tokens_estimate=0,
            confidence=1.0,
            impact_fingerprint_hash=fingerprint,
            evidence_packet_id=str(evidence.get("artifact_id") or fingerprint),
            metadata=metadata,
        )
        CrystalChainLedger(CHAIN_PATH, node_id="dio-visual").append(
            "visual.design_pattern.crystallized",
            credit.credit_id,
            {"credit_id": credit.credit_id, "fingerprint": fingerprint, "reviewer": reviewer},
        )
        created = True
    else:
        credit = existing
        created = False

    residue = None
    try:
        residue = write_memory_residue(
            task=f"Visual design approval for {audience_archetype}/{surface}",
            decision="Human approved reusable representational design pattern.",
            evidence={"credit_id": credit.credit_id, "artifact": evidence},
            tags=["visual-design", "document-studio", "human-approved", "no-authority-transfer"],
        )
    except Exception:
        residue = None

    return {
        "schema": "dio.visual.design_crystal_receipt.v1",
        "state": "crystallized" if created else "existing",
        "credit_id": credit.credit_id,
        "fingerprint": fingerprint,
        "reviewer": reviewer,
        "memory_residue": residue,
        "authority": "representational_context_only",
        "semantic_authority_created": False,
        "release_authority_created": False,
    }
