from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

CASE_SCHEMA = "dio.governed_case.v2"
CLAIM_STATES = {"UNVERIFIED", "SUPPORTED", "CONTESTED", "REFUTED"}
GATE_STATES = {"allow", "refuse", "needs_you", "needs_evidence"}


def timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(str(part or "") for part in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16].upper()}"


def claim_fingerprint(statement: str) -> str:
    normalized = " ".join(str(statement).split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _index(rows: Iterable[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): row for row in rows if row.get(key)}


def _append_unique(row: dict[str, Any], field: str, value: str) -> None:
    values = row.setdefault(field, [])
    if value not in values:
        values.append(value)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def source_evidence(source: dict[str, Any], source_path: Path, case_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    fallback_ref = str((source.get("source") or {}).get("path") or source_path)
    for index, item in enumerate(source.get("evidence") or [], start=1):
        evidence_id = str(item.get("evidence_id") or stable_id("EVID", case_id, index, item.get("title")))
        raw_hash = str(item.get("sha256") or item.get("hash") or "")
        sha256 = raw_hash if len(raw_hash) == 64 and all(ch in "0123456789abcdefABCDEF" for ch in raw_hash) else None
        rows.append(
            {
                "evidence_id": evidence_id,
                "kind": str(item.get("source_type") or item.get("kind") or "source_record"),
                "source_ref": str(item.get("source_path") or item.get("source_ref") or fallback_ref),
                "sha256": sha256,
                "observed_at": item.get("date_observed") or item.get("observed_at"),
                "effective_at": item.get("effective_at"),
                "expires_at": item.get("expires_at"),
                "authority_grade": str(item.get("authority_grade") or "source_backed"),
                "trust_state": str(item.get("trust_state") or "captured_untrusted"),
                "freshness_state": str(item.get("freshness_state") or "unknown"),
                "supports_claim_ids": [],
                "contradicts_claim_ids": [],
                "supports_requirement_ids": [],
            }
        )
    return rows


def new_case(
    *,
    product: str,
    job_id: str,
    source: dict[str, Any],
    source_path: Path,
    evidence_inputs: list[str],
    expected_outputs: list[str],
    required_authorities: list[str],
    intake_state: str = "pending",
    framework_ids: list[str] | None = None,
    jurisdiction_ids: list[str] | None = None,
    subject_ref: str | None = None,
    world_state_ref: str | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    now = now or timestamp()
    case_id = stable_id("CASE", product, job_id)
    intake_gate = "allow" if intake_state == "approved" else "refuse" if intake_state == "rejected" else "needs_you"
    status = "blocked" if intake_state == "rejected" else "evidence_collection" if intake_state == "approved" else "intake_pending"
    authorities = [str(value) for value in required_authorities]
    requirements = [
        {
            "requirement_id": stable_id("REQ", case_id, statement),
            "statement": str(statement),
            "kind": "evidence_input",
            "source_ref": None,
            "mandatory": True,
            "state": "evidence_needed",
            "claim_ids": [],
            "evidence_ids": [],
            "dependency_ids": [],
            "owner_actor_id": None,
            "due_at": None,
            "expires_at": None,
        }
        for statement in evidence_inputs
    ]
    outputs = [
        {
            "output_id": stable_id("OUT", case_id, output),
            "kind": str(output),
            "state": "planned",
            "artifact_ref": None,
            "sha256": None,
        }
        for output in expected_outputs
    ]
    source_meta = source.get("source") or {}
    case = {
        "schema": CASE_SCHEMA,
        "case_id": case_id,
        "product": product,
        "status": status,
        "created_at": now,
        "updated_at": now,
        "scope": {
            "framework_ids": list(dict.fromkeys(framework_ids or [])),
            "jurisdiction_ids": list(dict.fromkeys(jurisdiction_ids or [])),
            "subject_ref": subject_ref,
            "world_state_ref": world_state_ref,
        },
        "lineage": {
            "campaign_id": (source.get("attribution") or {}).get("campaign_id"),
            "lead_id": source_meta.get("lead_id"),
            "conversation_id": source_meta.get("conversation_id") or source_meta.get("thread_ref"),
            "job_id": job_id,
            "transaction_id": None,
            "parent_case_id": None,
            "revision_of_case_id": None,
        },
        "actors": [],
        "requirements": requirements,
        "claims": [],
        "evidence": source_evidence(source, source_path, case_id),
        "challenges": [],
        "exceptions": [],
        "deadlines": [],
        "gates": [
            {
                "gate_id": "intake_authority",
                "state": intake_gate,
                "reason": "Explicit intake review is required before product-specific processing.",
                "required_authority": authorities[0] if authorities else None,
                "required_evidence_ids": [],
                "decision_id": None,
                "decided_at": now if intake_gate in {"allow", "refuse"} else None,
            },
            {
                "gate_id": "generic_executor",
                "state": "refuse",
                "reason": "The shared product platform has no generic product executor. A product-specific runner and validation receipt are required.",
                "required_authority": None,
                "required_evidence_ids": [],
                "decision_id": None,
                "decided_at": now,
            },
            {
                "gate_id": "external_release",
                "state": "needs_you",
                "reason": "External release requires completed processing, review evidence, and explicit authorised human release.",
                "required_authority": authorities[-1] if authorities else None,
                "required_evidence_ids": [],
                "decision_id": None,
                "decided_at": None,
            },
        ],
        "actions": [],
        "decisions": [],
        "outputs": outputs,
        "event_refs": [],
    }
    validate_case(case)
    return case


def add_actor(case: dict[str, Any], *, actor_id: str, actor_type: str, role: str, authority_scope: list[str]) -> dict[str, Any]:
    if actor_type not in {"human", "system", "service", "organisation"}:
        raise ValueError("Unsupported actor type.")
    actors = _index(case["actors"], "actor_id")
    if actor_id in actors:
        raise ValueError(f"Actor already exists: {actor_id}")
    row = {"actor_id": actor_id, "actor_type": actor_type, "role": role, "authority_scope": list(dict.fromkeys(authority_scope))}
    case["actors"].append(row)
    case["updated_at"] = timestamp()
    return row


def add_requirement(
    case: dict[str, Any], *, statement: str, kind: str, source_ref: str | None = None, mandatory: bool = True,
    dependency_ids: list[str] | None = None, owner_actor_id: str | None = None, due_at: str | None = None,
    expires_at: str | None = None,
) -> dict[str, Any]:
    if kind not in {"framework", "control", "contract", "obligation", "policy", "request", "evidence_input"}:
        raise ValueError("Unsupported requirement kind.")
    requirement_id = stable_id("REQ", case["case_id"], kind, source_ref, statement)
    existing = _index(case["requirements"], "requirement_id")
    if requirement_id in existing:
        return existing[requirement_id]
    dependencies = list(dict.fromkeys(dependency_ids or []))
    known_requirements = _index(case["requirements"], "requirement_id")
    unknown_dependencies = [item for item in dependencies if item not in known_requirements]
    if unknown_dependencies:
        raise ValueError(f"Unknown requirement dependencies: {unknown_dependencies}")
    row = {
        "requirement_id": requirement_id,
        "statement": statement,
        "kind": kind,
        "source_ref": source_ref,
        "mandatory": bool(mandatory),
        "state": "evidence_needed",
        "claim_ids": [],
        "evidence_ids": [],
        "dependency_ids": dependencies,
        "owner_actor_id": owner_actor_id,
        "due_at": due_at,
        "expires_at": expires_at,
    }
    case["requirements"].append(row)
    if due_at:
        add_deadline(case, subject_type="requirement", subject_id=requirement_id, kind="response", due_at=due_at)
    if expires_at:
        add_deadline(case, subject_type="requirement", subject_id=requirement_id, kind="expiry", due_at=expires_at)
    case["updated_at"] = timestamp()
    return row


def add_claim(
    case: dict[str, Any], *, statement: str, requirement_ids: list[str] | None = None,
    parent_claim_id: str | None = None, lineage_id: str | None = None,
) -> dict[str, Any]:
    requirements = _index(case["requirements"], "requirement_id")
    requested_requirements = list(dict.fromkeys(requirement_ids or []))
    missing = [item for item in requested_requirements if item not in requirements]
    if missing:
        raise ValueError(f"Unknown claim requirement IDs: {missing}")
    claims = _index(case["claims"], "claim_id")
    parent = claims.get(parent_claim_id) if parent_claim_id else None
    if parent_claim_id and not parent:
        raise ValueError(f"Unknown parent claim: {parent_claim_id}")
    fingerprint = claim_fingerprint(statement)
    inherited_lineage = str(parent["lineage_id"]) if parent else None
    lineage_id = lineage_id or inherited_lineage or stable_id("LINEAGE", case["case_id"], statement)
    claim_id = stable_id("CLAIM", case["case_id"], lineage_id, fingerprint, parent_claim_id)
    if claim_id in claims:
        return claims[claim_id]
    now = timestamp()
    row = {
        "claim_id": claim_id,
        "lineage_id": lineage_id,
        "statement": statement,
        "fingerprint": fingerprint,
        "epistemic_state": "UNVERIFIED",
        "parent_claim_id": parent_claim_id,
        "requirement_ids": requested_requirements,
        "evidence_ids": [],
        "challenge_ids": [],
        "created_at": now,
        "updated_at": now,
    }
    case["claims"].append(row)
    for requirement_id in requested_requirements:
        _append_unique(requirements[requirement_id], "claim_ids", claim_id)
    case["updated_at"] = now
    return row


def add_evidence(
    case: dict[str, Any], *, kind: str, source_ref: str, sha256: str | None = None,
    observed_at: str | None = None, effective_at: str | None = None, expires_at: str | None = None,
    authority_grade: str = "source_backed", trust_state: str = "captured_untrusted",
    freshness_state: str = "unknown",
) -> dict[str, Any]:
    if authority_grade not in {"self_asserted", "source_backed", "independent", "authoritative"}:
        raise ValueError("Unsupported evidence authority grade.")
    if trust_state not in {"captured_untrusted", "trusted_for_review", "rejected", "quarantined"}:
        raise ValueError("Unsupported evidence trust state.")
    if freshness_state not in {"unknown", "current", "stale", "expired"}:
        raise ValueError("Unsupported freshness state.")
    if sha256 and (len(sha256) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in sha256)):
        raise ValueError("Evidence sha256 must be a 64-character hexadecimal digest.")
    evidence_id = stable_id("EVID", case["case_id"], kind, source_ref, sha256, observed_at)
    existing = _index(case["evidence"], "evidence_id")
    if evidence_id in existing:
        return existing[evidence_id]
    row = {
        "evidence_id": evidence_id,
        "kind": kind,
        "source_ref": source_ref,
        "sha256": sha256.lower() if sha256 else None,
        "observed_at": observed_at,
        "effective_at": effective_at,
        "expires_at": expires_at,
        "authority_grade": authority_grade,
        "trust_state": trust_state,
        "freshness_state": freshness_state,
        "supports_claim_ids": [],
        "contradicts_claim_ids": [],
        "supports_requirement_ids": [],
    }
    case["evidence"].append(row)
    if expires_at:
        add_deadline(case, subject_type="evidence", subject_id=evidence_id, kind="expiry", due_at=expires_at)
    case["updated_at"] = timestamp()
    return row


def link_evidence(
    case: dict[str, Any], *, evidence_id: str, claim_id: str | None = None,
    requirement_id: str | None = None, relation: str = "supports",
) -> None:
    evidence = _index(case["evidence"], "evidence_id")
    if evidence_id not in evidence:
        raise ValueError(f"Unknown evidence: {evidence_id}")
    claims = _index(case["claims"], "claim_id")
    requirements = _index(case["requirements"], "requirement_id")
    row = evidence[evidence_id]
    if relation not in {"supports", "contradicts"}:
        raise ValueError("Evidence relation must be supports or contradicts.")
    if claim_id:
        if claim_id not in claims:
            raise ValueError(f"Unknown claim: {claim_id}")
        field = "supports_claim_ids" if relation == "supports" else "contradicts_claim_ids"
        _append_unique(row, field, claim_id)
        _append_unique(claims[claim_id], "evidence_ids", evidence_id)
    if requirement_id:
        if requirement_id not in requirements:
            raise ValueError(f"Unknown requirement: {requirement_id}")
        if relation != "supports":
            raise ValueError("Requirement links currently accept supporting evidence only; use a challenge for contradiction.")
        _append_unique(row, "supports_requirement_ids", requirement_id)
        _append_unique(requirements[requirement_id], "evidence_ids", evidence_id)
    recalculate_epistemic_state(case)
    recalculate_requirement_state(case)
    case["updated_at"] = timestamp()


def raise_challenge(
    case: dict[str, Any], *, target_type: str, target_id: str, challenge_type: str,
    severity: str, hypothesis: str, raised_by: str, evidence_ids: list[str] | None = None,
) -> dict[str, Any]:
    if target_type not in {"case", "requirement", "claim", "evidence", "gate", "action"}:
        raise ValueError("Unsupported challenge target type.")
    if challenge_type not in {"contradiction", "missing_evidence", "stale_evidence", "authority", "scope", "alternative_hypothesis", "duplication", "world_state"}:
        raise ValueError("Unsupported challenge type.")
    if severity not in {"advisory", "material", "blocking"}:
        raise ValueError("Unsupported challenge severity.")
    known_evidence = _index(case["evidence"], "evidence_id")
    evidence_ids = list(dict.fromkeys(evidence_ids or []))
    missing = [item for item in evidence_ids if item not in known_evidence]
    if missing:
        raise ValueError(f"Unknown challenge evidence IDs: {missing}")
    challenge_id = stable_id("CHAL", case["case_id"], target_type, target_id, challenge_type, hypothesis)
    existing = _index(case["challenges"], "challenge_id")
    if challenge_id in existing:
        return existing[challenge_id]
    now = timestamp()
    row = {
        "challenge_id": challenge_id,
        "target_type": target_type,
        "target_id": target_id,
        "challenge_type": challenge_type,
        "severity": severity,
        "hypothesis": hypothesis,
        "evidence_ids": evidence_ids,
        "state": "open",
        "raised_by": raised_by,
        "raised_at": now,
        "resolved_by": None,
        "resolved_at": None,
        "resolution": None,
    }
    case["challenges"].append(row)
    if target_type == "claim":
        claims = _index(case["claims"], "claim_id")
        if target_id not in claims:
            raise ValueError(f"Unknown claim challenge target: {target_id}")
        _append_unique(claims[target_id], "challenge_ids", challenge_id)
    case["updated_at"] = now
    recalculate_epistemic_state(case)
    return row


def resolve_challenge(case: dict[str, Any], *, challenge_id: str, state: str, resolved_by: str, resolution: str) -> dict[str, Any]:
    if state not in {"accepted", "dismissed", "resolved"}:
        raise ValueError("Challenge resolution state must be accepted, dismissed, or resolved.")
    challenges = _index(case["challenges"], "challenge_id")
    if challenge_id not in challenges:
        raise ValueError(f"Unknown challenge: {challenge_id}")
    row = challenges[challenge_id]
    row.update({"state": state, "resolved_by": resolved_by, "resolved_at": timestamp(), "resolution": resolution})
    recalculate_epistemic_state(case)
    case["updated_at"] = timestamp()
    return row


def record_decision(
    case: dict[str, Any], *, decision_type: str, verdict: str, actor_id: str,
    reasoning_summary: str, evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    if decision_type not in {"requirement", "claim", "gate", "exception", "action", "release", "closeout"}:
        raise ValueError("Unsupported decision type.")
    now = timestamp()
    decision_id = stable_id("DEC", case["case_id"], decision_type, verdict, actor_id, now, reasoning_summary)
    row = {
        "decision_id": decision_id,
        "decision_type": decision_type,
        "verdict": verdict,
        "actor_id": actor_id,
        "reasoning_summary": reasoning_summary,
        "evidence_refs": list(dict.fromkeys(evidence_refs or [])),
        "created_at": now,
    }
    case["decisions"].append(row)
    case["updated_at"] = now
    return row


def set_gate(
    case: dict[str, Any], *, gate_id: str, state: str, reason: str,
    actor_id: str | None = None, required_evidence_ids: list[str] | None = None,
) -> dict[str, Any]:
    if state not in GATE_STATES:
        raise ValueError("Unsupported gate state.")
    gates = _index(case["gates"], "gate_id")
    if gate_id not in gates:
        raise ValueError(f"Unknown gate: {gate_id}")
    evidence = _index(case["evidence"], "evidence_id")
    requested = list(dict.fromkeys(required_evidence_ids or gates[gate_id].get("required_evidence_ids") or []))
    missing = [item for item in requested if item not in evidence]
    if missing:
        raise ValueError(f"Gate references unknown evidence: {missing}")
    if state == "allow":
        unusable = [item for item in requested if evidence[item]["trust_state"] != "trusted_for_review" or evidence[item]["freshness_state"] in {"stale", "expired"}]
        if unusable:
            raise ValueError(f"Cannot ALLOW gate with untrusted/stale evidence: {unusable}")
        required_authority = gates[gate_id].get("required_authority")
        if required_authority and not actor_id:
            raise ValueError(f"Gate {gate_id} requires an explicit authority actor.")
    decision_id = None
    now = timestamp()
    if actor_id:
        decision = record_decision(
            case,
            decision_type="gate",
            verdict=state.upper(),
            actor_id=actor_id,
            reasoning_summary=reason,
            evidence_refs=requested,
        )
        decision_id = decision["decision_id"]
    gates[gate_id].update({
        "state": state,
        "reason": reason,
        "required_evidence_ids": requested,
        "decision_id": decision_id,
        "decided_at": now if state in {"allow", "refuse"} else None,
    })
    case["updated_at"] = now
    return gates[gate_id]


def add_deadline(case: dict[str, Any], *, subject_type: str, subject_id: str, kind: str, due_at: str) -> dict[str, Any]:
    if subject_type not in {"case", "requirement", "evidence", "exception", "action"}:
        raise ValueError("Unsupported deadline subject type.")
    if kind not in {"submission", "renewal", "review", "expiry", "response", "other"}:
        raise ValueError("Unsupported deadline kind.")
    _parse_time(due_at)
    deadline_id = stable_id("DEADLINE", case["case_id"], subject_type, subject_id, kind, due_at)
    existing = _index(case["deadlines"], "deadline_id")
    if deadline_id in existing:
        return existing[deadline_id]
    row = {"deadline_id": deadline_id, "subject_type": subject_type, "subject_id": subject_id, "kind": kind, "due_at": due_at, "state": "open"}
    case["deadlines"].append(row)
    case["updated_at"] = timestamp()
    return row


def propose_action(
    case: dict[str, Any], *, action_type: str, description: str, risk_tier: str,
    reversibility: str, required_gate_ids: list[str], proposed_by: str,
) -> dict[str, Any]:
    if risk_tier not in {"read_only", "reversible_internal", "consequential_internal", "external", "irreversible"}:
        raise ValueError("Unsupported action risk tier.")
    if reversibility not in {"reversible", "compensatable", "irreversible", "unknown"}:
        raise ValueError("Unsupported reversibility value.")
    gates = _index(case["gates"], "gate_id")
    required_gate_ids = list(dict.fromkeys(required_gate_ids))
    missing = [item for item in required_gate_ids if item not in gates]
    if missing:
        raise ValueError(f"Unknown action gates: {missing}")
    now = timestamp()
    action_id = stable_id("ACTION", case["case_id"], action_type, description, proposed_by)
    existing = _index(case["actions"], "action_id")
    if action_id in existing:
        return existing[action_id]
    state = "approved" if all(gates[item]["state"] == "allow" for item in required_gate_ids) else "blocked"
    row = {
        "action_id": action_id,
        "action_type": action_type,
        "description": description,
        "risk_tier": risk_tier,
        "reversibility": reversibility,
        "state": state,
        "required_gate_ids": required_gate_ids,
        "capability_lease_id": None,
        "proposed_by": proposed_by,
        "proposed_at": now,
        "executed_at": None,
        "receipt_ref": None,
    }
    case["actions"].append(row)
    case["updated_at"] = now
    derive_case_status(case)
    return row


def record_action_receipt(
    case: dict[str, Any], *, action_id: str, receipt_ref: str, capability_lease_id: str | None = None,
    success: bool = True,
) -> dict[str, Any]:
    actions = _index(case["actions"], "action_id")
    if action_id not in actions:
        raise ValueError(f"Unknown action: {action_id}")
    action = actions[action_id]
    gates = _index(case["gates"], "gate_id")
    if action["state"] != "approved":
        raise ValueError("Only an approved action may receive an execution receipt.")
    if any(gates[gate_id]["state"] != "allow" for gate_id in action["required_gate_ids"]):
        raise ValueError("Action gate state changed; execution receipt cannot be accepted.")
    action.update({
        "state": "executed" if success else "failed",
        "capability_lease_id": capability_lease_id,
        "executed_at": timestamp(),
        "receipt_ref": receipt_ref,
    })
    _append_unique(case, "event_refs", receipt_ref)
    case["updated_at"] = timestamp()
    derive_case_status(case)
    return action


def refresh_temporal_state(case: dict[str, Any], *, now: str | None = None) -> None:
    current = _parse_time(now or timestamp())
    assert current is not None
    for evidence in case["evidence"]:
        expiry = _parse_time(evidence.get("expires_at"))
        if expiry and current >= expiry:
            evidence["freshness_state"] = "expired"
    for requirement in case["requirements"]:
        expiry = _parse_time(requirement.get("expires_at"))
        if expiry and current >= expiry and requirement["state"] not in {"waived", "refused"}:
            requirement["state"] = "expired"
    for deadline in case["deadlines"]:
        if deadline["state"] in {"satisfied", "cancelled"}:
            continue
        due = _parse_time(deadline["due_at"])
        if due and current > due:
            deadline["state"] = "overdue"
        elif due and 0 <= (due - current).total_seconds() <= 86400:
            deadline["state"] = "due"
    recalculate_epistemic_state(case)
    recalculate_requirement_state(case)
    derive_case_status(case)
    case["updated_at"] = current.isoformat()


def recalculate_epistemic_state(case: dict[str, Any]) -> None:
    evidence = _index(case["evidence"], "evidence_id")
    challenges = _index(case["challenges"], "challenge_id")
    for claim in case["claims"]:
        supporting = [
            evidence[item] for item in claim["evidence_ids"]
            if item in evidence and claim["claim_id"] in evidence[item].get("supports_claim_ids", [])
            and evidence[item]["trust_state"] == "trusted_for_review"
            and evidence[item]["freshness_state"] not in {"stale", "expired"}
        ]
        contradicting = [
            evidence[item] for item in claim["evidence_ids"]
            if item in evidence and claim["claim_id"] in evidence[item].get("contradicts_claim_ids", [])
            and evidence[item]["trust_state"] == "trusted_for_review"
        ]
        open_material = [
            challenges[item] for item in claim["challenge_ids"]
            if item in challenges and challenges[item]["state"] == "open" and challenges[item]["severity"] in {"material", "blocking"}
        ]
        if contradicting:
            claim["epistemic_state"] = "REFUTED"
        elif open_material:
            claim["epistemic_state"] = "CONTESTED"
        elif supporting:
            claim["epistemic_state"] = "SUPPORTED"
        else:
            claim["epistemic_state"] = "UNVERIFIED"
        claim["updated_at"] = timestamp()


def recalculate_requirement_state(case: dict[str, Any]) -> None:
    evidence = _index(case["evidence"], "evidence_id")
    claims = _index(case["claims"], "claim_id")
    challenges = case["challenges"]
    for requirement in case["requirements"]:
        if requirement["state"] in {"waived", "refused", "expired"}:
            continue
        blocking = any(
            row["target_type"] == "requirement" and row["target_id"] == requirement["requirement_id"]
            and row["state"] == "open" and row["severity"] in {"material", "blocking"}
            for row in challenges
        )
        if blocking:
            requirement["state"] = "challenged"
            continue
        usable_evidence = [
            evidence[item] for item in requirement["evidence_ids"]
            if item in evidence and evidence[item]["trust_state"] == "trusted_for_review"
            and evidence[item]["freshness_state"] not in {"stale", "expired"}
        ]
        supported_claims = [claims[item] for item in requirement["claim_ids"] if item in claims and claims[item]["epistemic_state"] == "SUPPORTED"]
        dependencies = _index(case["requirements"], "requirement_id")
        deps_satisfied = all(dependencies[item]["state"] in {"supported", "satisfied", "waived"} for item in requirement["dependency_ids"] if item in dependencies)
        if (usable_evidence or supported_claims) and deps_satisfied:
            requirement["state"] = "supported"
        else:
            requirement["state"] = "evidence_needed"


def derive_case_status(case: dict[str, Any]) -> str:
    gates = _index(case["gates"], "gate_id")
    if gates.get("intake_authority", {}).get("state") == "refuse":
        case["status"] = "blocked"
    elif any(row["state"] == "open" and row["severity"] == "blocking" for row in case["challenges"]):
        case["status"] = "review"
    elif any(row["state"] == "approved" for row in case["actions"]):
        case["status"] = "action_ready"
    elif case["claims"] or any(row["state"] in {"supported", "challenged"} for row in case["requirements"]):
        case["status"] = "review"
    elif gates.get("intake_authority", {}).get("state") == "allow":
        case["status"] = "evidence_collection"
    else:
        case["status"] = "intake_pending"
    if gates.get("external_release", {}).get("state") == "allow" and case["outputs"] and all(row["state"] in {"released", "superseded"} for row in case["outputs"]):
        case["status"] = "closed"
    return case["status"]


def validate_case(case: dict[str, Any]) -> None:
    if case.get("schema") != CASE_SCHEMA:
        raise ValueError(f"Expected {CASE_SCHEMA}.")
    id_specs = [
        ("actors", "actor_id"), ("requirements", "requirement_id"), ("claims", "claim_id"),
        ("evidence", "evidence_id"), ("challenges", "challenge_id"), ("exceptions", "exception_id"),
        ("deadlines", "deadline_id"), ("gates", "gate_id"), ("actions", "action_id"),
        ("decisions", "decision_id"), ("outputs", "output_id"),
    ]
    for field, key in id_specs:
        values = [str(row[key]) for row in case.get(field, [])]
        if len(values) != len(set(values)):
            raise ValueError(f"Duplicate {key} in {field}.")
    claims = _index(case["claims"], "claim_id")
    requirements = _index(case["requirements"], "requirement_id")
    evidence = _index(case["evidence"], "evidence_id")
    gates = _index(case["gates"], "gate_id")
    for claim in case["claims"]:
        if claim["epistemic_state"] not in CLAIM_STATES:
            raise ValueError(f"Unsupported claim state: {claim['epistemic_state']}")
        if claim["epistemic_state"] == "SUPPORTED":
            usable = [
                evidence[item] for item in claim["evidence_ids"] if item in evidence
                and claim["claim_id"] in evidence[item].get("supports_claim_ids", [])
                and evidence[item]["trust_state"] == "trusted_for_review"
                and evidence[item]["freshness_state"] not in {"stale", "expired"}
            ]
            if not usable:
                raise ValueError(f"SUPPORTED claim lacks current trusted evidence: {claim['claim_id']}")
        if claim.get("parent_claim_id") and claim["parent_claim_id"] not in claims:
            raise ValueError(f"Claim parent not found: {claim['parent_claim_id']}")
        if any(item not in requirements for item in claim["requirement_ids"]):
            raise ValueError(f"Claim references unknown requirement: {claim['claim_id']}")
    for gate in case["gates"]:
        if gate["state"] not in GATE_STATES:
            raise ValueError(f"Unsupported gate state: {gate['state']}")
        if gate["state"] == "allow":
            for evidence_id in gate["required_evidence_ids"]:
                if evidence_id not in evidence:
                    raise ValueError(f"ALLOW gate references missing evidence: {gate['gate_id']}")
                row = evidence[evidence_id]
                if row["trust_state"] != "trusted_for_review" or row["freshness_state"] in {"stale", "expired"}:
                    raise ValueError(f"ALLOW gate relies on unusable evidence: {gate['gate_id']}")
    for action in case["actions"]:
        missing = [item for item in action["required_gate_ids"] if item not in gates]
        if missing:
            raise ValueError(f"Action references unknown gates: {missing}")
        if action["state"] in {"approved", "executed"} and any(gates[item]["state"] != "allow" for item in action["required_gate_ids"]):
            raise ValueError(f"Action {action['action_id']} bypasses a non-ALLOW gate.")
        if action["state"] == "executed" and not action.get("receipt_ref"):
            raise ValueError(f"Executed action lacks receipt: {action['action_id']}")
    released = [row for row in case["outputs"] if row["state"] == "released"]
    if released and gates.get("external_release", {}).get("state") != "allow":
        raise ValueError("Released output exists without external_release ALLOW.")


def clone_case(case: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(case)


def canonical_hash(case: dict[str, Any]) -> str:
    validate_case(case)
    raw = json.dumps(case, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
