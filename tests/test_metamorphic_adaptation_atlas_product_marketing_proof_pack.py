from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from experiments.metamorphic_adaptation.atlas_product_marketing_proof_pack import (
    ATLAS_PRODUCT_MARKETING_PROOF_PACK_READY_TOKEN,
    ATLAS_PRODUCT_MARKETING_PROOF_PACK_REFUSED_TOKEN,
    build_atlas_product_marketing_proof_pack,
)


def _write_morphology_receipt(path: Path, **overrides) -> None:
    data = {
        "status": "DIO_METAMORPHIC_ADAPTATION_AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_READY",
        "audience_morphology_evidence": True,
        "adaptive_claim_authorized": True,
        "commercial_validation_claim_authorized": False,
        "world_first_claim_authorized": False,
        "agi_claim_authorized": False,
        "authority_expansion_authorized": False,
    }
    data.update(overrides)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _write_atlas_receipt(path: Path, **overrides) -> None:
    data = {
        "status": "DIO_METAMORPHIC_ADAPTATION_ATLAS_GUIDED_PRODUCT_COMPOSITION_GAUNTLET_READY",
        "atlas_guided_product_composition_evidence": True,
        "higher_grade_product_composition_evidence": True,
        "product_composition_claim_authorized": True,
        "adaptive_claim_authorized": True,
        "commercial_validation_claim_authorized": False,
        "autonomous_development_authorized": False,
        "world_first_claim_authorized": False,
        "agi_claim_authorized": False,
        "authority_expansion_authorized": False,
        "opportunities_processed": 6,
        "atlas_work_maps_bound": 6,
        "development_ready_specs_written": 6,
        "static_product_baseline_mean_score": 0.17,
        "adaptive_atlas_product_mean_score": 1.0,
        "adaptive_atlas_minus_static_effect": 0.83,
        "minimum_adaptive_atlas_product_score": 0.84,
        "minimum_atlas_product_effect": 0.4,
    }
    data.update(overrides)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def test_refuses_when_morphology_receipt_not_ready(tmp_path):
    morphology = tmp_path / "morphology.json"
    atlas = tmp_path / "atlas.json"
    _write_morphology_receipt(morphology, status="NOT_READY")
    _write_atlas_receipt(atlas)

    receipt = build_atlas_product_marketing_proof_pack(
        audience_morphology_gauntlet_path=morphology,
        atlas_product_composition_path=atlas,
        output_dir=tmp_path / "out",
    )

    assert receipt.status == ATLAS_PRODUCT_MARKETING_PROOF_PACK_REFUSED_TOKEN
    assert receipt.product_evolution_marketing_language_authorized is False
    assert receipt.adaptive_claim_authorized is False
    assert receipt.marketing_claim_tier == "T0_NO_PRODUCT_COMPOSITION_MARKETING_CLAIM"


def test_refuses_when_atlas_receipt_not_ready(tmp_path):
    morphology = tmp_path / "morphology.json"
    atlas = tmp_path / "atlas.json"
    _write_morphology_receipt(morphology)
    _write_atlas_receipt(atlas, higher_grade_product_composition_evidence=False)

    receipt = build_atlas_product_marketing_proof_pack(
        audience_morphology_gauntlet_path=morphology,
        atlas_product_composition_path=atlas,
        output_dir=tmp_path / "out",
    )

    assert receipt.status == ATLAS_PRODUCT_MARKETING_PROOF_PACK_REFUSED_TOKEN
    assert receipt.product_composition_claim_authorized is False
    assert receipt.development_ready_specs_written == 0


def test_builds_t10_marketing_safe_product_evolution_pack(tmp_path):
    morphology = tmp_path / "morphology.json"
    atlas = tmp_path / "atlas.json"
    _write_morphology_receipt(morphology)
    _write_atlas_receipt(atlas)

    receipt = build_atlas_product_marketing_proof_pack(
        audience_morphology_gauntlet_path=morphology,
        atlas_product_composition_path=atlas,
        output_dir=tmp_path / "out",
    )

    assert receipt.status == ATLAS_PRODUCT_MARKETING_PROOF_PACK_READY_TOKEN
    assert receipt.marketing_claim_tier == "T10_MARKETING_SAFE_ATLAS_GUIDED_DOMAIN_PRODUCT_COMPOSITION"
    assert receipt.product_evolution_marketing_language_authorized is True
    assert receipt.adaptive_claim_authorized is True
    assert receipt.product_composition_claim_authorized is True
    assert receipt.higher_grade_product_composition_evidence is True
    assert receipt.opportunities_processed == 6
    assert receipt.atlas_work_maps_bound == 6
    assert receipt.development_ready_specs_written == 6
    assert receipt.adaptive_atlas_minus_static_effect == 0.83
    assert receipt.allowed_public_claims_count == 7
    assert receipt.forbidden_public_claims_count == 12


def test_claim_locks_are_preserved(tmp_path):
    morphology = tmp_path / "morphology.json"
    atlas = tmp_path / "atlas.json"
    _write_morphology_receipt(morphology)
    _write_atlas_receipt(atlas)

    receipt = build_atlas_product_marketing_proof_pack(
        audience_morphology_gauntlet_path=morphology,
        atlas_product_composition_path=atlas,
        output_dir=tmp_path / "out",
    )

    assert receipt.commercial_validation_claim_authorized is False
    assert receipt.product_market_fit_claim_authorized is False
    assert receipt.autonomous_development_authorized is False
    assert receipt.professional_approval_claim_authorized is False
    assert receipt.publication_authorized is False
    assert receipt.spend_authorized is False
    assert receipt.fulfilment_authorized is False
    assert receipt.world_first_claim_authorized is False
    assert receipt.agi_claim_authorized is False
    assert receipt.autonomous_action_claim_authorized is False
    assert receipt.authority_expansion_authorized is False


def test_claims_and_copy_are_written(tmp_path):
    morphology = tmp_path / "morphology.json"
    atlas = tmp_path / "atlas.json"
    out = tmp_path / "out"
    _write_morphology_receipt(morphology)
    _write_atlas_receipt(atlas)

    receipt = build_atlas_product_marketing_proof_pack(
        audience_morphology_gauntlet_path=morphology,
        atlas_product_composition_path=atlas,
        output_dir=out,
    )

    claims = json.loads(Path(receipt.atlas_product_claims_path).read_text())
    copy = Path(receipt.atlas_product_copy_path).read_text()
    persisted = json.loads((out / "atlas_product_marketing_proof_pack_receipt.json").read_text())

    assert claims["marketing_claim_tier"] == "T10_MARKETING_SAFE_ATLAS_GUIDED_DOMAIN_PRODUCT_COMPOSITION"
    assert claims["proof_numbers"]["development_ready_specs_written"] == 6
    assert claims["claim_locks"]["autonomous_development_authorized"] is False
    assert "DIO does not merely generate product ideas" in copy
    assert "Not product-market fit" in copy
    assert persisted["status"] == ATLAS_PRODUCT_MARKETING_PROOF_PACK_READY_TOKEN


def test_cli_runner(tmp_path):
    morphology = tmp_path / "morphology.json"
    atlas = tmp_path / "atlas.json"
    out = tmp_path / "out"
    _write_morphology_receipt(morphology)
    _write_atlas_receipt(atlas)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_atlas_product_marketing_proof_pack.py",
            "--audience-morphology-gauntlet",
            str(morphology),
            "--atlas-product-composition",
            str(atlas),
            "--output",
            str(out),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert ATLAS_PRODUCT_MARKETING_PROOF_PACK_READY_TOKEN in completed.stdout
    persisted = json.loads((out / "atlas_product_marketing_proof_pack_receipt.json").read_text())
    assert persisted["product_evolution_marketing_language_authorized"] is True


def test_asdict_round_trip(tmp_path):
    morphology = tmp_path / "morphology.json"
    atlas = tmp_path / "atlas.json"
    _write_morphology_receipt(morphology)
    _write_atlas_receipt(atlas)

    receipt = build_atlas_product_marketing_proof_pack(
        audience_morphology_gauntlet_path=morphology,
        atlas_product_composition_path=atlas,
        output_dir=tmp_path / "out",
    )

    payload = json.loads(json.dumps(asdict(receipt)))
    assert payload["status"] == ATLAS_PRODUCT_MARKETING_PROOF_PACK_READY_TOKEN
    assert payload["product_market_fit_claim_authorized"] is False
    assert payload["agi_claim_authorized"] is False
