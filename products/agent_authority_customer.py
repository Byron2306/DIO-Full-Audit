"""Customer-owned Agent Authority review workflow; never grants agent authority."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from products.ai_trust.runner import run_ai_trust


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_agent_authority_package(packet: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    """Evaluate the owner's explicit agent evidence and create a held review pack."""
    assessment = packet.get("agent_assessment")
    if not isinstance(assessment, Mapping):
        raise ValueError("agent_assessment must contain the customer-supplied Agent Authority assessment")
    payload = dict(assessment)
    packet_telemetry = packet.get("seraph_telemetry")
    assessment_telemetry = payload.get("seraph_telemetry")
    if packet_telemetry is not None and assessment_telemetry is not None:
        raise ValueError("Seraph telemetry must be supplied in one Agent Authority packet location only")
    if packet_telemetry is not None:
        if not isinstance(packet_telemetry, Mapping):
            raise ValueError("seraph_telemetry must be a customer-supplied object")
        payload["seraph_telemetry"] = dict(packet_telemetry)
    if payload.get("seraph_telemetry") is not None:
        telemetry_request = payload["seraph_telemetry"]
        if not isinstance(telemetry_request, Mapping) or not isinstance(telemetry_request.get("required"), bool):
            raise ValueError("seraph_telemetry must contain an explicit boolean required field")
    if payload.get("source_type") != "ai_agent":
        raise ValueError("agent_assessment.source_type must be ai_agent")
    system = payload.get("system")
    if not isinstance(system, dict) or not system.get("system_id") or not system.get("intended_use"):
        raise ValueError("agent_assessment.system requires owner-supplied system_id and intended_use")
    if not isinstance(payload.get("sources"), list) or not payload["sources"]:
        raise ValueError("agent_assessment.sources must identify the supplied evidence sources")
    for index, source in enumerate(payload["sources"], 1):
        digest = str(source.get("sha256") or "") if isinstance(source, dict) else ""
        if len(digest.removeprefix("sha256:")) != 64:
            raise ValueError(f"agent_assessment.sources[{index}] needs a SHA-256 digest")

    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    input_path = out / "CUSTOMER_AGENT_ASSESSMENT.json"
    input_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    result = run_ai_trust(
        "dio_agentauthority",
        payload,
        output_dir=out / "agent_authority",
        operator_id=str(packet.get("operator_id") or "customer-packet-operator"),
        now=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    receipt = result.get("receipt") or {}
    if receipt.get("human_gate") != "NEEDS_YOU" or receipt.get("external_release_gate") != "REFUSE":
        raise RuntimeError("Agent Authority did not preserve required human and release gates")
    if receipt.get("authority_created") is not False or receipt.get("external_effects") is not False:
        raise RuntimeError("Agent Authority execution created a forbidden authority or external effect")
    seraph = result.get("seraph_challenge") or {}
    telemetry_assessment = ((seraph.get("evidence_context") or {}).get("seraph_telemetry") or {
        "state": "NOT_REQUESTED", "required": False, "event_count": 0, "audit_count": 0,
        "signature_state": "NOT_ASSESSED", "source_identity_state": "NOT_ASSESSED",
        "case_scope_state": "NOT_ASSESSED",
    })
    telemetry_review = {
        "schema": "dio.agent_authority.seraph_telemetry_review.v1",
        "case_id": str(payload.get("case_id") or system["system_id"]),
        "assessment": telemetry_assessment,
        "proof_summary": receipt.get("seraph_telemetry_review"),
        "source_binding": {
            "source_ref": "CUSTOMER_AGENT_ASSESSMENT.json#/seraph_telemetry" if payload.get("seraph_telemetry") is not None else None,
            "assessment_file_sha256": _sha(input_path),
            "telemetry_input_sha256": (receipt.get("seraph_telemetry_review") or {}).get("input_sha256"),
            "challenge_receipt_path": "agent_authority/SERAPH_CHALLENGE_RECEIPT.json",
            "challenge_receipt_sha256": _sha(out / "agent_authority" / "SERAPH_CHALLENGE_RECEIPT.json"),
        },
        "claim_boundary": "Offline case-bound event/audit-chain and detached-signature checks are supplementary review evidence only. Hash integrity does not establish trusted signer identity, source authenticity, complete telemetry, persistent storage, live collection or deployed-agent behavior.",
    }
    telemetry_review_path = out / "SERAPH_TELEMETRY_REVIEW.json"
    telemetry_review_path.write_text(json.dumps(telemetry_review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    artifacts = [{"path": str(p.relative_to(out)), "bytes": p.stat().st_size, "sha256": _sha(p)}
                 for p in sorted((out / "agent_authority").rglob("*")) if p.is_file()]
    artifacts.append({"path": telemetry_review_path.name, "bytes": telemetry_review_path.stat().st_size, "sha256": _sha(telemetry_review_path)})
    package = {
        "schema": "dio.agent_authority.customer_package.v1",
        "case_id": str(payload.get("case_id") or system["system_id"]),
        "source_input_sha256": _sha(input_path),
        "processor": "products.ai_trust.runner.run_ai_trust",
        "product_id": "dio_agentauthority",
        "seraph_challenge": result.get("seraph_challenge"),
        "seraph_telemetry_review": telemetry_review,
        "human_review_required": True,
        "external_release": "REFUSE",
        "authority_created": False,
        "external_effects": False,
        "commercial_validation": "UNPROVED",
        "artifacts": artifacts,
        "claim_boundary": "This package evaluates customer-supplied declarations and evidence for human review. It does not grant capabilities, approve an agent, verify customer declarations independently, execute actions, or authorize external release.",
    }
    (out / "AGENT_AUTHORITY_PACKAGE_RECEIPT.json").write_text(json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return package
