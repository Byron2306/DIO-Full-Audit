from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from products.dossierops.runner import load_dossierops_profile, run_controlled_dossierops_assembly
from products.governed_case import new_case
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
ROUTES_PATH = ROOT / "config" / "product_class_routes.json"
RECONCILIATION_PATH = ROOT / "config" / "product_class_reconciliation.json"
PROFILE_PATH = ROOT / "config" / "products" / "profiles" / "dossierops.json"
PRODUCT_ID = "dio_dossierops"
PROFILE_ID = "dossierops"
PROCESSOR_ID = "controlled_dossier_assembly_v1"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _profile_contract() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    profile = load_dossierops_profile()
    routes = _read_json(ROUTES_PATH)
    reconciliation = _read_json(RECONCILIATION_PATH)
    route = (routes.get("product_classes") or {}).get(PROFILE_ID)
    extension = (reconciliation.get("genuine_profile_extensions") or {}).get(PROFILE_ID)
    if not isinstance(route, dict) or not isinstance(extension, dict):
        raise ProductClassExecutionProofError("DossierOps route/reconciliation contract is missing")
    if route.get("route_kind") != "profile_extension" or route.get("auto_promotable") is not False:
        raise ProductClassExecutionProofError("DossierOps route boundary drifted")
    if route.get("suggested_engine") != "document_studio" or extension.get("suggested_engine") != "document_studio":
        raise ProductClassExecutionProofError("DossierOps must remain bound to Document Studio review artifacts")
    if profile.get("suggested_engine_binding") != "document_studio_review_artifacts":
        raise ProductClassExecutionProofError("DossierOps profile engine binding drifted")
    for field in ("authority_created", "external_effects", "external_release"):
        if profile.get(field) is not False:
            raise ProductClassExecutionProofError(f"DossierOps profile illegally promotes {field}")
    return profile, route, extension


def controlled_dossierops_fixture() -> dict[str, Any]:
    return {
        "fixture_kind": "dio.controlled_product_class_fixture.v1",
        "profile_id": PROFILE_ID,
        "intake_authority_approved": True,
        "source_authority_scope": "controlled_fixture_only",
        "document_studio_receipt": {
            "schema": "dio.document_studio.receipt.v1",
            "job_id": "DOC-REVIEW-PROOF-001",
            "status": "human_review_required",
            "release": {
                "delivery_released": False,
                "human_approval_required": True,
                "release_readiness": "blocked_pending_human_approval",
            },
        },
        "working_paper": "Authorised controlled internal review artifact for DossierOps execution proof.\n",
    }


def _verify_result(
    *,
    output_dir: Path,
    result: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    receipt = result.get("receipt") or {}
    proof_manifest = result.get("proof_manifest") or {}

    if receipt.get("schema") != "dio.dossier_assembly.controlled_processing_receipt.v1":
        raise ProductClassExecutionProofError("DossierOps unexpected controlled-processing receipt schema")
    if receipt.get("processor_id") != PROCESSOR_ID:
        raise ProductClassExecutionProofError("DossierOps processor identity mismatch")
    if receipt.get("product_id") != PRODUCT_ID or receipt.get("profile_id") != PROFILE_ID:
        raise ProductClassExecutionProofError("DossierOps processor product/profile identity drifted")
    if receipt.get("internal_processing") != "COMPLETE" or receipt.get("assembly_performed") is not True:
        raise ProductClassExecutionProofError("DossierOps controlled assembly did not complete")
    if receipt.get("product_execution_proved") is not False:
        raise ProductClassExecutionProofError("DossierOps inner processor cannot promote product execution proof")
    if receipt.get("generic_executor_gate") != "refuse":
        raise ProductClassExecutionProofError("DossierOps generic executor boundary drifted")
    if receipt.get("human_review_gate") != "NEEDS_YOU" or receipt.get("external_release_gate") != "REFUSE":
        raise ProductClassExecutionProofError("DossierOps human/release gates drifted")
    if receipt.get("document_studio_receipt_count") != 1:
        raise ProductClassExecutionProofError("DossierOps controlled fixture must bind exactly one Document Studio receipt")
    if receipt.get("document_studio_execution_performed") is not False:
        raise ProductClassExecutionProofError("DossierOps cannot relabel artifact binding as Document Studio execution")
    for field in ("execution_performed", "authority_created", "external_effects", "external_release"):
        if receipt.get(field) is not False:
            raise ProductClassExecutionProofError(f"DossierOps controlled assembly illegally promotes {field}")
    if any((receipt.get("forbidden_outcomes_created") or {}).values()):
        raise ProductClassExecutionProofError("DossierOps forbidden outcome was created")

    if proof_manifest.get("schema") != "dio.dossier_assembly.controlled_proof_manifest.v1":
        raise ProductClassExecutionProofError("DossierOps unexpected proof manifest schema")
    if proof_manifest.get("processor_id") != PROCESSOR_ID:
        raise ProductClassExecutionProofError("DossierOps proof processor identity mismatch")
    if proof_manifest.get("product_id") != PRODUCT_ID or proof_manifest.get("profile_id") != PROFILE_ID:
        raise ProductClassExecutionProofError("DossierOps proof product/profile identity drifted")
    for field in ("execution_performed", "authority_created", "external_effects", "external_release"):
        if proof_manifest.get(field) is not False:
            raise ProductClassExecutionProofError(f"DossierOps proof manifest illegally promotes {field}")
    if any((proof_manifest.get("forbidden_outcomes_created") or {}).values()):
        raise ProductClassExecutionProofError("DossierOps proof manifest created a forbidden outcome")

    receipt_path = output_dir / "DOSSIEROPS_PROCESSING_RECEIPT.json"
    proof_path = output_dir / "PROOF_MANIFEST.json"
    bundle_path = Path(str(result.get("bundle_path") or ""))
    if not receipt_path.is_file() or not proof_path.is_file() or not bundle_path.is_file():
        raise ProductClassExecutionProofError("DossierOps persisted receipt/proof/bundle is missing")
    if _read_json(receipt_path) != receipt or _read_json(proof_path) != proof_manifest:
        raise ProductClassExecutionProofError("DossierOps persisted receipt/proof drifted")
    if _sha_file(bundle_path) != (receipt.get("bundle") or {}).get("sha256"):
        raise ProductClassExecutionProofError("DossierOps bundle hash mismatch")

    artifacts: list[dict[str, Any]] = []
    for row in proof_manifest.get("artifacts") or []:
        filename = str(row.get("filename") or "")
        path = output_dir / filename
        if not filename or not path.is_file():
            raise ProductClassExecutionProofError(f"DossierOps declared artifact is missing: {filename}")
        observed = _sha_file(path)
        if observed != row.get("sha256"):
            raise ProductClassExecutionProofError(f"DossierOps artifact hash mismatch: {filename}")
        artifacts.append({"artifact_type": row.get("artifact_type"), "filename": filename, "sha256": observed})
    artifacts.extend(
        [
            {"artifact_type": "processor_receipt", "filename": receipt_path.name, "sha256": _sha_file(receipt_path)},
            {"artifact_type": "proof_manifest", "filename": proof_path.name, "sha256": _sha_file(proof_path)},
            {"artifact_type": "controlled_dossier_bundle", "filename": bundle_path.name, "sha256": _sha_file(bundle_path)},
        ]
    )
    return receipt, artifacts


def run_dossierops_execution_proof(
    fixture: dict[str, Any],
    *,
    output_dir: Path,
    operator_id: str,
    now: str,
    job_id: str | None = None,
) -> dict[str, Any]:
    if not str(operator_id or "").strip():
        raise ProductClassExecutionProofError("DossierOps execution proof requires an explicit operator_id")
    if not isinstance(fixture, dict) or fixture.get("profile_id") != PROFILE_ID:
        raise ProductClassExecutionProofError("DossierOps controlled fixture identity mismatch")
    if fixture.get("intake_authority_approved") is not True:
        raise ProductClassExecutionProofError("DossierOps controlled fixture requires approved intake authority")

    profile, route, _ = _profile_contract()
    output_dir = output_dir.resolve()
    _assert_output_dir_is_fresh(output_dir)

    with tempfile.TemporaryDirectory(prefix="dio-dossierops-proof-") as tmp:
        fixture_root = Path(tmp)
        doc_receipt_path = fixture_root / "DOCUMENT_STUDIO_RECEIPT.json"
        _write_json(doc_receipt_path, fixture.get("document_studio_receipt") or {})
        working_paper_path = fixture_root / "working-paper.txt"
        working_paper_path.write_text(str(fixture.get("working_paper") or ""), encoding="utf-8")
        source_path = fixture_root / "CONTROLLED_SOURCE.json"
        case_source = {
            "source": {
                "fixture_kind": fixture.get("fixture_kind"),
                "profile_id": PROFILE_ID,
                "authority_scope": fixture.get("source_authority_scope"),
            },
            "evidence": [],
        }
        _write_json(source_path, case_source)
        case = new_case(
            product=PRODUCT_ID,
            job_id=job_id or "proof-dossierops",
            source=case_source,
            source_path=source_path,
            evidence_inputs=["controlled authorised review artifacts", "controlled Document Studio review receipt"],
            expected_outputs=["dossier index", "hash-bound controlled dossier bundle", "proof manifest", "controlled-processing receipt"],
            required_authorities=["fixture_owner", "record_reviewer", "final_release_owner"],
            intake_state="approved",
            now=now,
        )
        result = run_controlled_dossierops_assembly(
            case,
            artifact_inputs=[
                {
                    "artifact_id": "DOCSTUDIO-RECEIPT",
                    "artifact_type": "document_studio_receipt",
                    "source_system": "document_studio",
                    "approval_state": "review_candidate",
                    "path": str(doc_receipt_path),
                },
                {
                    "artifact_id": "WORKPAPER-001",
                    "artifact_type": "working_paper",
                    "source_system": "source_record",
                    "approval_state": "authorised_for_internal_review",
                    "path": str(working_paper_path),
                    "sha256": "sha256:" + _sha_file(working_paper_path),
                },
            ],
            output_dir=output_dir,
            operator_id=operator_id,
            now=now,
        )

    receipt, artifacts = _verify_result(output_dir=output_dir, result=result)
    proof = {
        "schema": PROOF_SCHEMA,
        "product_id": PRODUCT_ID,
        "profile_id": PROFILE_ID,
        "atlas_product_class": "DossierOps",
        "adapter_family": "controlled_dossier_assembly",
        "profile": str(PROFILE_PATH.relative_to(ROOT)),
        "profile_sha256": "sha256:" + _sha_file(PROFILE_PATH),
        "route_contract_sha256": "sha256:" + _sha_file(ROUTES_PATH),
        "reconciliation_sha256": "sha256:" + _sha_file(RECONCILIATION_PATH),
        "fixture_sha256": "sha256:" + _sha_bytes(_canonical(fixture)),
        "source_authority_scope": "controlled_fixture_only",
        "operator_id": operator_id,
        "executed_at": now,
        "execution_capability": "profile.processor.dossierops.assembly",
        "executor_id": PROCESSOR_ID,
        "executor_ref": "products/dossier_assembly.py",
        "suggested_engine": route.get("suggested_engine"),
        "processor_invoked": True,
        "controlled_processor_execution": True,
        "execution_proof_state": "CONTROLLED_ROUTE_PROVED",
        "processor_receipt_schema": receipt.get("schema"),
        "processor_receipt_internal_state": receipt.get("internal_processing"),
        "human_review_gate": receipt.get("human_review_gate"),
        "external_release_gate": receipt.get("external_release_gate"),
        "document_studio_execution_performed": False,
        "authority_created": False,
        "external_effects": False,
        "external_release": False,
        "public_launch_ready": False,
        "artifacts": artifacts,
        "claim_ceiling": (
            "This receipt proves that the bounded DossierOps controlled assembly processor executed over the recorded "
            "controlled fixture and produced a hash-verified dossier index and bundle. It does not prove Document "
            "Studio execution, dossier completeness, legal sufficiency, authenticity, retention authority, external "
            "submission, customer validation, public-launch authority, or external release."
        ),
    }
    proof["proof_fingerprint"] = "sha256:" + _sha_bytes(_canonical(proof))
    _write_json(output_dir / "PRODUCT_EXECUTION_PROOF.json", proof)
    verify_execution_proof(output_dir)
    return {"proof": proof, "processor_result": result, "output_dir": str(output_dir)}
