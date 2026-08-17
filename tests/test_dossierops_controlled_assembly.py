from __future__ import annotations

import copy
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from products.dossierops.runner import (
    load_dossierops_profile,
    run_controlled_dossierops_assembly,
)
from products.governed_case import new_case
from products.meta import load_meta_registry
from products.registry import load_portfolio


ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-08-17T13:30:00+00:00"


def _case(
    tmp_path: Path,
    *,
    product: str = "dio_dossierops",
    intake_state: str = "approved",
) -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source_path = tmp_path / "source.json"
    source_path.write_text("{}", encoding="utf-8")
    return new_case(
        product=product,
        job_id=f"dossierops-controlled-{product}-{intake_state}",
        source={"source": {}, "evidence": []},
        source_path=source_path,
        evidence_inputs=["authorised review artifacts", "optional Document Studio review receipt"],
        expected_outputs=[
            "dossier index",
            "hash-bound controlled dossier bundle",
            "proof manifest",
            "controlled-processing receipt",
        ],
        required_authorities=[
            "dossier_owner",
            "record_reviewer",
            "final_release_owner",
        ],
        intake_state=intake_state,
        now=NOW,
    )


def _document_studio_receipt(path: Path, *, released: bool = False) -> Path:
    payload = {
        "schema": "dio.document_studio.receipt.v1",
        "job_id": "DOC-REVIEW-001",
        "status": "human_review_required",
        "release": {
            "delivery_released": released,
            "human_approval_required": True,
            "release_readiness": (
                "released" if released else "blocked_pending_human_approval"
            ),
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_controlled_dossierops_assembles_hash_bound_review_pack_without_release_authority(
    tmp_path: Path,
) -> None:
    case = _case(tmp_path / "case")
    before = {
        field: copy.deepcopy(case[field])
        for field in ("gates", "actions", "decisions", "outputs")
    }
    doc_receipt = _document_studio_receipt(tmp_path / "DOCUMENT_STUDIO_RECEIPT.json")
    working_paper = tmp_path / "working-paper.txt"
    working_paper.write_text("Authorised internal review artifact.\n", encoding="utf-8")
    working_sha = hashlib.sha256(working_paper.read_bytes()).hexdigest()

    result = run_controlled_dossierops_assembly(
        case,
        artifact_inputs=[
            {
                "artifact_id": "DOCSTUDIO-RECEIPT",
                "artifact_type": "document_studio_receipt",
                "source_system": "document_studio",
                "approval_state": "review_candidate",
                "path": str(doc_receipt),
            },
            {
                "artifact_id": "WORKPAPER-001",
                "artifact_type": "working_paper",
                "source_system": "source_record",
                "approval_state": "authorised_for_internal_review",
                "path": str(working_paper),
                "sha256": "sha256:" + working_sha,
            },
        ],
        output_dir=tmp_path / "out",
        operator_id="human.dossierops_test",
        now=NOW,
    )

    index = result["dossier_index"]
    assert [row["artifact_id"] for row in index["items"]] == [
        "DOCSTUDIO-RECEIPT",
        "WORKPAPER-001",
    ]
    assert index["document_studio_binding"]["receipt_count"] == 1
    assert index["document_studio_binding"]["document_studio_execution_performed"] is False
    assert index["human_review"] == {
        "dossier_completeness": "NEEDS_YOU",
        "record_sufficiency": "NEEDS_YOU",
        "final_release": "NEEDS_YOU",
    }
    assert index["external_release"] == "REFUSE"
    assert not any(index["forbidden_outcomes_created"].values())

    proof = result["proof_manifest"]
    assert proof["authority_created"] is False
    assert proof["execution_performed"] is False
    assert proof["external_effects"] is False
    assert proof["external_release"] is False
    assert not any(proof["forbidden_outcomes_created"].values())

    out = Path(result["output_dir"])
    for artifact in proof["artifacts"]:
        path = out / artifact["filename"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]

    receipt = result["receipt"]
    assert receipt["internal_processing"] == "COMPLETE"
    assert receipt["assembly_performed"] is True
    assert receipt["product_execution_proved"] is False
    assert receipt["generic_executor_gate"] == "refuse"
    assert receipt["human_review_gate"] == "NEEDS_YOU"
    assert receipt["external_release_gate"] == "REFUSE"
    assert receipt["document_studio_receipt_count"] == 1
    assert receipt["document_studio_execution_performed"] is False
    assert receipt["bundle"]["contains_processing_receipt"] is False
    assert receipt["authority_created"] is False
    assert receipt["execution_performed"] is False
    assert receipt["external_effects"] is False
    assert receipt["external_release"] is False

    bundle = Path(result["bundle_path"])
    assert hashlib.sha256(bundle.read_bytes()).hexdigest() == receipt["bundle"]["sha256"]
    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
    assert "DOSSIEROPS_DOSSIER_INDEX.json" in names
    assert "DOSSIEROPS_DOSSIER_INDEX.html" in names
    assert "PROOF_MANIFEST.json" in names
    assert "items/DOCSTUDIO-RECEIPT.json" in names
    assert "items/WORKPAPER-001.txt" in names
    assert "DOSSIEROPS_PROCESSING_RECEIPT.json" not in names

    for field in before:
        assert case[field] == before[field]


def test_dossierops_refuses_document_studio_receipt_that_claims_release(
    tmp_path: Path,
) -> None:
    case = _case(tmp_path / "case")
    released = _document_studio_receipt(
        tmp_path / "released-document-studio-receipt.json",
        released=True,
    )
    with pytest.raises(ValueError, match="claims delivery release"):
        run_controlled_dossierops_assembly(
            case,
            artifact_inputs=[
                {
                    "artifact_id": "DOCSTUDIO-RELEASED",
                    "artifact_type": "document_studio_receipt",
                    "source_system": "document_studio",
                    "path": str(released),
                }
            ],
            output_dir=tmp_path / "out",
            operator_id="human.dossierops_test",
            now=NOW,
        )


def test_dossierops_refuses_unapproved_intake_and_wrong_product(tmp_path: Path) -> None:
    artifact = tmp_path / "record.txt"
    artifact.write_text("record", encoding="utf-8")

    pending = _case(tmp_path / "pending", intake_state="pending")
    with pytest.raises(RuntimeError, match="approved intake authority"):
        run_controlled_dossierops_assembly(
            pending,
            artifact_inputs=[
                {
                    "artifact_id": "RECORD-001",
                    "artifact_type": "record",
                    "path": str(artifact),
                }
            ],
            output_dir=tmp_path / "pending-out",
            operator_id="human.dossierops_test",
            now=NOW,
        )

    wrong = _case(tmp_path / "wrong", product="dio_vendorproof")
    with pytest.raises(ValueError, match="requires product=dio_dossierops"):
        run_controlled_dossierops_assembly(
            wrong,
            artifact_inputs=[
                {
                    "artifact_id": "RECORD-001",
                    "artifact_type": "record",
                    "path": str(artifact),
                }
            ],
            output_dir=tmp_path / "wrong-out",
            operator_id="human.dossierops_test",
            now=NOW,
        )


def test_dossierops_profile_remains_unpromoted_and_outside_canonical_portfolio() -> None:
    profile = load_dossierops_profile()
    assert profile["identity_state"] == "genuine_profile_extension_unpromoted"
    assert profile["canonical_portfolio_registration"] is False
    assert profile["scope_basis"] == "atlas_product_class_name_and_reconciliation_route_only"
    assert profile["suggested_engine_binding"] == "document_studio_review_artifacts"

    portfolio_ids = {row["id"] for row in load_portfolio()["products"]}
    composition_ids = {
        row["product_id"]
        for row in load_meta_registry()["vertical_compositions"]
    }
    assert "dio_dossierops" not in portfolio_ids
    assert "dio_dossierops" not in composition_ids

    reconciliation = json.loads(
        (ROOT / "config" / "product_class_reconciliation.json").read_text(
            encoding="utf-8"
        )
    )
    assert reconciliation["genuine_profile_extensions"]["dossierops"]["suggested_engine"] == "document_studio"
    assert "dossierops" not in reconciliation["exact_canonical_incarnations"]
    assert "dossierops" not in reconciliation["equivalence_candidates"]
    assert "dossierops" not in reconciliation["resolved_composition_bindings"]
