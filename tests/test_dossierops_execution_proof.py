from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from products.dossierops_execution_proof import controlled_dossierops_fixture, run_dossierops_execution_proof
from products.product_class_execution_proof import ProductClassExecutionProofError, verify_execution_proof


NOW = "2026-08-17T21:30:00+00:00"


def test_dossierops_execution_proof_runs_real_assembly_without_promoting_release(tmp_path: Path) -> None:
    out = tmp_path / "dossierops"
    result = run_dossierops_execution_proof(
        controlled_dossierops_fixture(),
        output_dir=out,
        operator_id="human.dossierops_execution_proof_test",
        now=NOW,
    )
    proof = result["proof"]
    assert proof["product_id"] == "dio_dossierops"
    assert proof["adapter_family"] == "controlled_dossier_assembly"
    assert proof["executor_id"] == "controlled_dossier_assembly_v1"
    assert proof["suggested_engine"] == "document_studio"
    assert proof["execution_proof_state"] == "CONTROLLED_ROUTE_PROVED"
    assert proof["processor_invoked"] is True
    assert proof["controlled_processor_execution"] is True
    assert proof["document_studio_execution_performed"] is False
    assert proof["human_review_gate"] == "NEEDS_YOU"
    assert proof["external_release_gate"] == "REFUSE"
    assert proof["authority_created"] is False
    assert proof["external_effects"] is False
    assert proof["external_release"] is False
    assert proof["public_launch_ready"] is False
    assert verify_execution_proof(out) == proof
    assert (out / "DOSSIEROPS_CONTROLLED_DOSSIER.zip").is_file()
    assert (out / "DOSSIEROPS_DOSSIER_INDEX.json").is_file()
    assert (out / "DOSSIEROPS_PROCESSING_RECEIPT.json").is_file()


def test_dossierops_execution_proof_refuses_released_document_studio_fixture(tmp_path: Path) -> None:
    fixture = copy.deepcopy(controlled_dossierops_fixture())
    fixture["document_studio_receipt"]["release"] = {
        "delivery_released": True,
        "human_approval_required": True,
        "release_readiness": "released",
    }
    with pytest.raises(ValueError, match="claims delivery release"):
        run_dossierops_execution_proof(
            fixture,
            output_dir=tmp_path / "released",
            operator_id="human.dossierops_execution_proof_test",
            now=NOW,
        )


def test_dossierops_execution_proof_detects_top_level_tamper(tmp_path: Path) -> None:
    out = tmp_path / "tamper"
    run_dossierops_execution_proof(
        controlled_dossierops_fixture(),
        output_dir=out,
        operator_id="human.dossierops_execution_proof_test",
        now=NOW,
    )
    path = out / "PRODUCT_EXECUTION_PROOF.json"
    proof = json.loads(path.read_text(encoding="utf-8"))
    proof["public_launch_ready"] = True
    path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(ProductClassExecutionProofError, match="fingerprint mismatch"):
        verify_execution_proof(out)
