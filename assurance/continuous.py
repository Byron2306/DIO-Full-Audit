from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from twin import build_loki_mirror_maze, validate_twin
from twin.canonical import TwinError

ASSURANCE_RECEIPT_SCHEMA = "dio.continuous_assurance.receipt.v1"
DRIFT_SCHEMA = "dio.continuous_assurance.drift.v1"


class AssuranceError(ValueError):
    pass


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _record_key(layer: str, row: dict[str, Any]) -> tuple[str, str, str]:
    return layer, str(row.get("source_case_id") or ""), str(row.get("source_id") or "")


def _index_twin(twin: dict[str, Any]) -> dict[tuple[str, str, str], dict[str, Any]]:
    index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for layer, rows in twin["layers"].items():
        for row in rows:
            key = _record_key(layer, row)
            if not key[2]:
                raise AssuranceError(f"Twin record in {layer} has no source identity.")
            if key in index:
                raise AssuranceError(f"Duplicate Twin record identity: {key}")
            index[key] = row
    return index


def _payload_changed(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return before.get("payload") != after.get("payload")


def _classify_change(layer: str, before: dict[str, Any] | None, after: dict[str, Any] | None) -> tuple[str, str, str, bool, bool]:
    """Return category, severity, response, reopen_case, block_execution."""
    if before is None and after is not None:
        if layer == "receipt_state":
            return "receipt_added", "info", "record", False, False
        if layer == "authority_state" and after.get("current") is True:
            return "authority_added", "info", "record", False, False
        if layer == "capability_state" and after.get("current") is True:
            return "capability_added", "info", "record", False, False
        return f"{layer}_added", "info", "record", False, False

    if before is not None and after is None:
        if layer == "receipt_state":
            return "receipt_missing", "critical", "needs_you", True, True
        if layer == "authority_state":
            return "authority_missing", "critical", "needs_you", True, True
        if layer == "capability_state":
            return "capability_missing", "critical", "needs_you", True, True
        return f"{layer}_missing", "high", "review", True, False

    assert before is not None and after is not None
    before_current = before.get("current") is True
    after_current = after.get("current") is True

    if before_current and not after_current:
        mapping = {
            "evidence_state": ("evidence_became_noncurrent", "high", "needs_evidence", True, False),
            "authority_state": ("authority_became_noncurrent", "critical", "needs_you", True, True),
            "capability_state": ("capability_became_noncurrent", "critical", "needs_you", True, True),
            "requirement_state": ("requirement_became_noncurrent", "high", "needs_evidence", True, False),
            "world_state": ("world_state_became_noncurrent", "high", "review", True, False),
        }
        if layer in mapping:
            return mapping[layer]
        return f"{layer}_became_noncurrent", "high", "review", True, False

    if not before_current and after_current:
        return f"{layer}_became_current", "medium", "review", False, False

    if _payload_changed(before, after):
        mapping = {
            "claim_state": ("claim_state_changed", "high", "review", True, False),
            "requirement_state": ("requirement_state_changed", "high", "needs_evidence", True, False),
            "authority_state": ("authority_state_changed", "critical", "needs_you", True, True),
            "capability_state": ("capability_state_changed", "critical", "needs_you", True, True),
            "action_state": ("action_payload_changed", "critical", "needs_you", True, True),
            "receipt_state": ("receipt_chain_changed", "critical", "needs_you", True, True),
            "world_state": ("world_state_changed", "high", "review", True, False),
            "evidence_state": ("evidence_state_changed", "high", "needs_evidence", True, False),
        }
        return mapping.get(layer, (f"{layer}_changed", "medium", "review", False, False))

    return "unchanged", "info", "none", False, False


def compare_twin_snapshots(previous_twin: dict[str, Any], current_twin: dict[str, Any]) -> dict[str, Any]:
    try:
        validate_twin(previous_twin)
        validate_twin(current_twin)
    except TwinError as exc:
        raise AssuranceError(str(exc)) from exc

    previous_time = _parse_time(previous_twin["observed_at"])
    current_time = _parse_time(current_twin["observed_at"])
    if current_time < previous_time:
        raise AssuranceError("Continuous assurance cannot compare a current Twin older than the previous Twin.")

    previous = _index_twin(previous_twin)
    current = _index_twin(current_twin)
    findings: list[dict[str, Any]] = []

    for key in sorted(set(previous) | set(current)):
        layer, source_case_id, source_id = key
        before = previous.get(key)
        after = current.get(key)
        category, severity, response, reopen_case, block_execution = _classify_change(layer, before, after)
        if category == "unchanged":
            continue
        body = {
            "layer": layer,
            "source_case_id": source_case_id or None,
            "source_id": source_id,
            "category": category,
            "severity": severity,
            "response": response,
            "reopen_case": reopen_case,
            "block_execution": block_execution,
            "previous_record_id": before.get("twin_record_id") if before else None,
            "current_record_id": after.get("twin_record_id") if after else None,
            "previous_current": before.get("current") if before else None,
            "current_current": after.get("current") if after else None,
            "previous_reason": before.get("currency_reason") if before else None,
            "current_reason": after.get("currency_reason") if after else None,
            "synthetic": False,
            "authority_effect": False,
            "execution_effect": False,
        }
        body["fingerprint"] = _fingerprint(body)
        body["finding_id"] = f"ASF-{body['fingerprint'][:16].upper()}"
        findings.append(body)

    material = [row for row in findings if row["severity"] in {"medium", "high", "critical"}]
    critical = [row for row in findings if row["severity"] == "critical"]
    reopen_case_ids = sorted({str(row["source_case_id"]) for row in findings if row["reopen_case"] and row.get("source_case_id")})
    block_case_ids = sorted({str(row["source_case_id"]) for row in findings if row["block_execution"] and row.get("source_case_id")})

    result = {
        "schema": DRIFT_SCHEMA,
        "previous_twin_id": previous_twin["twin_id"],
        "previous_twin_fingerprint": previous_twin["fingerprint"],
        "current_twin_id": current_twin["twin_id"],
        "current_twin_fingerprint": current_twin["fingerprint"],
        "previous_observed_at": previous_twin["observed_at"],
        "current_observed_at": current_twin["observed_at"],
        "findings": findings,
        "finding_count": len(findings),
        "material_finding_count": len(material),
        "critical_finding_count": len(critical),
        "reopen_case_ids": reopen_case_ids,
        "block_execution_case_ids": block_case_ids,
        "material_drift": bool(material),
        "authority_created": False,
        "execution_created": False,
    }
    result["fingerprint"] = _fingerprint(result)
    return result


def assess_continuous_assurance(previous_twin: dict[str, Any], current_twin: dict[str, Any]) -> dict[str, Any]:
    drift = compare_twin_snapshots(previous_twin, current_twin)
    maze = build_loki_mirror_maze(current_twin) if drift["material_drift"] else None
    mirror_categories = []
    if maze is not None:
        mirror_categories = sorted({
            row["category"] for row in maze["nodes"] if row.get("category") != "canonical_anchor"
        })

    body = {
        "schema": ASSURANCE_RECEIPT_SCHEMA,
        "previous_twin_id": previous_twin["twin_id"],
        "previous_twin_fingerprint": previous_twin["fingerprint"],
        "current_twin_id": current_twin["twin_id"],
        "current_twin_fingerprint": current_twin["fingerprint"],
        "drift_fingerprint": drift["fingerprint"],
        "finding_count": drift["finding_count"],
        "material_finding_count": drift["material_finding_count"],
        "critical_finding_count": drift["critical_finding_count"],
        "reopen_case_ids": drift["reopen_case_ids"],
        "block_execution_case_ids": drift["block_execution_case_ids"],
        "material_drift": drift["material_drift"],
        "loki_rerun": maze is not None,
        "loki_mirror_maze_id": maze["mirror_maze_id"] if maze else None,
        "loki_mirror_fingerprint": maze["fingerprint"] if maze else None,
        "mirror_divergence_categories": mirror_categories,
        "findings": copy.deepcopy(drift["findings"]),
        "recommended_state": (
            "BLOCK_AND_REVIEW" if drift["critical_finding_count"] else
            "REVIEW_REQUIRED" if drift["material_finding_count"] else
            "ASSURED_NO_MATERIAL_DRIFT"
        ),
        "laws": {
            "continuous_assurance_has_no_authority": True,
            "continuous_assurance_never_executes": True,
            "findings_do_not_self_apply": True,
            "loki_reruns_only_on_material_drift": True,
            "synthetic_mirror_never_becomes_canonical": True,
            "valinor_remains_sole_kernel_authority": True,
            "arda_remains_execution_identity_only": True,
        },
        "authority_created": False,
        "execution_created": False,
    }
    fingerprint = _fingerprint(body)
    receipt = copy.deepcopy(body)
    receipt["fingerprint"] = fingerprint
    receipt["assurance_receipt_id"] = f"ASSURE-{fingerprint[:16].upper()}"
    validate_assurance_receipt(receipt, previous_twin=previous_twin, current_twin=current_twin)
    return receipt


def validate_assurance_receipt(
    receipt: dict[str, Any], *, previous_twin: dict[str, Any] | None = None, current_twin: dict[str, Any] | None = None
) -> None:
    if receipt.get("schema") != ASSURANCE_RECEIPT_SCHEMA:
        raise AssuranceError("Unsupported continuous assurance receipt schema.")
    laws = receipt.get("laws") or {}
    required_laws = (
        "continuous_assurance_has_no_authority",
        "continuous_assurance_never_executes",
        "findings_do_not_self_apply",
        "loki_reruns_only_on_material_drift",
        "synthetic_mirror_never_becomes_canonical",
        "valinor_remains_sole_kernel_authority",
        "arda_remains_execution_identity_only",
    )
    if any(laws.get(name) is not True for name in required_laws):
        raise AssuranceError("Continuous assurance constitutional law disabled.")
    if receipt.get("authority_created") is not False or receipt.get("execution_created") is not False:
        raise AssuranceError("Continuous assurance attempted to create authority or execution.")
    if receipt.get("loki_rerun") and not receipt.get("material_drift"):
        raise AssuranceError("Loki may only rerun for material drift.")
    for finding in receipt.get("findings") or []:
        if finding.get("synthetic") is not False:
            raise AssuranceError("Assurance finding must describe canonical drift, not synthetic truth.")
        if finding.get("authority_effect") is not False or finding.get("execution_effect") is not False:
            raise AssuranceError("Assurance finding attempted to self-apply authority or execution effects.")
    if previous_twin is not None:
        validate_twin(previous_twin)
        if receipt.get("previous_twin_id") != previous_twin["twin_id"] or receipt.get("previous_twin_fingerprint") != previous_twin["fingerprint"]:
            raise AssuranceError("Assurance receipt is not bound to the supplied previous Twin.")
    if current_twin is not None:
        validate_twin(current_twin)
        if receipt.get("current_twin_id") != current_twin["twin_id"] or receipt.get("current_twin_fingerprint") != current_twin["fingerprint"]:
            raise AssuranceError("Assurance receipt is not bound to the supplied current Twin.")
    payload = copy.deepcopy(receipt)
    fingerprint = payload.pop("fingerprint", None)
    receipt_id = payload.pop("assurance_receipt_id", None)
    expected = _fingerprint(payload)
    if fingerprint != expected or receipt_id != f"ASSURE-{expected[:16].upper()}":
        raise AssuranceError("Continuous assurance receipt fingerprint mismatch.")
