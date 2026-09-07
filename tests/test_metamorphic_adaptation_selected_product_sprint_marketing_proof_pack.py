import json
import subprocess
import sys
from pathlib import Path

from experiments.metamorphic_adaptation.selected_product_sprint_marketing_proof_pack import (
    READY_TOKEN,
    build_selected_product_sprint_marketing_proof_pack,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sprint_receipt() -> dict:
    return {
        "status": "DIO_METAMORPHIC_ADAPTATION_SELECTED_PRODUCT_SPRINT_PLANNING_GAUNTLET_READY",
        "selected_product": "DIO_TRUST_DOSSIER_STUDIO",
        "work_packages_planned": 5,
        "acceptance_gates_planned": 20,
        "evidence_receipts_planned": 15,
        "static_sprint_baseline_mean_score": 0.19,
        "governed_sprint_plan_mean_score": 0.98,
        "governed_sprint_minus_static_effect": 0.79,
        "selected_product_sprint_planning_evidence": True,
        "sprint_planning_claim_authorized": True,
        "adaptive_claim_authorized": True,
        "autonomous_development_authorized": False,
        "autonomous_action_claim_authorized": False,
        "commercial_validation_claim_authorized": False,
        "product_market_fit_claim_authorized": False,
        "publication_authorized": False,
        "spend_authorized": False,
        "fulfilment_authorized": False,
        "professional_approval_claim_authorized": False,
        "world_first_claim_authorized": False,
        "agi_claim_authorized": False,
        "authority_expansion_authorized": False,
    }


def test_builds_marketing_pack_with_safe_claims(tmp_path: Path) -> None:
    sprint_path = tmp_path / "selected_product_sprint_planning_gauntlet_receipt.json"
    output_dir = tmp_path / "out"
    _write_json(sprint_path, _sprint_receipt())

    receipt = build_selected_product_sprint_marketing_proof_pack(sprint_path, output_dir)

    assert receipt.status == READY_TOKEN
    assert receipt.marketing_claim_tier == "T13_MARKETING_SAFE_SELECTED_PRODUCT_SPRINT_PLANNING"
    assert receipt.selected_product == "DIO_TRUST_DOSSIER_STUDIO"
    assert receipt.selected_product_sprint_marketing_language_authorized is True
    assert receipt.sprint_planning_claim_authorized is True
    assert receipt.autonomous_development_authorized is False
    assert receipt.commercial_validation_claim_authorized is False
    assert receipt.product_market_fit_claim_authorized is False
    assert receipt.world_first_claim_authorized is False
    assert receipt.agi_claim_authorized is False
    assert receipt.authority_expansion_authorized is False
    assert Path(receipt.sprint_marketing_claims_path).exists()
    assert Path(receipt.sprint_marketing_copy_path).exists()

    copy = Path(receipt.sprint_marketing_copy_path).read_text(encoding="utf-8")
    assert "DIO_TRUST_DOSSIER_STUDIO" in copy
    assert "not autonomous development" in copy
    assert "Not product-market fit" in copy
    assert "world-first" in copy


def test_rejects_unready_sprint_receipt(tmp_path: Path) -> None:
    sprint_path = tmp_path / "bad.json"
    _write_json(sprint_path, {**_sprint_receipt(), "status": "NOT_READY"})

    try:
        build_selected_product_sprint_marketing_proof_pack(sprint_path, tmp_path / "out")
    except ValueError as exc:
        assert "unexpected sprint planning status" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_cli_runner_writes_receipt(tmp_path: Path) -> None:
    sprint_path = tmp_path / "selected_product_sprint_planning_gauntlet_receipt.json"
    output_dir = tmp_path / "cli-out"
    _write_json(sprint_path, _sprint_receipt())

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_selected_product_sprint_marketing_proof_pack.py",
            "--selected-product-sprint-planning",
            str(sprint_path),
            "--output",
            str(output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert READY_TOKEN in result.stdout
    receipt_path = output_dir / "selected_product_sprint_marketing_proof_pack_receipt.json"
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == READY_TOKEN
    assert receipt["selected_product"] == "DIO_TRUST_DOSSIER_STUDIO"
