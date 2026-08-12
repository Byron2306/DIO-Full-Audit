from __future__ import annotations

import copy
from typing import Any

from .models import (
    BUNDLE_SCHEMA,
    CANONICAL_STATES,
    ENGINE_VERSION,
    OBLIGATION_KINDS,
    normalize_space,
    parse_time,
    require_source,
)


def normalize(source: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Normalize extracted candidates without inventing missing legal meaning."""
    source_meta = require_source(source)
    seen: set[str] = set()
    obligations: list[dict[str, Any]] = []

    for candidate in candidates:
        obligation_id = normalize_space(candidate.get("obligation_id"))
        if not obligation_id or obligation_id in seen:
            raise ValueError(f"duplicate/empty obligation candidate: {obligation_id}")
        seen.add(obligation_id)

        declared = candidate.get("declared") or {}
        statement = normalize_space(declared.get("statement"))
        kind = normalize_space(declared.get("kind") or "other")
        if not statement:
            raise ValueError(f"obligation {obligation_id} requires statement")
        if kind not in OBLIGATION_KINDS:
            raise ValueError(f"unsupported obligation kind for {obligation_id}: {kind}")

        due_at = declared.get("due_at")
        expires_at = declared.get("expires_at")
        if due_at:
            parse_time(str(due_at))
        if expires_at:
            parse_time(str(expires_at))

        evidence_requirements = list(dict.fromkeys(
            normalize_space(item)
            for item in declared.get("evidence_requirements") or []
            if normalize_space(item)
        ))
        dependency_refs = list(dict.fromkeys(
            normalize_space(item)
            for item in declared.get("dependency_refs") or []
            if normalize_space(item)
        ))

        obligations.append(
            {
                "obligation_id": obligation_id,
                "source": {
                    "source_id": source_meta["source_id"],
                    "source_ref": source_meta["source_ref"],
                    "sha256": source_meta["sha256"],
                    "locator": normalize_space(candidate.get("source_locator")),
                },
                "statement": statement,
                "raw_text": normalize_space(candidate.get("raw_text")),
                "kind": kind,
                "responsible_party": normalize_space(declared.get("responsible_party")) or None,
                "due_at": due_at,
                "expires_at": expires_at,
                "dependency_refs": dependency_refs,
                "evidence_requirements": evidence_requirements,
                "authority_requirement": normalize_space(declared.get("authority_requirement")) or None,
                "extraction_basis": normalize_space(candidate.get("extraction_basis")),
                "review_required": bool(candidate.get("review_required", True)),
                "evidence_binding_ids": [],
                "status": "NEEDS_REVIEW",
                "status_basis": ["human review remains required"],
            }
        )

    return {
        "schema": BUNDLE_SCHEMA,
        "engine_version": ENGINE_VERSION,
        "source": copy.deepcopy(source_meta),
        "canonical_states": sorted(CANONICAL_STATES),
        "obligations": obligations,
        "deadlines": [],
        "evidence_bindings": [],
        "evaluations": [],
        "human_gate": {
            "state": "NEEDS_YOU",
            "reason": "Owner decides fulfilment, escalation, waiver, acceptance and any consequential action.",
        },
        "authority_created": False,
        "executor_created": False,
        "external_effects": False,
        "fingerprint": None,
    }
