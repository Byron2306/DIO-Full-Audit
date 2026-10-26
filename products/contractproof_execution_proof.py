from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from products.phase11_1_gauntlet import ACCEPTANCE_TOKEN, run_phase11_1_gauntlet
from products.product_class_execution_proof import (
    PROOF_SCHEMA,
    ProductClassExecutionProofError,
    _assert_output_dir_is_fresh,
    _canonical,
    _sha_bytes,
    _sha_file,
    _write_json,
    verify_execution_proof,
)


ROOT = Path(__file__).resolve().parents[1]
RECONCILIATION_PATH = ROOT / "config" / "product_class_reconciliation.json"
ROUTES_PATH = ROOT / "config" / "product_class_routes.json"
PRODUCT_ID = "dio_contractproof"
PROFILE_KEY = "contractproof"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _contract() -> tuple[dict[str, Any], dict[str, Any]]:
    reconciliation = _read_json(RECONCILIATION_PATH)
    routes = _read_json(ROUTES_PATH)
    binding = (reconciliation.get("exact_canonical_incarnations") or {}).get(PROFILE_KEY)
    route = (routes.get("product_classes") or {}).get(PROFILE_KEY)
    if not isinstance(binding, dict) or not isinstance(route, dict):
        raise ProductClassExecutionProofError("ContractProof reconciliation/route contract is missing")
    if binding.get("canonical_product_id") != PRODUCT_ID:
        raise ProductClassExecutionProofError("ContractProof canonical product identity drifted")
    if binding.get("canonical_executor") != "product.executor.contractproof":
        raise ProductClassExecutionProofError("ContractProof canonical executor binding drifted")
    if binding.get("inbound_owner") != "vesper":
        raise ProductClassExecutionProofError("ContractProof inbound ownership must remain Vesper")
    if route.get("auto_promotable") is not False:
        raise ProductClassExecutionProofError("ContractProof cannot become auto-promotable")
    return binding, route


def _require_file(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise ProductClassExecutionProofError(f"ContractProof controlled journey artifact is missing: {relative}")
    return {"artifact_type": "journey_artifact", "filename": relative, "sha256": _sha_file(path)}


def run_contractproof_execution_proof(
    *,
    output_dir: Path,
    operator_id: str,
    now: str,
) -> dict[str, Any]:
    if not str(operator_id or "").strip():
        raise ProductClassExecutionProofError("ContractProof execution proof requires an explicit operator_id")
    binding, route = _contract()
    output_dir = output_dir.resolve()
    _assert_output_dir_is_fresh(output_dir)

    journey_root = output_dir / "vesper_contractproof_journey"
    receipt = run_phase11_1_gauntlet(output_dir=journey_root, root=ROOT)
    if receipt.get("acceptance_token") != ACCEPTANCE_TOKEN:
        raise ProductClassExecutionProofError("ContractProof Phase 11.1 acceptance token is missing")
    if receipt.get("deterministic_execution") != "PASS":
        raise ProductClassExecutionProofError("ContractProof Vesper journey is not deterministic")
    for field, expected in {
        "source_binding": "PASS",
        "proof_integrity": "PASS",
        "vesper_intake": "PASS",
        "outlook_draft": "PASS",
        "evidence_fanout_guard": "PASS",
        "external_delivery": "REFUSE",
        "human_release": "NEEDS_YOU",
        "sent": False,
    }.items():
        if receipt.get(field) != expected:
            raise ProductClassExecutionProofError(f"ContractProof Phase 11.1 boundary drifted: {field}")

    first = journey_root / "first"
    proof_dir = first / str(receipt.get("proof_output_dir") or "")
    contract_receipt_path = proof_dir / "CONTRACTPROOF_RECEIPT.json"
    if not contract_receipt_path.is_file():
        raise ProductClassExecutionProofError("ContractProof downstream execution receipt is missing")
    downstream = _read_json(contract_receipt_path)
    if downstream.get("schema") != "dio.contractproof.execution_receipt.v1":
        raise ProductClassExecutionProofError("ContractProof downstream receipt schema drifted")
    if downstream.get("executor_id") != "contractproof_internal_runner_v1":
        raise ProductClassExecutionProofError("ContractProof downstream executor identity drifted")
    if downstream.get("product_id") != PRODUCT_ID or downstream.get("internal_processing") != "COMPLETE":
        raise ProductClassExecutionProofError("ContractProof downstream processor did not complete")
    if downstream.get("proof_integrity_verified") is not True:
        raise ProductClassExecutionProofError("ContractProof downstream proof integrity was not verified")
    if downstream.get("human_fulfilment_gate") != "NEEDS_YOU" or downstream.get("external_release_gate") != "REFUSE":
        raise ProductClassExecutionProofError("ContractProof downstream human/release gate drifted")
    for field in ("authority_created", "waiver_created", "legal_opinion_created", "external_effects", "external_release"):
        if downstream.get(field) is not False:
            raise ProductClassExecutionProofError(f"ContractProof downstream receipt illegally promotes {field}")

    vesper_receipts = list((first / "state" / "vesper" / "intakes").glob("*/VESPER_INTAKE_RECEIPT.json"))
    if len(vesper_receipts) != 1:
        raise ProductClassExecutionProofError("ContractProof controlled journey must persist exactly one Vesper intake receipt")
    vesper = _read_json(vesper_receipts[0])
    if vesper.get("schema") != "dio.vesper.intake_receipt.v1" or vesper.get("identity") != "Vesper, DIO Presence Core":
        raise ProductClassExecutionProofError("ContractProof Vesper intake identity drifted")
    if vesper.get("automatic_external_actions") is not False or vesper.get("external_reply") != "REFUSE" or vesper.get("human_gate") != "NEEDS_YOU":
        raise ProductClassExecutionProofError("ContractProof Vesper external-action boundary drifted")

    draft_path = first / str(receipt.get("outlook_draft_ref") or "")
    draft = _read_json(draft_path)
    if draft.get("state") != "DRAFT_ONLY" or draft.get("send_authorized") is not False or draft.get("sent") is not False:
        raise ProductClassExecutionProofError("ContractProof delivery draft escaped DRAFT_ONLY boundary")
    if draft.get("external_effects") is not False:
        raise ProductClassExecutionProofError("ContractProof delivery draft created external effects")

    relative_artifacts = [
        "vesper_contractproof_journey/PHASE11_1_RECEIPT.json",
        "vesper_contractproof_journey/first/fulfilment/proof/CONTRACTPROOF_RECEIPT.json",
        "vesper_contractproof_journey/first/fulfilment/proof/PROOF_MANIFEST.json",
        "vesper_contractproof_journey/first/fulfilment/proof/EVIDENCE_PACK.json",
        "vesper_contractproof_journey/first/fulfilment/proof/EVIDENCE_PACK.html",
        "vesper_contractproof_journey/first/fulfilment/proof/EVIDENCE_PACK.docx",
        "vesper_contractproof_journey/first/fulfilment/proof/EVIDENCE_PACK.pdf",
        "vesper_contractproof_journey/first/fulfilment/proof/EVIDENCE_RECONCILIATION.json",
        "vesper_contractproof_journey/first/fulfilment/proof/EVIDENCE_RECONCILIATION.html",
        str(vesper_receipts[0].relative_to(output_dir)),
        str(draft_path.relative_to(output_dir)),
    ]
    artifacts = [_require_file(output_dir, relative) for relative in relative_artifacts]

    proof: dict[str, Any] = {
        "schema": PROOF_SCHEMA,
        "product_id": PRODUCT_ID,
        "adapter_family": "vesper_contractproof_attachment_journey",
        "route_contract_sha256": "sha256:" + _sha_file(ROUTES_PATH),
        "reconciliation_sha256": "sha256:" + _sha_file(RECONCILIATION_PATH),
        "operator_id": operator_id,
        "executed_at": now,
        "inbound_owner": "vesper",
        "execution_capability": "product.executor.contractproof",
        "executor_id": "contractproof_internal_runner_v1",
        "executor_ref": "products/contractproof/runner.py",
        "processor_invoked": True,
        "controlled_processor_execution": True,
        "execution_proof_state": "CONTROLLED_ROUTE_PROVED",
        "processor_receipt_schema": downstream.get("schema"),
        "processor_receipt_internal_state": downstream.get("internal_processing"),
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
        "authority_created": False,
        "external_effects": False,
        "external_release": False,
        "public_launch_ready": False,
        "artifacts": artifacts,
        "journey": {
            "acceptance_token": receipt.get("acceptance_token"),
            "deterministic_execution": receipt.get("deterministic_execution"),
            "source_binding": receipt.get("source_binding"),
            "proof_integrity": receipt.get("proof_integrity"),
            "vesper_intake": receipt.get("vesper_intake"),
            "outlook_draft": receipt.get("outlook_draft"),
            "evidence_fanout_guard": receipt.get("evidence_fanout_guard"),
            "unresolved_attachment_count": receipt.get("unresolved_attachment_count"),
            "sent": receipt.get("sent"),
        },
        "route_snapshot": {
            "canonical_product_id": binding.get("canonical_product_id"),
            "canonical_executor": binding.get("canonical_executor"),
            "inbound_owner": binding.get("inbound_owner"),
            "auto_promotable": route.get("auto_promotable"),
        },
        "claim_ceiling": (
            "This receipt proves the controlled Vesper-owned ContractProof attachment route executed deterministically, "
            "reconciled evidence, invoked the canonical ContractProof processor, verified the proof pack, and stopped at a "
            "draft-only delivery boundary. It does not prove contract fulfilment, legal advice, waiver, customer acceptance, "
            "external delivery, public-launch authority, or repeatable commercial demand."
        ),
    }
    proof["proof_fingerprint"] = "sha256:" + _sha_bytes(_canonical(proof))
    _write_json(output_dir / "PRODUCT_EXECUTION_PROOF.json", proof)
    verify_execution_proof(output_dir)
    return {"proof": proof, "journey_receipt": receipt, "downstream_receipt": downstream, "output_dir": str(output_dir)}
