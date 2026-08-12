from __future__ import annotations

from typing import Any

from .models import (
    EVIDENCE_FRESHNESS_STATES,
    EVIDENCE_TRUST_STATES,
    normalize_space,
    stable_id,
)


def bind_evidence(bundle: dict[str, Any], evidence_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bind explicitly addressed evidence records to obligations.

    Evidence is never semantically auto-matched in v0.1. Each record must name
    one or more obligation IDs. This keeps the reusable engine deterministic and
    avoids turning similarity into fulfilment truth.
    """
    obligations = {row["obligation_id"]: row for row in bundle.get("obligations") or []}
    bindings: list[dict[str, Any]] = []
    seen: set[str] = set()

    for record in evidence_records:
        evidence_id = normalize_space(record.get("evidence_id"))
        if not evidence_id:
            raise ValueError("evidence record requires evidence_id")
        obligation_ids = list(dict.fromkeys(
            normalize_space(item)
            for item in record.get("obligation_ids") or []
            if normalize_space(item)
        ))
        if not obligation_ids:
            raise ValueError(f"evidence {evidence_id} requires explicit obligation_ids")
        missing = [item for item in obligation_ids if item not in obligations]
        if missing:
            raise ValueError(f"evidence {evidence_id} references unknown obligations: {missing}")

        relation = normalize_space(record.get("relation") or "supports")
        if relation not in {"supports", "contradicts"}:
            raise ValueError("obligation evidence relation must be supports or contradicts")
        trust_state = normalize_space(record.get("trust_state") or "captured_untrusted")
        freshness_state = normalize_space(record.get("freshness_state") or "unknown")
        if trust_state not in EVIDENCE_TRUST_STATES:
            raise ValueError(f"unsupported evidence trust_state: {trust_state}")
        if freshness_state not in EVIDENCE_FRESHNESS_STATES:
            raise ValueError(f"unsupported evidence freshness_state: {freshness_state}")

        evidence_kind = normalize_space(record.get("evidence_kind") or record.get("kind") or "other")
        source_ref = normalize_space(record.get("source_ref")) or None
        for obligation_id in obligation_ids:
            binding_id = stable_id("OBIND", obligation_id, evidence_id, relation, evidence_kind)
            if binding_id in seen:
                continue
            seen.add(binding_id)
            row = {
                "binding_id": binding_id,
                "obligation_id": obligation_id,
                "evidence_id": evidence_id,
                "evidence_kind": evidence_kind,
                "source_ref": source_ref,
                "relation": relation,
                "trust_state": trust_state,
                "freshness_state": freshness_state,
            }
            bindings.append(row)
            obligation = obligations[obligation_id]
            if binding_id not in obligation["evidence_binding_ids"]:
                obligation["evidence_binding_ids"].append(binding_id)

    bundle["evidence_bindings"] = bindings
    return bindings
