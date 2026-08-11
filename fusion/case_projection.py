from __future__ import annotations

from typing import Any

from products.governed_case import add_evidence, add_requirement, raise_challenge, record_decision, validate_case
from fusion.contracts import validate_assertion


def project_assertion(case: dict[str, Any], assertion: dict[str, Any]) -> dict[str, Any]:
    """Project one canonical fusion assertion into Governed Case v2.

    Projection never upgrades kernel or release authority. Those flags remain
    evidence about an upstream authority decision, not authority created here.
    """
    validate_assertion(assertion)
    kind = assertion["assertion_type"]
    issuer = assertion["issuer"]["system_id"]
    subject = assertion["subject"]
    payload = assertion["payload"]
    epi = assertion["epistemic"]
    assertion_id = assertion["assertion_id"]

    if kind in {"evidence", "observation"}:
        row = add_evidence(
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
        row["fusion_assertion_id"] = assertion_id

    elif kind == "challenge":
        target_type = str(payload.get("target_type") or "case")
        target_id = str(payload.get("target_id") or case["case_id"])
        challenge_type = str(payload.get("challenge_type") or "alternative_hypothesis")
        severity = str(payload.get("severity") or "advisory")
        hypothesis = str(payload.get("hypothesis") or payload.get("summary") or "Fusion challenge")
        row = raise_challenge(
            case,
            target_type=target_type,
            target_id=target_id,
            challenge_type=challenge_type,
            severity=severity,
            hypothesis=hypothesis,
            raised_by=issuer,
            evidence_ids=list(payload.get("evidence_ids") or []),
        )
        row["fusion_assertion_id"] = assertion_id

    elif kind in {"requirement", "capability_request"}:
        statement = str(payload.get("statement") or payload.get("capability") or subject["ref"])
        row = add_requirement(
            case,
            statement=statement,
            kind="request" if kind == "capability_request" else str(payload.get("kind") or "framework"),
            source_ref=assertion_id,
            mandatory=bool(payload.get("mandatory", True)),
            due_at=payload.get("due_at"),
            expires_at=payload.get("expires_at"),
        )
        row["fusion_assertion_id"] = assertion_id

    elif kind in {"authority", "decision"}:
        row = record_decision(
            case,
            decision_type=str(payload.get("decision_type") or "gate"),
            verdict=str(payload.get("verdict") or "recorded"),
            actor_id=issuer,
            reasoning_summary=str(payload.get("reasoning_summary") or payload.get("summary") or subject["ref"]),
            evidence_refs=list(payload.get("evidence_refs") or assertion["lineage"]["source_refs"]),
        )
        row["fusion_assertion_id"] = assertion_id
        row["kernel_authorized_observed"] = bool(assertion["authority"]["kernel_authorized"])
        row["external_release_authorized_observed"] = bool(assertion["authority"]["external_release_authorized"])

    elif kind == "receipt":
        ref = f"fusion://{assertion_id}"
        if ref not in case["event_refs"]:
            case["event_refs"].append(ref)

    validate_case(case)
    return case
