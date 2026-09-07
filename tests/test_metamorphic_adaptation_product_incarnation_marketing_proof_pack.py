from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from experiments.metamorphic_adaptation.product_incarnation_marketing_proof_pack import (
    PRODUCT_INCARNATION_MARKETING_PROOF_PACK_READY_TOKEN,
    PRODUCT_INCARNATION_MARKETING_PROOF_PACK_REFUSED_TOKEN,
    build_product_incarnation_marketing_proof_pack,
)


def _write_gauntlet(path: Path, **overrides) -> None:
    data = {
        "status": "DIO_METAMORPHIC_ADAPTATION_PRODUCT_INCARNATION_DEVELOPMENT_GAUNTLET_READY",
        "adaptive_claim_authorized": True,
        "product_composition_claim_authorized": True,
        "starter_implementation_claim_authorized": True,
        "product_incarnation_development_evidence": True,
        "candidate_products_loaded": 6,
        "starter_incarnations_written": 6,
        "manifests_written": 6,
        "evidence_contracts_written": 6,
        "acceptance_test_plans_written": 6,
        "readmes_written": 6,
        "static_scaffold_baseline_mean_score": 0.18,
        "governed_incarnation_mean_score": 1.0,
        "governed_incarnation_minus_static_effect": 0.82,
        "minimum_governed_incarnation_score": 0.84,
        "minimum_incarnation_development_effect": 0.4,
        "commercial_validation_claim_authorized": False,
        "product_market_fit_claim_authorized": False,
        "autonomous_development_authorized": False,
        "authority_expansion_authorized": False,
    }
    data.update(overrides)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def test_builds_ready_marketing_pack(tmp_path):
    gauntlet = tmp_path / "gauntlet.json"
    _write_gauntlet(gauntlet)

    receipt = build_product_incarnation_marketing_proof_pack(
        product_incarnation_gauntlet_path=gauntlet,
        output_dir=tmp_path / "out",
    )

    assert receipt.status == PRODUCT_INCARNATION_MARKETING_PROOF_PACK_READY_TOKEN
    assert receipt.marketing_claim_tier == "T11_MARKETING_SAFE_GOVERNED_PRODUCT_INCARNATION_DEVELOPMENT"
    assert receipt.starter_incarnation_marketing_language_authorized is True
    assert receipt.product_incarnation_development_evidence is True
    assert receipt.starter_incarnations_written == 6
    assert receipt.manifests_written == 6
    assert receipt.evidence_contracts_written == 6
    assert receipt.acceptance_test_plans_written == 6
    assert receipt.readmes_written == 6
    assert receipt.governed_incarnation_minus_static_effect == 0.82


def test_refuses_when_incarnation_gauntlet_not_ready(tmp_path):
    gauntlet = tmp_path / "gauntlet.json"
    _write_gauntlet(gauntlet, status="NOT_READY")

    receipt = build_product_incarnation_marketing_proof_pack(
        product_incarnation_gauntlet_path=gauntlet,
        output_dir=tmp_path / "out",
    )

    assert receipt.status == PRODUCT_INCARNATION_MARKETING_PROOF_PACK_REFUSED_TOKEN
    assert receipt.marketing_claim_tier == "T0_NO_PRODUCT_INCARNATION_MARKETING_CLAIM"
    assert receipt.starter_incarnation_marketing_language_authorized is False
    assert receipt.adaptive_claim_authorized is False


def test_preserves_all_overclaim_locks(tmp_path):
    gauntlet = tmp_path / "gauntlet.json"
    _write_gauntlet(gauntlet)

    receipt = build_product_incarnation_marketing_proof_pack(
        product_incarnation_gauntlet_path=gauntlet,
        output_dir=tmp_path / "out",
    )

    assert receipt.commercial_validation_claim_authorized is False
    assert receipt.product_market_fit_claim_authorized is False
    assert receipt.autonomous_development_authorized is False
    assert receipt.publication_authorized is False
    assert receipt.spend_authorized is False
    assert receipt.fulfilment_authorized is False
    assert receipt.world_first_claim_authorized is False
    assert receipt.agi_claim_authorized is False
    assert receipt.autonomous_action_claim_authorized is False
    assert receipt.authority_expansion_authorized is False


def test_writes_claims_copy_and_receipt(tmp_path):
    gauntlet = tmp_path / "gauntlet.json"
    _write_gauntlet(gauntlet)
    out = tmp_path / "out"

    receipt = build_product_incarnation_marketing_proof_pack(
        product_incarnation_gauntlet_path=gauntlet,
        output_dir=out,
    )

    claims = json.loads(Path(receipt.product_incarnation_claims_path).read_text())
    copy = Path(receipt.product_incarnation_copy_path).read_text()
    persisted = json.loads((out / "product_incarnation_marketing_proof_pack_receipt.json").read_text())

    assert claims["marketing_claim_tier"] == receipt.marketing_claim_tier
    assert len(claims["allowed_public_claims"]) == receipt.allowed_public_claims_count
    assert len(claims["forbidden_public_claims"]) == receipt.forbidden_public_claims_count
    assert "DIO does not merely compose product specifications" in copy
    assert "Not product-market fit" in copy
    assert persisted["status"] == PRODUCT_INCARNATION_MARKETING_PROOF_PACK_READY_TOKEN


def test_cli_runner(tmp_path):
    gauntlet = tmp_path / "gauntlet.json"
    _write_gauntlet(gauntlet)
    out = tmp_path / "out"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_product_incarnation_marketing_proof_pack.py",
            "--product-incarnation-gauntlet",
            str(gauntlet),
            "--output",
            str(out),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert PRODUCT_INCARNATION_MARKETING_PROOF_PACK_READY_TOKEN in completed.stdout
    persisted = json.loads((out / "product_incarnation_marketing_proof_pack_receipt.json").read_text())
    assert persisted["starter_incarnation_marketing_language_authorized"] is True


def test_asdict_round_trip(tmp_path):
    gauntlet = tmp_path / "gauntlet.json"
    _write_gauntlet(gauntlet)

    receipt = build_product_incarnation_marketing_proof_pack(
        product_incarnation_gauntlet_path=gauntlet,
        output_dir=tmp_path / "out",
    )

    payload = json.loads(json.dumps(asdict(receipt)))
    assert payload["status"] == PRODUCT_INCARNATION_MARKETING_PROOF_PACK_READY_TOKEN
    assert payload["autonomous_development_authorized"] is False
    assert payload["product_market_fit_claim_authorized"] is False
