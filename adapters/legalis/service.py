from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

LEGALIS_DECISION_SCHEMA = "dio.legalis.decision_receipt.v1"
LEGALIS_IDENTITY_SCHEMA = "dio.legalis.legal_identity.v1"
LEGALIS_REGISTRY_SCHEMA = "dio.legalis.requirement_registry.v1"
VERDICTS = {"ALLOW", "REFUSE", "NEEDS_YOU"}
AUTHORITY_GRADES = {"self_asserted": 0, "source_backed": 1, "independent": 2, "authoritative": 3}


class LegalisError(ValueError):
    pass


def timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(str(part or "") for part in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16].upper()}"


def load_json(path: str | Path) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve()
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LegalisError(f"Cannot load JSON {resolved}: {exc}") from exc
    if not isinstance(payload, dict):
        raise LegalisError(f"Expected an object in {resolved}.")
    return payload


def _get_path(payload: Mapping[str, Any], dotted_path: str) -> Any:
    current: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _operator_value(operator_checks: Mapping[str, Any], key: str) -> tuple[bool, Any, str | None]:
    if key not in operator_checks:
        return False, None, None
    raw = operator_checks[key]
    if isinstance(raw, Mapping):
        return True, raw.get("value"), str(raw.get("receipt_ref")) if raw.get("receipt_ref") else None
    return True, raw, None


def _validate_verdict(value: str | None, *, default: str) -> str:
    verdict = str(value or default).upper()
    if verdict not in VERDICTS:
        raise LegalisError(f"Unsupported Legalis verdict in registry: {verdict}")
    return verdict


def validate_identity(identity: Mapping[str, Any]) -> None:
    if identity.get("schema") != LEGALIS_IDENTITY_SCHEMA:
        raise LegalisError("Unsupported legal identity schema.")
    if not identity.get("identity_id"):
        raise LegalisError("Legal identity requires identity_id.")
    if "registered_entity" not in identity:
        raise LegalisError("Legal identity must explicitly state registered_entity.")


def validate_registry(registry: Mapping[str, Any]) -> None:
    if registry.get("schema") != LEGALIS_REGISTRY_SCHEMA:
        raise LegalisError("Unsupported Legalis requirement registry schema.")
    capabilities = registry.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        raise LegalisError("Requirement registry requires at least one capability.")
    seen: set[str] = set()
    for capability in capabilities:
        capability_id = str(capability.get("capability_id") or "")
        if not capability_id:
            raise LegalisError("Capability requires capability_id.")
        if capability_id in seen:
            raise LegalisError(f"Duplicate capability_id: {capability_id}")
        seen.add(capability_id)
        for requirement in capability.get("requirements") or []:
            if not requirement.get("requirement_id"):
                raise LegalisError(f"Capability {capability_id} contains a requirement without requirement_id.")
            kind = str(requirement.get("kind") or "")
            if kind not in {"identity_field", "evidence", "operator_check", "deadline"}:
                raise LegalisError(f"Unsupported requirement kind: {kind}")


def _capability(registry: Mapping[str, Any], capability_id: str) -> Mapping[str, Any]:
    for row in registry.get("capabilities") or []:
        if row.get("capability_id") == capability_id:
            return row
    raise LegalisError(f"Unknown capability: {capability_id}")


def _result(requirement: Mapping[str, Any], verdict: str, state: str, reason: str, **extra: Any) -> dict[str, Any]:
    row = {
        "requirement_id": str(requirement["requirement_id"]),
        "kind": str(requirement["kind"]),
        "state": state,
        "verdict": verdict,
        "reason": reason,
        "source_ref": requirement.get("source_ref"),
    }
    row.update(extra)
    return row


def _evaluate_identity(requirement: Mapping[str, Any], identity: Mapping[str, Any]) -> dict[str, Any]:
    field = str(requirement.get("field") or "")
    if not field:
        raise LegalisError(f"Identity requirement {requirement['requirement_id']} has no field.")
    value = _get_path(identity, field)
    missing = value is None or value == ""
    if missing:
        verdict = _validate_verdict(requirement.get("missing_verdict"), default="NEEDS_YOU")
        return _result(requirement, verdict, "missing", f"Identity field is not recorded: {field}", observed_value=None)

    operator = str(requirement.get("operator") or "present")
    expected = requirement.get("value")
    accepted = requirement.get("accepted_values") or []
    if operator == "present":
        matched = True
    elif operator == "equals":
        matched = value == expected
    elif operator == "in":
        matched = value in accepted
    else:
        raise LegalisError(f"Unsupported identity operator: {operator}")

    if matched:
        return _result(requirement, "ALLOW", "satisfied", f"Recorded identity prerequisite satisfied: {field}", observed_value=value)
    verdict = _validate_verdict(requirement.get("failure_verdict"), default="REFUSE")
    return _result(requirement, verdict, "mismatch", f"Recorded identity prerequisite does not match: {field}", observed_value=value)


def _evaluate_evidence(
    requirement: Mapping[str, Any], evidence: list[Mapping[str, Any]], current: datetime
) -> dict[str, Any]:
    kind = str(requirement.get("evidence_kind") or "")
    if not kind:
        raise LegalisError(f"Evidence requirement {requirement['requirement_id']} has no evidence_kind.")
    candidates = [row for row in evidence if str(row.get("kind") or "") == kind]
    if not candidates:
        verdict = _validate_verdict(requirement.get("missing_verdict"), default="NEEDS_YOU")
        return _result(requirement, verdict, "missing", f"Required evidence is not present: {kind}", evidence_ids=[])

    minimum = str(requirement.get("minimum_authority_grade") or "source_backed")
    if minimum not in AUTHORITY_GRADES:
        raise LegalisError(f"Unknown minimum authority grade: {minimum}")
    usable: list[str] = []
    stale: list[str] = []
    rejected: list[str] = []
    for row in candidates:
        evidence_id = str(row.get("evidence_id") or stable_id("LEVID", kind, row.get("source_ref"), row.get("sha256")))
        trust = str(row.get("trust_state") or "captured_untrusted")
        grade = str(row.get("authority_grade") or "self_asserted")
        expiry = _parse_time(str(row.get("expires_at"))) if row.get("expires_at") else None
        if trust != "trusted_for_review" or AUTHORITY_GRADES.get(grade, -1) < AUTHORITY_GRADES[minimum]:
            rejected.append(evidence_id)
            continue
        if expiry and current >= expiry:
            stale.append(evidence_id)
            continue
        usable.append(evidence_id)

    if usable:
        return _result(requirement, "ALLOW", "satisfied", f"Current trusted evidence satisfies: {kind}", evidence_ids=usable)
    if stale:
        verdict = _validate_verdict(requirement.get("stale_verdict"), default="NEEDS_YOU")
        return _result(requirement, verdict, "stale", f"Evidence exists but is expired: {kind}", evidence_ids=stale)
    verdict = _validate_verdict(requirement.get("rejected_verdict"), default="NEEDS_YOU")
    return _result(requirement, verdict, "unusable", f"Evidence exists but is not trusted/authoritative enough: {kind}", evidence_ids=rejected)


def _evaluate_operator(requirement: Mapping[str, Any], operator_checks: Mapping[str, Any]) -> dict[str, Any]:
    key = str(requirement.get("operator_key") or "")
    if not key:
        raise LegalisError(f"Operator requirement {requirement['requirement_id']} has no operator_key.")
    present, value, receipt_ref = _operator_value(operator_checks, key)
    if not present:
        verdict = _validate_verdict(requirement.get("missing_verdict"), default="NEEDS_YOU")
        return _result(requirement, verdict, "missing", f"Explicit operator check is required: {key}", operator_key=key, operator_receipt_ref=None)
    required_value = requirement.get("required_value", True)
    if value == required_value:
        return _result(requirement, "ALLOW", "satisfied", f"Operator check satisfied: {key}", operator_key=key, operator_receipt_ref=receipt_ref)
    verdict = _validate_verdict(requirement.get("failure_verdict"), default="REFUSE")
    return _result(requirement, verdict, "failed", f"Operator check does not satisfy configured prerequisite: {key}", operator_key=key, operator_receipt_ref=receipt_ref)


def _evaluate_deadline(requirement: Mapping[str, Any], identity: Mapping[str, Any], current: datetime) -> dict[str, Any]:
    raw_due = requirement.get("due_at")
    if not raw_due and requirement.get("due_at_field"):
        raw_due = _get_path(identity, str(requirement["due_at_field"]))
    if not raw_due:
        verdict = _validate_verdict(requirement.get("missing_verdict"), default="NEEDS_YOU")
        return _result(requirement, verdict, "missing", "Deadline prerequisite has no recorded due date.", due_at=None)
    due = _parse_time(str(raw_due))
    if due is None:
        raise LegalisError(f"Deadline {requirement['requirement_id']} has an invalid due date.")
    if current > due:
        verdict = _validate_verdict(requirement.get("overdue_verdict"), default="REFUSE")
        return _result(requirement, verdict, "overdue", "Configured deadline has passed.", due_at=due.isoformat())
    return _result(requirement, "ALLOW", "satisfied", "Configured deadline has not passed.", due_at=due.isoformat())


def evaluate_capability(
    *,
    capability_id: str,
    identity: Mapping[str, Any],
    registry: Mapping[str, Any],
    evidence: list[Mapping[str, Any]] | None = None,
    operator_checks: Mapping[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Evaluate configured prerequisites only. This function never supplies legal advice or legal clearance."""
    validate_identity(identity)
    validate_registry(registry)
    capability = _capability(registry, capability_id)
    evidence = list(evidence or [])
    operator_checks = dict(operator_checks or {})
    current = _parse_time(now or timestamp())
    assert current is not None

    results: list[dict[str, Any]] = []
    for requirement in capability.get("requirements") or []:
        kind = str(requirement["kind"])
        if kind == "identity_field":
            results.append(_evaluate_identity(requirement, identity))
        elif kind == "evidence":
            results.append(_evaluate_evidence(requirement, evidence, current))
        elif kind == "operator_check":
            results.append(_evaluate_operator(requirement, operator_checks))
        elif kind == "deadline":
            results.append(_evaluate_deadline(requirement, identity, current))
        else:
            raise LegalisError(f"Unsupported requirement kind: {kind}")

    verdict = "ALLOW"
    if any(row["verdict"] == "REFUSE" for row in results):
        verdict = "REFUSE"
    elif any(row["verdict"] == "NEEDS_YOU" for row in results):
        verdict = "NEEDS_YOU"

    identity_hash = canonical_hash(identity)
    registry_hash = canonical_hash(registry)
    evidence_hash = canonical_hash(evidence)
    operator_hash = canonical_hash(operator_checks)
    evaluated_at = current.isoformat()
    decision_id = stable_id("LEGALIS", capability_id, identity_hash, registry_hash, evidence_hash, operator_hash, evaluated_at)
    reason_codes = [f"{row['requirement_id']}:{row['state']}" for row in results if row["verdict"] != "ALLOW"]
    evidence_ids = sorted({str(item) for row in results for item in row.get("evidence_ids", []) if item})
    operator_receipts = sorted({str(row["operator_receipt_ref"]) for row in results if row.get("operator_receipt_ref")})

    return {
        "schema": LEGALIS_DECISION_SCHEMA,
        "decision_id": decision_id,
        "capability_id": capability_id,
        "capability_description": capability.get("description"),
        "verdict": verdict,
        "configured_prerequisites_satisfied": verdict == "ALLOW",
        "legal_clearance": False,
        "legal_opinion": False,
        "automatic_waiver": False,
        "automatic_filing": False,
        "human_or_professional_decision_may_still_be_required": bool(capability.get("human_or_professional_decision_may_still_be_required", True)),
        "reason_codes": reason_codes,
        "requirement_results": results,
        "evidence_ids": evidence_ids,
        "operator_receipt_refs": operator_receipts,
        "identity_id": identity["identity_id"],
        "identity_snapshot_sha256": identity_hash,
        "requirement_registry_sha256": registry_hash,
        "evidence_snapshot_sha256": evidence_hash,
        "operator_snapshot_sha256": operator_hash,
        "evaluated_at": evaluated_at,
        "kernel_authority": "Valinor",
        "kernel_enforcement_performed": False,
        "boundary_statement": (
            "ALLOW means only that configured prerequisites are satisfied. It is not legal advice, a legal opinion, "
            "a regulatory ruling, a waiver, a filing, or authority to bypass explicit human/professional decisions."
        ),
    }


def bind_to_governed_case(case: dict[str, Any], decision: Mapping[str, Any], *, receipt_ref: str | None = None) -> dict[str, Any]:
    """Project a Legalis decision into DIO Governed Case without conflating epistemic support with authority."""
    if decision.get("schema") != LEGALIS_DECISION_SCHEMA:
        raise LegalisError("Cannot bind an unsupported Legalis decision schema.")
    try:
        from products.governed_case import add_actor, record_decision
    except ImportError as exc:
        raise LegalisError("DIO Governed Case core is unavailable.") from exc

    actor_id = "dio-legalis"
    if not any(row.get("actor_id") == actor_id for row in case.get("actors") or []):
        add_actor(
            case,
            actor_id=actor_id,
            actor_type="service",
            role="configured_prerequisite_evaluator",
            authority_scope=["configured_prerequisite_evaluation"],
        )

    gate_id = f"legalis:{decision['capability_id']}"
    gate_state = {"ALLOW": "allow", "REFUSE": "refuse", "NEEDS_YOU": "needs_you"}[str(decision["verdict"])]
    reason = str(decision.get("boundary_statement") or "Legalis configured-prerequisite decision.")
    gate = next((row for row in case.get("gates") or [] if row.get("gate_id") == gate_id), None)
    if gate is None:
        gate = {
            "gate_id": gate_id,
            "state": gate_state,
            "reason": reason,
            "required_authority": None,
            "required_evidence_ids": [],
            "decision_id": None,
            "decided_at": decision.get("evaluated_at") if gate_state in {"allow", "refuse"} else None,
        }
        case.setdefault("gates", []).append(gate)
    else:
        gate.update({
            "state": gate_state,
            "reason": reason,
            "decided_at": decision.get("evaluated_at") if gate_state in {"allow", "refuse"} else None,
        })

    recorded = record_decision(
        case,
        decision_type="gate",
        verdict=str(decision["verdict"]),
        actor_id=actor_id,
        reasoning_summary="; ".join(decision.get("reason_codes") or []) or "Configured prerequisites satisfied.",
        evidence_refs=list(decision.get("evidence_ids") or []),
    )
    gate["decision_id"] = recorded["decision_id"]
    if receipt_ref and receipt_ref not in case.setdefault("event_refs", []):
        case["event_refs"].append(receipt_ref)
    return gate
