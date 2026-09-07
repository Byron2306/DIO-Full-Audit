from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from experiments.metamorphic_adaptation.product_portfolio_marketing_proof_pack import (
    PRODUCT_PORTFOLIO_MARKETING_PROOF_PACK_READY_TOKEN,
    PRODUCT_PORTFOLIO_MARKETING_PROOF_PACK_REFUSED_TOKEN,
    build_product_portfolio_marketing_proof_pack,
)


def _write_priority(path: Path, **overrides) -> None:
    data = {
        "status": "DIO_METAMORPHIC_ADAPTATION_PRODUCT_PORTFOLIO_PRIORITIZATION_GAUNTLET_READY",
        "portfolio_prioritization_evidence": True,
        "next_build_selection_claim_authorized": True,
        "adaptive_claim_authorized": True,
        "product_market_fit_claim_authorized": False,
        "commercial_validation_claim_authorized": False,
        "autonomous_development_authorized": False,
        "authority_expansion_authorized": False,
        "candidate_products_inspected": 6,
        "prioritized_products_written": 6,
        "next_build_candidate_selected": "DIO_TRUST_DOSSIER_STUDIO",
        "static_priority_baseline_mean_score": 0.172333,
        "governed_priority_mean_score": 0.8015,
        "governed_priority_minus_static_effect": 0.629167,
    }
    data.update(overrides)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def test_builds_marketing_pack_from_ready_priority_receipt(tmp_path):
    priority = tmp_path / "priority.json"
    _write_priority(priority)

    receipt = build_product_portfolio_marketing_proof_pack(
        product_portfolio_prioritization_path=priority,
        output_dir=tmp_path / "out",
    )

    assert receipt.status == PRODUCT_PORTFOLIO_MARKETING_PROOF_PACK_READY_TOKEN
    assert receipt.marketing_claim_tier == "T12_MARKETING_SAFE_GOVERNED_PRODUCT_PORTFOLIO_PRIORITIZATION"
    assert receipt.portfolio_prioritization_marketing_language_authorized is True
    assert receipt.next_build_selection_claim_authorized is True
    assert receipt.next_build_candidate_selected == "DIO_TRUST_DOSSIER_STUDIO"
    assert receipt.governed_priority_minus_static_effect == 0.629167


def test_refuses_when_priority_receipt_not_ready(tmp_path):
    priority = tmp_path / "priority.json"
    _write_priority(priority, status="NOT_READY")

    receipt = build_product_portfolio_marketing_proof_pack(
        product_portfolio_prioritization_path=priority,
        output_dir=tmp_path / "out",
    )

    assert receipt.status == PRODUCT_PORTFOLIO_MARKETING_PROOF_PACK_REFUSED_TOKEN
    assert receipt.marketing_claim_tier == "T0_NO_PORTFOLIO_MARKETING_CLAIM"
    assert receipt.adaptive_claim_authorized is False
    assert receipt.next_build_selection_claim_authorized is False


def test_preserves_all_external_and_overclaim_locks(tmp_path):
    priority = tmp_path / "priority.json"
    _write_priority(priority)

    receipt = build_product_portfolio_marketing_proof_pack(
        product_portfolio_prioritization_path=priority,
        output_dir=tmp_path / "out",
    )

    assert receipt.product_market_fit_claim_authorized is False
    assert receipt.commercial_validation_claim_authorized is False
    assert receipt.autonomous_development_authorized is False
    assert receipt.autonomous_action_claim_authorized is False
    assert receipt.world_first_claim_authorized is False
    assert receipt.agi_claim_authorized is False
    assert receipt.authority_expansion_authorized is False


def test_writes_claims_copy_and_receipt(tmp_path):
    priority = tmp_path / "priority.json"
    _write_priority(priority)
    out = tmp_path / "out"

    receipt = build_product_portfolio_marketing_proof_pack(
        product_portfolio_prioritization_path=priority,
        output_dir=out,
    )

    claims = json.loads(Path(receipt.portfolio_claims_path).read_text())
    copy = Path(receipt.portfolio_copy_path).read_text()
    persisted = json.loads((out / "product_portfolio_marketing_proof_pack_receipt.json").read_text())

    assert claims["proof_numbers"]["next_build_candidate_selected"] == "DIO_TRUST_DOSSIER_STUDIO"
    assert "DIO Product Portfolio Prioritization Marketing Proof Pack" in copy
    assert "Not product-market fit" in copy
    assert persisted["status"] == PRODUCT_PORTFOLIO_MARKETING_PROOF_PACK_READY_TOKEN


def test_cli_runner(tmp_path):
    priority = tmp_path / "priority.json"
    _write_priority(priority)
    out = tmp_path / "out"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_product_portfolio_marketing_proof_pack.py",
            "--product-portfolio-prioritization",
            str(priority),
            "--output",
            str(out),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert PRODUCT_PORTFOLIO_MARKETING_PROOF_PACK_READY_TOKEN in completed.stdout


def test_asdict_round_trip(tmp_path):
    priority = tmp_path / "priority.json"
    _write_priority(priority)

    receipt = build_product_portfolio_marketing_proof_pack(
        product_portfolio_prioritization_path=priority,
        output_dir=tmp_path / "out",
    )

    payload = json.loads(json.dumps(asdict(receipt)))
    assert payload["status"] == PRODUCT_PORTFOLIO_MARKETING_PROOF_PACK_READY_TOKEN
    assert payload["publication_authorized"] is False
    assert payload["agi_claim_authorized"] is False
