from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from products.changeproof_execution_proof import (
    DECISION_PATH,
    PRODUCT_ID,
    controlled_changeproof_fixture,
    run_changeproof_execution_proof,
)
from products.product_class_execution_proof import ProductClassExecutionProofError, verify_execution_proof


NOW = "2026-08-18T00:05:00+02:00"
OPERATOR = "human.changeproof_execution_proof_test"


def test_changeproof_executes_only_inside_operator_approved_bounded_scope(tmp_path: Path) -> None:
    fixture = controlled_changeproof_fixture()
    out = tmp_path / "changeproof"
    result = run_changeproof_execution_proof(
        fixture,
        output_dir=out,
        operator_id=OPERATOR,
        now=NOW,
    )
    proof = verify_execution_proof(out)
    assert proof == result["proof"]
    assert proof["product_id"] == PRODUCT_ID
    assert proof["atlas_product_class"] == "changeproof"
    assert proof["adapter_family"] == "ai_trust_changeproof_scope_equivalence"
    assert proof["execution_proof_state"] == "CONTROLLED_ROUTE_PROVED"
    assert proof["controlled_processor_execution"] is True
    assert proof["human_review_gate"] == "NEEDS_YOU"
    assert proof["external_release_gate"] == "REFUSE"
    assert proof["authority_created"] is False
    assert proof["external_effects"] is False
    assert proof["external_release"] is False
    assert proof["public_launch_ready"] is False
    assert {"model_fingerprint", "prompt_fingerprint"}.issubset(set(proof["drift_fields"]))
    assert proof["challenge_states"] == {
        "drift": "CONTESTED",
        "evaluation": "STALE",
        "integrity": "CONTESTED",
    }
    assert proof["route_snapshot"]["candidate_reconciliation_state"] == "equivalence_review_required"
    assert proof["route_snapshot"]["operator_decision"] == "scope_equivalent"
    assert proof["route_snapshot"]["approved_scope_kind"] == "bounded_ai_model_system_change_assurance"
    assert (out / "AI_TRUST_DOSSIER.json").is_file()
    assert (out / "AI_TRUST_DOSSIER.html").is_file()
    assert (out / "AI_TRUST_DOSSIER.docx").is_file()
    assert (out / "AI_TRUST_DOSSIER.pdf").is_file()
    assert (out / "AI_TRUST_RECEIPT.json").is_file()
    assert (out / "PROOF_MANIFEST.json").is_file()
    assert (out / "PRODUCT_EXECUTION_PROOF.json").is_file()


def test_changeproof_decision_records_exact_narrow_scope() -> None:
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    assert decision["decision"] == "scope_equivalent"
    assert decision["atlas_product_class"] == "changeproof"
    assert decision["candidate_product_id"] == PRODUCT_ID
    assert decision["approved_by"] == "human.Byron2306"
    assert set(decision["approved_scope"]["includes"]) == {
        "baseline_identity",
        "current_identity",
        "model_change",
        "prompt_change",
        "policy_change",
        "connector_change",
        "environment_change",
        "reevaluation",
    }
    assert set(decision["approved_scope"]["excludes"]) == {
        "generic_enterprise_change_management",
        "residual_risk_acceptance",
        "automatic_promotion",
        "public_launch_authority",
        "external_release_authority",
    }
    assert decision["auto_promotable"] is False
    assert decision["authority_created"] is False
    assert decision["public_launch_authorized"] is False
    assert decision["external_release_authorized"] is False


def test_changeproof_refuses_wrong_source_type_and_dirty_output(tmp_path: Path) -> None:
    wrong = copy.deepcopy(controlled_changeproof_fixture())
    wrong["source_type"] = "enterprise_change"
    with pytest.raises(ProductClassExecutionProofError, match="source_type=ai_model_change"):
        run_changeproof_execution_proof(
            wrong,
            output_dir=tmp_path / "wrong",
            operator_id=OPERATOR,
            now=NOW,
        )

    dirty = tmp_path / "dirty"
    dirty.mkdir()
    (dirty / "stale.txt").write_text("stale\n", encoding="utf-8")
    with pytest.raises(ProductClassExecutionProofError, match="must be empty"):
        run_changeproof_execution_proof(
            controlled_changeproof_fixture(),
            output_dir=dirty,
            operator_id=OPERATOR,
            now=NOW,
        )
