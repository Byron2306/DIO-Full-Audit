from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
from typing import Any

from products.governed_case import canonical_hash, validate_case
from products.regulatory.core import build_regulatory_context

from .materializer import materialize_regops_case


COMPONENT_PRODUCT_ID = "dio_airegreadiness"
COMPONENT_RELATION = "composition_reuse"
COMPONENT_SOURCE_TYPE = "ai_regulatory_context"


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write(path: Path, value: bytes) -> str:
    path.write_bytes(value)
    return _sha(value)


def _gate(case: dict[str, Any], gate_id: str) -> dict[str, Any]:
    return next(row for row in case["gates"] if row["gate_id"] == gate_id)


def _component_binding(
    payload: dict[str, Any] | None,
    *,
    now: str,
) -> dict[str, Any]:
    if payload is None:
        return {
            "reusable_component_product_id": COMPONENT_PRODUCT_ID,
            "relationship": COMPONENT_RELATION,
            "state": "NOT_EVALUATED",
            "reason": "No AI regulatory-readiness context was supplied.",
            "authority_created": False,
            "external_effects": False,
            "external_release": "REFUSE",
        }

    if payload.get("source_type") != COMPONENT_SOURCE_TYPE:
        raise ValueError(
            f"RegOps AI component requires source_type={COMPONENT_SOURCE_TYPE}"
        )

    envelope = build_regulatory_context(
        COMPONENT_PRODUCT_ID,
        payload,
        now=now,
    )
    if envelope["authority_created"] is not False:
        raise RuntimeError("AIRegReadiness component illegally created authority.")
    if envelope["external_effects"] is not False:
        raise RuntimeError("AIRegReadiness component illegally created external effects.")
    if envelope["external_release"] != "REFUSE":
        raise RuntimeError("AIRegReadiness component external release boundary drifted.")

    return {
        "reusable_component_product_id": COMPONENT_PRODUCT_ID,
        "relationship": COMPONENT_RELATION,
        "state": "CONTROLLED_CONTEXT_EVALUATED",
        "envelope_fingerprint": envelope["envelope_fingerprint"],
        "dimensions": {
            row["dimension"]: row["state"]
            for row in envelope["dimensions"]
        },
        "human_gate": envelope["human_gate"],
        "authority_created": False,
        "external_effects": False,
        "external_release": "REFUSE",
    }


def _review_pack(
    case: dict[str, Any],
    materialization: dict[str, Any],
    component: dict[str, Any],
) -> dict[str, Any]:
    matrix = materialization["prerequisite_matrix"]
    evidence = {row["evidence_id"]: row for row in case["evidence"]}
    used_evidence_ids = sorted(
        {
            evidence_id
            for row in matrix
            for evidence_id in row["evidence_ids"]
        }
    )
    evidence_receipts = [
        {
            "evidence_id": evidence_id,
            "source_ref": evidence[evidence_id]["source_ref"],
            "sha256": evidence[evidence_id].get("sha256"),
            "authority_grade": evidence[evidence_id]["authority_grade"],
            "trust_state": evidence[evidence_id]["trust_state"],
            "freshness_state": evidence[evidence_id]["freshness_state"],
        }
        for evidence_id in used_evidence_ids
        if evidence_id in evidence
    ]
    deadline_queue = [
        {
            "prerequisite_id": row["prerequisite_id"],
            "due_at": row["due_at"],
            "expires_at": row["expires_at"],
            "deadline_state": row["deadline_state"],
        }
        for row in matrix
        if row["deadline_state"] != "NONE"
    ]
    professional_ids = [
        row["prerequisite_id"]
        for row in matrix
        if row["professional_review_required"]
    ]

    return {
        "schema": "dio.regops.readiness_pack.v1",
        "product_id": "dio_regops",
        "case_id": case["case_id"],
        "profile_id": materialization["profile_id"],
        "requirement_register": matrix,
        "evidence_receipt_set": evidence_receipts,
        "deadline_and_renewal_queue": deadline_queue,
        "readiness_decision": materialization["readiness_decision"],
        "professional_escalation_record": {
            "state": "NEEDS_YOU" if professional_ids else "NOT_REQUIRED_BY_PROFILE",
            "prerequisite_ids": professional_ids,
            "professional_decision_created": False,
        },
        "ai_regulatory_component_binding": component,
        "risk_boundary": (
            "RegOps evaluates configured operational prerequisites and evidence for readiness review. "
            "It does not provide legal, accounting, tax, regulatory, or professional advice; an ALLOW "
            "readiness state is not legal clearance and creates no execution, filing, or release authority."
        ),
        "authority_created": False,
        "external_effects": False,
        "external_release": "REFUSE",
    }


def _html_pack(pack: dict[str, Any]) -> bytes:
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(row['prerequisite_id']))}</td>"
        f"<td>{html.escape(str(row['readiness_state']))}</td>"
        f"<td>{html.escape(str(row['deadline_state']))}</td>"
        f"<td>{html.escape(str(row['statement']))}</td>"
        "</tr>"
        for row in pack["requirement_register"]
    )
    decision = html.escape(str(pack["readiness_decision"]["state"]))
    page = (
        "<!doctype html><meta charset='utf-8'>"
        "<title>DIO RegOps Controlled Readiness Pack</title>"
        "<h1>DIO RegOps Controlled Readiness Pack</h1>"
        f"<p><strong>Configured readiness: {decision}</strong></p>"
        "<p>HUMAN/PROFESSIONAL REVIEW REMAINS AUTHORITATIVE. EXTERNAL RELEASE REFUSED.</p>"
        "<table border='1' cellspacing='0' cellpadding='6'>"
        "<tr><th>Prerequisite</th><th>Evidence state</th><th>Deadline state</th>"
        "<th>Statement</th></tr>"
        f"{rows}</table>"
        "<h2>AI regulatory component</h2>"
        f"<pre>{html.escape(json.dumps(pack['ai_regulatory_component_binding'], indent=2, sort_keys=True))}</pre>"
        "<p>An ALLOW readiness state means configured prerequisites are satisfied only. "
        "It is not legal clearance, professional advice, execution authority, filing authority, "
        "or external release authority.</p>"
    )
    return page.encode("utf-8")


def run_controlled_regops_review(
    case: dict[str, Any],
    *,
    profile_id: str,
    prerequisites: list[dict[str, Any]],
    evidence_inputs: list[dict[str, Any]],
    gaps: list[dict[str, Any]] | None,
    ai_regulatory_context: dict[str, Any] | None,
    output_dir: Path,
    operator_id: str,
    now: str,
) -> dict[str, Any]:
    if not str(operator_id or "").strip():
        raise ValueError("RegOps controlled processing requires an explicit operator_id.")

    validate_case(case)
    if _gate(case, "intake_authority")["state"] != "allow":
        raise RuntimeError("RegOps controlled processing requires approved intake authority.")
    if _gate(case, "generic_executor")["state"] != "refuse":
        raise RuntimeError("Generic executor boundary drifted before RegOps processing.")
    if _gate(case, "external_release")["state"] == "allow":
        raise RuntimeError("RegOps controlled processing cannot start with external release ALLOW.")

    materialization = materialize_regops_case(
        case,
        profile_id=profile_id,
        prerequisites=prerequisites,
        evidence_inputs=evidence_inputs,
        gaps=gaps,
        raised_by=operator_id,
        now=now,
    )
    component = _component_binding(ai_regulatory_context, now=now)
    pack = _review_pack(case, materialization, component)
    validate_case(case)

    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered = {
        "JSON": (
            "REGOPS_READINESS_PACK.json",
            json.dumps(pack, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")
            + b"\n",
        ),
        "HTML": ("REGOPS_READINESS_PACK.html", _html_pack(pack)),
    }
    artifacts = [
        {
            "artifact_type": kind,
            "filename": filename,
            "sha256": _write(output_dir / filename, body),
        }
        for kind, (filename, body) in rendered.items()
    ]

    pack_fingerprint = "sha256:" + _sha(_canonical(pack))
    proof = {
        "schema": "dio.regops.controlled_proof_manifest.v1",
        "provider_id": "regops_controlled_readiness_v1",
        "product_id": "dio_regops",
        "artifact_type": "proof_room_manifest",
        "case_id": case["case_id"],
        "profile_id": profile_id,
        "readiness_state": materialization["readiness_decision"]["state"],
        "readiness_pack_fingerprint": pack_fingerprint,
        "ai_regulatory_component": {
            "product_id": COMPONENT_PRODUCT_ID,
            "relationship": COMPONENT_RELATION,
            "state": component["state"],
            "envelope_fingerprint": component.get("envelope_fingerprint"),
        },
        "case_sha256": canonical_hash(case),
        "artifacts": artifacts,
        "human_gate": {
            "state": "NEEDS_YOU",
            "reason": (
                "Professional interpretation, consequential action, filing, and external release "
                "remain human-authority bound."
            ),
        },
        "authority_created": False,
        "execution_performed": False,
        "external_effects": False,
        "external_release": False,
    }
    proof["proof_fingerprint"] = "sha256:" + _sha(_canonical(proof))
    _write(
        output_dir / "PROOF_MANIFEST.json",
        json.dumps(proof, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )

    receipt = {
        "schema": "dio.regops.controlled_processing_receipt.v1",
        "processor_id": "regops_controlled_readiness_v1",
        "product_id": "dio_regops",
        "case_id": case["case_id"],
        "operator_id": operator_id,
        "processed_at": now,
        "profile_id": profile_id,
        "internal_processing": "COMPLETE",
        "readiness_state": materialization["readiness_decision"]["state"],
        "readiness_pack_fingerprint": pack_fingerprint,
        "proof_fingerprint": proof["proof_fingerprint"],
        "ai_regulatory_component_state": component["state"],
        "ai_regulatory_component_fingerprint": component.get("envelope_fingerprint"),
        "generic_executor_gate": _gate(case, "generic_executor")["state"],
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
        "legal_clearance_created": False,
        "professional_decision_created": False,
        "filing_authority_created": False,
        "authority_created": False,
        "execution_performed": False,
        "external_effects": False,
        "external_release": False,
    }
    _write(
        output_dir / "REGOPS_PROCESSING_RECEIPT.json",
        json.dumps(receipt, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )

    return {
        "case": case,
        "materialization": materialization,
        "ai_regulatory_component": component,
        "readiness_pack": pack,
        "proof_manifest": proof,
        "receipt": receipt,
        "output_dir": str(output_dir),
    }
