from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PROVIDER_ID = "contractproof_proof_pack_v1"
PROOF_SCHEMA = "dio.contractproof.proof_manifest.v1"
REQUIRED_OUTPUTS = (
    "requirement_evidence_matrix",
    "gap_report",
    "deadline_register",
    "evidence_inventory",
    "receipt_index",
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_json(path: Path, payload: Any) -> str:
    body = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.write_text(body, encoding="utf-8")
    return _sha256_bytes(body.encode("utf-8"))


def _artifact_payloads(
    case: dict[str, Any],
    obligation_bundle: dict[str, Any],
    sufficiency: dict[str, Any],
    projection_receipt: dict[str, Any],
) -> dict[str, Any]:
    requirement_matrix = {
        "schema": "dio.contractproof.requirement_evidence_matrix.v1",
        "case_id": case["case_id"],
        "rows": [
            {
                "requirement_id": row["requirement_id"],
                "statement": row["statement"],
                "kind": row["kind"],
                "state": row["state"],
                "source_ref": row.get("source_ref"),
                "evidence_ids": list(row.get("evidence_ids") or []),
                "due_at": row.get("due_at"),
                "expires_at": row.get("expires_at"),
            }
            for row in case.get("requirements") or []
        ],
        "human_gate": "NEEDS_YOU",
        "authority_created": False,
    }
    gap_report = {
        "schema": "dio.contractproof.gap_report.v1",
        "case_id": case["case_id"],
        "evidence_sufficiency": sufficiency,
        "obligation_evaluations": obligation_bundle.get("evaluations") or [],
        "human_gate": "NEEDS_YOU",
        "compliance_verdict": None,
    }
    deadline_register = {
        "schema": "dio.contractproof.deadline_register.v1",
        "case_id": case["case_id"],
        "governed_case_deadlines": case.get("deadlines") or [],
        "obligation_deadlines": obligation_bundle.get("deadlines") or [],
        "human_gate": "NEEDS_YOU",
    }
    evidence_inventory = {
        "schema": "dio.contractproof.evidence_inventory.v1",
        "case_id": case["case_id"],
        "evidence": case.get("evidence") or [],
        "count": len(case.get("evidence") or []),
    }
    receipt_index = {
        "schema": "dio.contractproof.receipt_index.v1",
        "case_id": case["case_id"],
        "obligation_bundle_fingerprint": obligation_bundle["fingerprint"],
        "obligation_projection": projection_receipt,
        "event_refs": list(case.get("event_refs") or []),
        "authority_created": False,
        "execution_receipt_claimed": False,
    }
    return {
        "requirement_evidence_matrix": requirement_matrix,
        "gap_report": gap_report,
        "deadline_register": deadline_register,
        "evidence_inventory": evidence_inventory,
        "receipt_index": receipt_index,
    }


def compile_portable_room(
    case: dict[str, Any],
    obligation_bundle: dict[str, Any],
    sufficiency: dict[str, Any],
    projection_receipt: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    """Compile the five ContractProof output-profile artifacts and a hash manifest.

    This is a product-scoped proof adapter, not CapitalRoom. It cannot create
    authority, perform external release, or turn an evidentiary state into a
    legal/compliance verdict.
    """
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    payloads = _artifact_payloads(case, obligation_bundle, sufficiency, projection_receipt)
    artifacts: list[dict[str, Any]] = []
    for output_id in REQUIRED_OUTPUTS:
        filename = f"{output_id.upper()}.json"
        digest = _write_json(output_dir / filename, payloads[output_id])
        artifacts.append({"output_id": output_id, "filename": filename, "sha256": digest})

    identity = {
        "case_id": case["case_id"],
        "obligation_bundle_fingerprint": obligation_bundle["fingerprint"],
        "artifacts": artifacts,
    }
    manifest = {
        "schema": PROOF_SCHEMA,
        "provider_id": PROVIDER_ID,
        "product_id": "dio_contractproof",
        "case_id": case["case_id"],
        "obligation_bundle_fingerprint": obligation_bundle["fingerprint"],
        "proof_fingerprint": f"sha256:{_sha256_bytes(_canonical(identity).encode('utf-8'))}",
        "artifacts": artifacts,
        "human_gate": {
            "state": "NEEDS_YOU",
            "reason": "An authorised contract owner controls any disclosure or contractual judgement based on this pack.",
        },
        "authority_created": False,
        "execution_performed": False,
        "external_release": False,
    }
    manifest_sha = _write_json(output_dir / "PROOF_MANIFEST.json", manifest)
    manifest["manifest_file_sha256"] = manifest_sha
    return manifest


def verify_integrity(output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    path = output_dir / "PROOF_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != PROOF_SCHEMA:
        raise ValueError("unexpected ContractProof proof manifest schema")
    failures: list[str] = []
    observed_outputs: set[str] = set()
    for artifact in manifest.get("artifacts") or []:
        output_id = str(artifact.get("output_id") or "")
        observed_outputs.add(output_id)
        artifact_path = output_dir / str(artifact.get("filename") or "")
        if not artifact_path.is_file():
            failures.append(f"missing:{output_id}")
            continue
        digest = _sha256_bytes(artifact_path.read_bytes())
        if digest != artifact.get("sha256"):
            failures.append(f"hash:{output_id}")
    missing_outputs = sorted(set(REQUIRED_OUTPUTS).difference(observed_outputs))
    failures.extend(f"manifest_missing:{item}" for item in missing_outputs)
    return {
        "schema": "dio.contractproof.integrity_verification.v1",
        "case_id": manifest.get("case_id"),
        "proof_fingerprint": manifest.get("proof_fingerprint"),
        "verified": not failures,
        "failures": failures,
        "authority_created": False,
        "execution_performed": False,
    }


def prepare_disclosure(output_dir: Path) -> dict[str, Any]:
    verification = verify_integrity(output_dir)
    if not verification["verified"]:
        raise ValueError(f"ContractProof proof pack failed integrity verification: {verification['failures']}")
    return {
        "schema": "dio.contractproof.disclosure_candidate.v1",
        "product_id": "dio_contractproof",
        "case_id": verification["case_id"],
        "proof_fingerprint": verification["proof_fingerprint"],
        "state": "INTERNAL_REVIEW_CANDIDATE",
        "human_gate": {
            "state": "NEEDS_YOU",
            "reason": "The internal proof pack requires authorised human review before any disclosure decision.",
        },
        "external_release_gate": "REFUSE",
        "authority_created": False,
        "release_authority_created": False,
    }
