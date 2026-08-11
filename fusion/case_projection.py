from __future__ import annotations

from typing import Any

from products.governed_case import (
    add_evidence,
    add_requirement,
    propose_action,
    raise_challenge,
    record_decision,
    validate_case,
)
from fusion.contracts import validate_assertion


def _record_fusion_ref(case: dict[str, Any], assertion_id: str) -> None:
    ref = f"fusion://{assertion_id}"
    if ref not in case["event_refs"]:
        case["event_refs"].append(ref)


def project_assertion(case: dict[str, Any], assertion: dict[str, Any]) -> dict[str, Any]:
    """Project a canonical fusion assertion into Governed Case v2.

    Projection never upgrades kernel or release authority. Authority flags are
    validated before projection, while execution continues to depend on normal
    Governed Case gates and capability receipts.
    """
    validate_assertion(assertion)
    kind = assertion["assertion_type"]
    issuer = assertion["issuer"]["system_id"]
    subject = assertion["subject"]
    payload = assertion["payload"]
    epi = assertion["epistemic"]
    assertion_id = assertion["assertion_id"]

    if kind in {"evidence", "observation"}:
        add_evidence(
            case,
            kind=f"fusion:{issuer}:{kind}",
            source_ref=str(payload.get("source_ref") or subject["ref"]),
            sha256=payload.get("sha256"),
            observed_at=payload.get("observed_at") or assertion["created_at"],
            effective_at=payload.get("effective_at"),
            expires_at=payload.get("expires_at"),
            authority_grade=epi["authority_grade"] if epi["authority_grade"] != "N/A" else "source_backed",
            trust_state=epi["trust_state"] if epi["trust_state"] != "N/A" else "captured_untrusted",
            freshness_state=epi["freshness_state"] if epi["freshness_state"] != "N/A" else "unknown",
        )

    elif kind == "challenge":
        raise_challenge(
            case,
            target_type=str(payload.get("target_type") or "case"),
            target_id=str(payload.get("target_id") or case["case_id"]),
            challenge_type=str(payload.get("challenge_type") or "alternative_hypothesis"),
            severity=str(payload.get("severity") or "advisory"),
            hypothesis=str(payload.get("hypothesis") or payload.get("summary") or "Fusion challenge"),
            raised_by=issuer,
            evidence_ids=list(payload.get("evidence_ids") or []),
        )

    elif kind == "requirement":
        add_requirement(
            case,
            statement=str(payload.get("statement") or subject["ref"]),
            kind=str(payload.get("kind") or "framework"),
            source_ref=assertion_id,
            mandatory=bool(payload.get("mandatory", True)),
            due_at=payload.get("due_at"),
            expires_at=payload.get("expires_at"),
        )

    elif kind == "capability_request":
        required_gate_ids = list(payload.get("required_gate_ids") or ["generic_executor"])
        if payload.get("external", False) and "external_release" not in required_gate_ids:
            required_gate_ids.append("external_release")
        propose_action(
            case,
            action_type=str(payload.get("capability") or subject["kind"]),
            description=str(payload.get("description") or subject["ref"]),
            risk_tier=str(payload.get("risk_tier") or ("external" if payload.get("external", False) else "reversible_internal")),
            reversibility=str(payload.get("reversibility") or "unknown"),
            required_gate_ids=required_gate_ids,
            proposed_by=issuer,
        )

    elif kind in {"authority", "decision"}:
        record_decision(
            case,
            decision_type=str(payload.get("decision_type") or "gate"),
            verdict=str(payload.get("verdict") or "recorded"),
            actor_id=issuer,
            reasoning_summary=str(payload.get("reasoning_summary") or payload.get("summary") or subject["ref"]),
            evidence_refs=list(payload.get("evidence_refs") or assertion["lineage"]["source_refs"]),
        )

    elif kind == "receipt":
        pass

    _record_fusion_ref(case, assertion_id)
    validate_case(case)
    return case
