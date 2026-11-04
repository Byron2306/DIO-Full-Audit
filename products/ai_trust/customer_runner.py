"""Customer-input execution for bounded AI Trust product review packs."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from products.ai_trust.runner import run_ai_trust


PRODUCTS = {
    "ChangeProof": ("dio_modelchangeproof", "ai_model_change", "change_assessment"),
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_customer_ai_trust_product(product_name: str, packet: Mapping[str, Any], output_dir: str | Path) -> dict[str, Any]:
    definition = PRODUCTS.get(product_name)
    if definition is None:
        raise ValueError(f"no customer AI Trust contract for {product_name}")
    if packet.get("owner_authorized") is not True:
        raise ValueError("owner_authorized=true is required for customer-source processing")
    product_id, source_type, assessment_key = definition
    assessment = packet.get(assessment_key)
    if not isinstance(assessment, Mapping) or assessment.get("source_type") != source_type:
        raise ValueError(f"{assessment_key}.source_type must be {source_type}")
    payload = dict(assessment)
    system = payload.get("system")
    if not isinstance(system, dict) or not system.get("system_id") or not system.get("intended_use"):
        raise ValueError(f"{assessment_key}.system requires owner-supplied system_id and intended_use")
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError(f"{assessment_key}.sources must identify the submitted evidence sources")
    for index, source in enumerate(sources, 1):
        digest = str(source.get("sha256") or "") if isinstance(source, dict) else ""
        digest = digest.removeprefix("sha256:")
        if len(digest) != 64 or any(char not in "0123456789abcdefABCDEF" for char in digest):
            raise ValueError(f"{assessment_key}.sources[{index}] needs a SHA-256 digest")

    out = Path(output_dir).resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError("customer AI Trust output directory must be empty")
    out.mkdir(parents=True, exist_ok=True)
    input_path = out / "CUSTOMER_AI_TRUST_ASSESSMENT.json"
    input_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    result = run_ai_trust(
        product_id,
        payload,
        output_dir=out / "ai_trust",
        operator_id=str(packet.get("operator_id") or "customer-packet-operator"),
        now=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    processor_receipt = result.get("receipt") or {}
    if processor_receipt.get("human_gate") != "NEEDS_YOU" or processor_receipt.get("external_release_gate") != "REFUSE":
        raise RuntimeError(f"{product_name} did not preserve the human review and external-release gates")
    if processor_receipt.get("authority_created") is not False or processor_receipt.get("external_effects") is not False:
        raise RuntimeError(f"{product_name} created a forbidden authority or external effect")
    seraph = result.get("seraph_challenge") or {}
    telemetry_assessment = (seraph.get("evidence_context") or {}).get("seraph_telemetry")
    telemetry_input = payload.get("seraph_telemetry")
    telemetry_summary = processor_receipt.get("seraph_telemetry_review") or {
        "state": "NOT_REQUESTED", "required": False, "signature_state": "NOT_ASSESSED",
        "source_identity_state": "NOT_ASSESSED", "case_scope_state": "NOT_ASSESSED",
        "event_count": 0, "audit_count": 0, "assessment_sha256": None,
        "input_sha256": None, "case_id": str(payload.get("case_id") or system["system_id"]),
    }
    if telemetry_assessment is not None:
        challenge_path = out / "ai_trust" / "SERAPH_CHALLENGE_RECEIPT.json"
        review = {
            "schema": "dio.ai_trust.customer_seraph_telemetry_review.v1",
            "case_id": str(payload.get("case_id") or system["system_id"]),
            "assessment": telemetry_assessment,
            "proof_summary": telemetry_summary,
            "source_binding": {
                "source_ref": f"{assessment_key}.seraph_telemetry",
                "assessment_file": input_path.name,
                "assessment_file_sha256": _sha(input_path),
                "telemetry_input_sha256": telemetry_summary.get("input_sha256"),
                "challenge_receipt_path": str(challenge_path.relative_to(out)),
                "challenge_receipt_sha256": _sha(challenge_path),
                "challenge_receipt_canonical_sha256": seraph.get("receipt_sha256"),
            },
            "claim_boundary": telemetry_summary.get("claim_boundary"),
        }
        review_path = out / "SERAPH_TELEMETRY_REVIEW.json"
        review_path.write_text(json.dumps(review, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    artifacts = [{"path": str(path.relative_to(out)), "bytes": path.stat().st_size, "sha256": _sha(path)}
                 for path in sorted(out.rglob("*")) if path.is_file() and path != input_path]
    receipt = {
        "schema": "dio.ai_trust.customer_package.v1",
        "product_name": product_name,
        "product_id": product_id,
        "case_id": str(payload.get("case_id") or system["system_id"]),
        "source_input_sha256": _sha(input_path),
        "seraph_challenge": result.get("seraph_challenge"),
        "seraph_telemetry_review": telemetry_summary,
        "human_review_required": True,
        "external_release": "REFUSE",
        "authority_created": False,
        "external_effects": False,
        "commercial_validation": "UNPROVED",
        "artifacts": artifacts,
        "claim_boundary": "This package evaluates customer-supplied technical declarations and evidence for human review. It does not independently verify source claims, approve a model change, grant authority, execute tools, or authorize external release.",
        "synthetic_acceptance_case": packet.get("synthetic_acceptance_not_customer_evidence") is True,
    }
    (out / "AI_TRUST_CUSTOMER_RECEIPT.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return receipt
