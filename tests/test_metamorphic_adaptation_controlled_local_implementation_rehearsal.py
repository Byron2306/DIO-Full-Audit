import json
import subprocess
import sys
from pathlib import Path

from experiments.metamorphic_adaptation.controlled_local_implementation_rehearsal import (
    READY_TOKEN,
    run_controlled_local_implementation_rehearsal,
)


def _write_t13_marketing_pack(tmp_path: Path) -> Path:
    path = tmp_path / "selected_product_sprint_marketing_proof_pack_receipt.json"
    path.write_text(
        json.dumps(
            {
                "status": "DIO_METAMORPHIC_ADAPTATION_SELECTED_PRODUCT_SPRINT_MARKETING_PROOF_PACK_READY",
                "selected_product": "DIO_TRUST_DOSSIER_STUDIO",
                "selected_product_sprint_planning_evidence": True,
                "sprint_planning_claim_authorized": True,
                "selected_product_sprint_marketing_language_authorized": True,
                "autonomous_development_authorized": False,
                "commercial_validation_claim_authorized": False,
                "product_market_fit_claim_authorized": False,
                "authority_expansion_authorized": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_rehearsal_builds_controlled_local_implementation_packet(tmp_path):
    pack = _write_t13_marketing_pack(tmp_path)
    out = tmp_path / "out"

    receipt = run_controlled_local_implementation_rehearsal(
        selected_product_sprint_marketing_pack_path=pack,
        output_dir=out,
        execute=True,
    )

    assert receipt.status == READY_TOKEN
    assert receipt.selected_product == "DIO_TRUST_DOSSIER_STUDIO"
    assert receipt.implementation_rehearsal_evidence is True
    assert receipt.local_implementation_rehearsal_claim_authorized is True
    assert receipt.starter_code_claim_authorized is False
    assert receipt.autonomous_development_authorized is False
    assert receipt.product_market_fit_claim_authorized is False
    assert receipt.modules_rehearsed == 5
    assert receipt.test_skeletons_rehearsed == 5
    assert receipt.receipt_schemas_rehearsed == 5
    assert receipt.acceptance_gate_bindings_rehearsed == 20
    assert receipt.controlled_rehearsal_mean_score >= receipt.minimum_controlled_rehearsal_score
    assert receipt.rehearsal_effect_threshold_met is True
    assert receipt.controlled_rehearsal_quality_threshold_met is True
    assert receipt.allowed_claim_tier == "T14_CANDIDATE_CONTROLLED_LOCAL_IMPLEMENTATION_REHEARSAL_EVIDENCE"
    assert (out / "dio_trust_dossier_studio_implementation_rehearsal_plan.json").exists()
    assert (out / "dio_trust_dossier_studio_rehearsal_file_manifest.json").exists()
    assert (out / "controlled_local_implementation_rehearsal_summary.json").exists()
    assert (out / "controlled_local_implementation_rehearsal_receipt.json").exists()


def test_rehearsal_refuses_bad_upstream_pack(tmp_path):
    pack = tmp_path / "bad.json"
    pack.write_text(json.dumps({"status": "BAD"}) + "\n", encoding="utf-8")

    receipt = run_controlled_local_implementation_rehearsal(
        selected_product_sprint_marketing_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=True,
    )

    assert receipt.status == "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_LOCAL_IMPLEMENTATION_REHEARSAL_REFUSED"
    assert receipt.implementation_rehearsal_evidence is False
    assert receipt.local_implementation_rehearsal_claim_authorized is False
    assert receipt.autonomous_development_authorized is False


def test_cli_runner_writes_receipt(tmp_path):
    pack = _write_t13_marketing_pack(tmp_path)
    out = tmp_path / "cli"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_controlled_local_implementation_rehearsal.py",
            "--selected-product-sprint-marketing-pack",
            str(pack),
            "--output",
            str(out),
            "--execute",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert READY_TOKEN in result.stdout
    receipt = json.loads((out / "controlled_local_implementation_rehearsal_receipt.json").read_text(encoding="utf-8"))
    assert receipt["status"] == READY_TOKEN
    assert receipt["selected_product"] == "DIO_TRUST_DOSSIER_STUDIO"
