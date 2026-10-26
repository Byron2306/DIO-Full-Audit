from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
from typing import Any

from products.governed_case import canonical_hash, validate_case
from products.regulatory.core import build_regulatory_context

from .materializer import materialize_accreditation_case


COMPONENT_PRODUCT_ID = "dio_educationaccreditationproof"
COMPONENT_RELATION = "composition_reuse"
SOURCE_TYPE = "education_accreditation_context"


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
            "reason": "No regulated accreditation context was supplied.",
            "authority_created": False,
            "external_effects": False,
            "external_release": "REFUSE",
        }

    if payload.get("source_type") != SOURCE_TYPE:
        raise ValueError(
            f"Accreditation regulatory component requires source_type={SOURCE_TYPE}"
        )

    envelope = build_regulatory_context(
        COMPONENT_PRODUCT_ID,
        payload,
        now=now,
    )
    if envelope["authority_created"] is not False:
        raise RuntimeError("Regulatory component illegally created authority.")
    if envelope["external_effects"] is not False:
        raise RuntimeError("Regulatory component illegally created external effects.")
    if envelope["external_release"] != "REFUSE":
        raise RuntimeError("Regulatory component external release boundary drifted.")

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


def _gap_register(
    case: dict[str, Any],
    matrix: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    criterion_by_requirement = {
        row["requirement_id"]: row["criterion_id"]
        for row in matrix
    }
    result = []
    for challenge in case["challenges"]:
        if challenge["state"] != "open":
            continue
        criterion_id = criterion_by_requirement.get(challenge["target_id"])
        if not criterion_id:
            continue
        result.append(
            {
                "criterion_id": criterion_id,
                "challenge_id": challenge["challenge_id"],
                "challenge_type": challenge["challenge_type"],
                "severity": challenge["severity"],
                "hypothesis": challenge["hypothesis"],
                "evidence_ids": list(challenge["evidence_ids"]),
            }
        )
    return sorted(
        result,
        key=lambda row: (row["criterion_id"], row["challenge_id"]),
    )


def _review_pack(
    case: dict[str, Any],
    materialization: dict[str, Any],
    component: dict[str, Any],
) -> dict[str, Any]:
    matrix = materialization["standards_evidence_matrix"]
    gaps = _gap_register(case, matrix)
    corrective_actions = [
        {
            "criterion_id": row["criterion_id"],
            "challenge_id": row["challenge_id"],
            "state": "NEEDS_YOU",
            "action": None,
            "owner": None,
            "reason": "Corrective action requires authorised human review and assignment.",
        }
        for row in gaps
    ]
    return {
        "schema": "dio.accreditation.review_pack.v1",
        "product_id": "dio_accreditation",
        "case_id": case["case_id"],
        "framework_id": materialization["framework_id"],
        "standards_evidence_matrix": matrix,
        "gap_register": gaps,
        "corrective_action_tracker": corrective_actions,
        "regulated_component_binding": component,
        "human_review": {
            "quality_assurance_review": "NEEDS_YOU",
            "signatory_review": "NEEDS_YOU",
            "signatory_receipt_created": False,
        },
        "authority_created": False,
        "external_effects": False,
        "external_release": "REFUSE",
    }


def _html_pack(pack: dict[str, Any]) -> bytes:
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(row['criterion_id']))}</td>"
        f"<td>{html.escape(str(row['readiness_state']))}</td>"
        f"<td>{html.escape(str(row['statement']))}</td>"
        f"<td>{len(row['evidence_ids'])}</td>"
        f"<td>{len(row['open_challenge_ids'])}</td>"
        "</tr>"
        for row in pack["standards_evidence_matrix"]
    )
    page = (
        "<!doctype html><meta charset='utf-8'>"
        "<title>DIO Accreditation Controlled Review Pack</title>"
        "<h1>DIO Accreditation Controlled Review Pack</h1>"
        "<p><strong>HUMAN REVIEW REQUIRED. EXTERNAL RELEASE REFUSED.</strong></p>"
        "<table border='1' cellspacing='0' cellpadding='6'>"
        "<tr><th>Criterion</th><th>State</th><th>Statement</th>"
        "<th>Evidence</th><th>Open gaps</th></tr>"
        f"{rows}</table>"
        "<h2>Regulated component</h2>"
        f"<pre>{html.escape(json.dumps(pack['regulated_component_binding'], indent=2, sort_keys=True))}</pre>"
        "<p>This controlled review pack creates no accreditation decision, "
        "institutional attestation, regulator acceptance, authority, external effect, "
        "or release authority.</p>"
    )
    return page.encode("utf-8")


def run_controlled_accreditation_review(
    case: dict[str, Any],
    *,
    framework_id: str,
    criteria: list[dict[str, Any]],
    evidence_inputs: list[dict[str, Any]],
    gaps: list[dict[str, Any]] | None,
    regulatory_context: dict[str, Any] | None,
    output_dir: Path,
    operator_id: str,
    now: str,
) -> dict[str, Any]:
    if not str(operator_id or "").strip():
        raise ValueError("Accreditation controlled processing requires an explicit operator_id.")
    if _gate(case, "intake_authority")["state"] != "allow":
        raise RuntimeError("Accreditation controlled processing requires approved intake authority.")
    if _gate(case, "generic_executor")["state"] != "refuse":
        raise RuntimeError("Generic executor boundary drifted before Accreditation processing.")
    if _gate(case, "external_release")["state"] == "allow":
        raise RuntimeError("Accreditation controlled processing cannot start with external release ALLOW.")

    materialization = materialize_accreditation_case(
        case,
        framework_id=framework_id,
        criteria=criteria,
        evidence_inputs=evidence_inputs,
        gaps=gaps,
        raised_by=operator_id,
    )
    component = _component_binding(regulatory_context, now=now)
    pack = _review_pack(case, materialization, component)
    validate_case(case)

    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered = {
        "JSON": (
            "ACCREDITATION_REVIEW_PACK.json",
            json.dumps(pack, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n",
        ),
        "HTML": ("ACCREDITATION_REVIEW_PACK.html", _html_pack(pack)),
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
        "schema": "dio.accreditation.controlled_proof_manifest.v1",
        "provider_id": "accreditation_controlled_review_pack_v1",
        "product_id": "dio_accreditation",
        "artifact_type": "proof_room_manifest",
        "case_id": case["case_id"],
        "framework_id": framework_id,
        "review_pack_fingerprint": pack_fingerprint,
        "regulated_component": {
            "product_id": COMPONENT_PRODUCT_ID,
            "relationship": COMPONENT_RELATION,
            "state": component["state"],
            "envelope_fingerprint": component.get("envelope_fingerprint"),
        },
        "case_sha256": canonical_hash(case),
        "artifacts": artifacts,
        "human_gate": {
            "state": "NEEDS_YOU",
            "reason": "Quality-assurance review and any institutional signatory action remain human-authority bound.",
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
        "schema": "dio.accreditation.controlled_processing_receipt.v1",
        "processor_id": "accreditation_controlled_review_v1",
        "product_id": "dio_accreditation",
        "case_id": case["case_id"],
        "operator_id": operator_id,
        "processed_at": now,
        "framework_id": framework_id,
        "review_pack_fingerprint": pack_fingerprint,
        "proof_fingerprint": proof["proof_fingerprint"],
        "regulated_component_state": component["state"],
        "regulated_component_fingerprint": component.get("envelope_fingerprint"),
        "internal_processing": "COMPLETE",
        "generic_executor_gate": _gate(case, "generic_executor")["state"],
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
        "signatory_receipt_created": False,
        "accreditation_decision_created": False,
        "institutional_attestation_created": False,
        "regulator_acceptance_created": False,
        "authority_created": False,
        "execution_performed": False,
        "external_effects": False,
        "external_release": False,
    }
    _write(
        output_dir / "ACCREDITATION_PROCESSING_RECEIPT.json",
        json.dumps(receipt, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    return {
        "case": case,
        "materialization": materialization,
        "regulated_component": component,
        "review_pack": pack,
        "proof_manifest": proof,
        "receipt": receipt,
        "output_dir": str(output_dir),
    }
