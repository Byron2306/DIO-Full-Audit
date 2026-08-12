from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dio.obligations.engine import build as build_obligations
from dio.obligations.engine import project as project_obligations
from dio.obligations.extractor import extract
from evidence.sufficiency import assess_sufficiency
from products.compiler import compile_manifest
from products.governed_case import add_evidence, new_case, validate_case

from .proof import compile_portable_room, prepare_disclosure, verify_integrity


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "config" / "products" / "manifests" / "contractproof.json"
EXECUTOR_ID = "contractproof_internal_runner_v1"
RECEIPT_SCHEMA = "dio.contractproof.execution_receipt.v1"


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _map_evidence_to_obligations(
    case: dict[str, Any],
    source: dict[str, Any],
    evidence_inputs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates = extract(source)
    by_locator = {str(row["source_locator"]): str(row["obligation_id"]) for row in candidates}
    mapped: list[dict[str, Any]] = []
    for index, item in enumerate(evidence_inputs, start=1):
        locators = [str(value) for value in item.get("target_locators") or []]
        if not locators:
            raise ValueError(f"ContractProof evidence input {index} requires target_locators")
        missing = [locator for locator in locators if locator not in by_locator]
        if missing:
            raise ValueError(f"ContractProof evidence input {index} references unknown obligation locators: {missing}")
        case_evidence = add_evidence(
            case,
            kind=str(item.get("evidence_kind") or "source_record"),
            source_ref=str(item.get("source_ref") or f"evidence://contractproof/{index}"),
            sha256=item.get("sha256"),
            observed_at=item.get("observed_at"),
            effective_at=item.get("effective_at"),
            expires_at=item.get("expires_at"),
            authority_grade=str(item.get("authority_grade") or "source_backed"),
            trust_state=str(item.get("trust_state") or "captured_untrusted"),
            freshness_state=str(item.get("freshness_state") or "unknown"),
        )
        mapped.append(
            {
                "evidence_id": case_evidence["evidence_id"],
                "obligation_ids": [by_locator[locator] for locator in locators],
                "evidence_kind": str(item.get("evidence_kind") or "source_record"),
                "source_ref": case_evidence["source_ref"],
                "relation": str(item.get("relation") or "supports"),
                "trust_state": case_evidence["trust_state"],
                "freshness_state": case_evidence["freshness_state"],
            }
        )
    return mapped


def run_contractproof(
    source: dict[str, Any],
    evidence_inputs: list[dict[str, Any]],
    *,
    output_dir: Path,
    operator_id: str,
    now: str,
    job_id: str | None = None,
) -> dict[str, Any]:
    """Execute the bounded internal ContractProof processing lane.

    The executor performs deterministic internal processing and local artifact
    writes only. It does not adjudicate fulfilment, grant authority, waive an
    obligation, send anything externally, or release the resulting proof pack.
    """
    operator_id = str(operator_id or "").strip()
    if not operator_id:
        raise ValueError("ContractProof internal execution requires an explicit operator_id")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    compiled = compile_manifest(ROOT, MANIFEST_PATH)
    capabilities = {row["capability_id"]: row for row in compiled["capability_plan"]}
    unresolved = [
        capability_id
        for capability_id, row in capabilities.items()
        if row["required"] and row["resolution_state"] != "RESOLVED"
    ]
    if unresolved:
        raise RuntimeError(f"ContractProof cannot execute with unresolved required capabilities: {sorted(unresolved)}")
    executor = capabilities["product.executor.contractproof"].get("provider") or {}
    if executor.get("provider_id") != EXECUTOR_ID or executor.get("execution_capable") is not True:
        raise RuntimeError("ContractProof bounded executor is not the compiler-selected execution provider")
    if compiled["gates"]["execution"]["state"] != "NEEDS_YOU":
        raise RuntimeError("ContractProof compiler execution gate must remain NEEDS_YOU for human-initiated internal execution")
    if compiled["gates"]["external_release"]["state"] != "REFUSE":
        raise RuntimeError("ContractProof internal proof profile must refuse external release")

    expected_outputs = [str(item) for item in compiled["output_plan"]["required_output_types"]]
    resolved_job_id = str(job_id or f"golden-{source.get('source_id') or 'contract'}")
    case = new_case(
        product="dio_contractproof",
        job_id=resolved_job_id,
        source={"source": {"path": str(source.get("source_ref") or "contract://unknown")}},
        source_path=MANIFEST_PATH,
        evidence_inputs=[],
        expected_outputs=expected_outputs,
        required_authorities=["contract_owner", "evidence_reviewer"],
        intake_state="approved",
        framework_ids=["framework.contract_generic"],
        subject_ref=str(source.get("source_ref") or ""),
        now=now,
    )
    mapped_evidence = _map_evidence_to_obligations(case, source, evidence_inputs)
    obligation_bundle = build_obligations(source, evidence_records=mapped_evidence, now=now)
    projection_receipt = project_obligations(obligation_bundle, case)
    validate_case(case)
    sufficiency = assess_sufficiency(case)

    proof_manifest = compile_portable_room(
        case,
        obligation_bundle,
        sufficiency,
        projection_receipt,
        output_dir,
    )
    integrity = verify_integrity(output_dir)
    if not integrity["verified"]:
        raise RuntimeError(f"ContractProof proof pack integrity failed: {integrity['failures']}")
    disclosure = prepare_disclosure(output_dir)

    observed_outputs = {str(row["output_id"]) for row in proof_manifest["artifacts"]}
    if observed_outputs != set(expected_outputs):
        raise RuntimeError(
            f"ContractProof output profile mismatch: expected {sorted(expected_outputs)}, observed {sorted(observed_outputs)}"
        )

    status_counts: dict[str, int] = {}
    for row in obligation_bundle.get("evaluations") or []:
        status = str(row["status"])
        status_counts[status] = status_counts.get(status, 0) + 1

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "executor_id": EXECUTOR_ID,
        "product_id": "dio_contractproof",
        "case_id": case["case_id"],
        "job_id": resolved_job_id,
        "operator_id": operator_id,
        "executed_at": now,
        "composition_fingerprint": compiled["composition_fingerprint"],
        "compilation_fingerprint": compiled["compilation_fingerprint"],
        "obligation_bundle_fingerprint": obligation_bundle["fingerprint"],
        "proof_fingerprint": proof_manifest["proof_fingerprint"],
        "proof_integrity_verified": True,
        "required_outputs": expected_outputs,
        "obligation_status_counts": status_counts,
        "evidence_sufficiency_state": sufficiency["state"],
        "internal_processing": "COMPLETE",
        "human_fulfilment_gate": "NEEDS_YOU",
        "human_disclosure_gate": disclosure["human_gate"]["state"],
        "external_release_gate": "REFUSE",
        "authority_created": False,
        "waiver_created": False,
        "legal_opinion_created": False,
        "external_effects": False,
        "external_release": False,
        "maturity_evidence": {
            "candidate_state": "internal_proof",
            "basis": "A controlled internal ContractProof case completed all required work-pattern operations and produced a hash-verified output pack.",
        },
    }
    _write_json(output_dir / "CONTRACTPROOF_RECEIPT.json", receipt)
    _write_json(output_dir / "GOVERNED_CASE.json", case)
    _write_json(output_dir / "OBLIGATION_BUNDLE.json", obligation_bundle)
    _write_json(output_dir / "EVIDENCE_SUFFICIENCY.json", sufficiency)
    _write_json(output_dir / "DISCLOSURE_CANDIDATE.json", disclosure)
    return {
        "receipt": receipt,
        "case": case,
        "obligation_bundle": obligation_bundle,
        "sufficiency": sufficiency,
        "proof_manifest": proof_manifest,
        "integrity": integrity,
        "disclosure": disclosure,
        "output_dir": str(output_dir),
    }
