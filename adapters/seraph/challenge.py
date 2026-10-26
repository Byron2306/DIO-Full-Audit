from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from products.governed_case import raise_challenge

VERDICTS = {"CLEAR", "CONTESTED", "HOSTILE", "INSUFFICIENT_EVIDENCE"}
SEVERITIES = {"advisory", "material", "blocking"}
COVERAGE_STATES = {"complete", "partial", "unknown"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _challenge_type(kind: str) -> str:
    mapping = {
        "contradiction": "contradiction",
        "missing_evidence": "missing_evidence",
        "stale_evidence": "stale_evidence",
        "authority": "authority",
        "scope": "scope",
        "alternative_hypothesis": "alternative_hypothesis",
        "world_state": "world_state",
        "threat": "alternative_hypothesis",
        "manipulation": "alternative_hypothesis",
    }
    return mapping.get(kind, "alternative_hypothesis")


def build_challenge_receipt(request: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic Seraph challenge receipt without executing any response action."""
    case_id = str(request.get("case_id") or "").strip()
    target_type = str(request.get("target_type") or "case").strip()
    target_id = str(request.get("target_id") or case_id).strip()
    coverage_state = str(request.get("coverage_state") or "unknown").strip()
    findings = list(request.get("findings") or [])

    if not case_id:
        raise ValueError("Seraph challenge requires case_id.")
    if target_type not in {"case", "requirement", "claim", "evidence", "gate", "action"}:
        raise ValueError("Unsupported Seraph challenge target_type.")
    if not target_id:
        raise ValueError("Seraph challenge requires target_id.")
    if coverage_state not in COVERAGE_STATES:
        raise ValueError("coverage_state must be complete, partial, or unknown.")

    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(findings, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"Seraph finding {index} must be an object.")
        severity = str(raw.get("severity") or "advisory")
        if severity not in SEVERITIES:
            raise ValueError(f"Unsupported Seraph finding severity: {severity}")
        detail = str(raw.get("detail") or "").strip()
        if not detail:
            raise ValueError(f"Seraph finding {index} requires detail.")
        normalized.append(
            {
                "finding_id": str(raw.get("finding_id") or f"FIND-{index:03d}"),
                "kind": str(raw.get("kind") or "alternative_hypothesis"),
                "severity": severity,
                "hostile_signal": bool(raw.get("hostile_signal", False)),
                "detail": detail,
                "evidence_ids": list(dict.fromkeys(str(x) for x in (raw.get("evidence_ids") or []) if str(x))),
                "mitre_refs": list(dict.fromkeys(str(x) for x in (raw.get("mitre_refs") or []) if str(x))),
            }
        )

    if any(item["hostile_signal"] and item["severity"] in {"material", "blocking"} for item in normalized):
        verdict = "HOSTILE"
    elif any(item["severity"] in {"material", "blocking"} for item in normalized):
        verdict = "CONTESTED"
    elif coverage_state != "complete":
        verdict = "INSUFFICIENT_EVIDENCE"
    else:
        verdict = "CLEAR"

    created_at = _now()
    basis = {
        "case_id": case_id,
        "target_type": target_type,
        "target_id": target_id,
        "coverage_state": coverage_state,
        "findings": normalized,
        "requested_action": request.get("requested_action"),
    }
    challenge_id = "SERAPH-" + _stable_hash(basis)[:16].upper()
    receipt = {
        "schema": "dio.seraph.challenge_receipt.v1",
        "challenge_id": challenge_id,
        "created_at": created_at,
        "case_id": case_id,
        "target_type": target_type,
        "target_id": target_id,
        "coverage_state": coverage_state,
        "verdict": verdict,
        "findings": normalized,
        "challenge_basis_sha256": _stable_hash(basis),
        "source_identity": "Seraph Challenge Organ",
        "execution_authorized": False,
        "kernel_authority": "Valinor",
        "external_action_executed": False,
        "response_action_requested": request.get("requested_action"),
        "response_action_executed": False,
        "boundary_statement": (
            "Seraph may challenge claims, evidence and proposed actions. A challenge receipt never authorizes "
            "SOAR response, containment, release, spend, mutation or any other external execution."
        ),
    }
    receipt["receipt_sha256"] = _stable_hash(receipt)
    return receipt


def project_challenge_into_case(case: dict[str, Any], receipt: dict[str, Any]) -> list[dict[str, Any]]:
    """Project material Seraph findings into Governed Case without granting execution authority."""
    if receipt.get("schema") != "dio.seraph.challenge_receipt.v1":
        raise ValueError("Unsupported Seraph receipt schema.")
    if str(receipt.get("case_id")) != str(case.get("case_id")):
        raise ValueError("Seraph receipt case_id does not match Governed Case.")
    if receipt.get("execution_authorized") is not False or receipt.get("external_action_executed") is not False:
        raise ValueError("Seraph receipt violates the no-execution authority boundary.")

    if receipt.get("verdict") == "CLEAR":
        return []

    rows: list[dict[str, Any]] = []
    findings = list(receipt.get("findings") or [])
    if not findings and receipt.get("verdict") == "INSUFFICIENT_EVIDENCE":
        findings = [
            {
                "kind": "missing_evidence",
                "severity": "material",
                "detail": "Seraph challenge coverage is incomplete; additional adversarial evidence is required.",
                "evidence_ids": [],
            }
        ]

    for finding in findings:
        severity = str(finding.get("severity") or "advisory")
        if receipt.get("verdict") == "HOSTILE" and severity == "advisory":
            severity = "material"
        rows.append(
            raise_challenge(
                case,
                target_type=str(receipt.get("target_type") or "case"),
                target_id=str(receipt.get("target_id") or case["case_id"]),
                challenge_type=_challenge_type(str(finding.get("kind") or "alternative_hypothesis")),
                severity=severity,
                hypothesis=str(finding.get("detail") or "Seraph adversarial challenge"),
                raised_by="seraph",
                evidence_ids=list(finding.get("evidence_ids") or []),
            )
        )
    return rows
