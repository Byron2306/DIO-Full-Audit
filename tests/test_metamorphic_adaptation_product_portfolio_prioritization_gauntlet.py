from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from experiments.metamorphic_adaptation.product_portfolio_prioritization_gauntlet import (
    PRODUCT_PORTFOLIO_PRIORITIZATION_GAUNTLET_READY_TOKEN,
    PRODUCT_PORTFOLIO_PRIORITIZATION_GAUNTLET_REFUSED_TOKEN,
    run_product_portfolio_prioritization_gauntlet,
)


def _write_product_incarnation_pack(path: Path, **overrides) -> None:
    data = {
        "status": "DIO_METAMORPHIC_ADAPTATION_PRODUCT_INCARNATION_MARKETING_PROOF_PACK_READY",
        "starter_incarnation_marketing_language_authorized": True,
        "starter_implementation_claim_authorized": True,
        "product_incarnation_development_evidence": True,
        "commercial_validation_claim_authorized": False,
        "product_market_fit_claim_authorized": False,
        "autonomous_development_authorized": False,
        "authority_expansion_authorized": False,
    }
    data.update(overrides)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def test_refuses_without_explicit_execute(tmp_path):
    pack = tmp_path / "pack.json"
    _write_product_incarnation_pack(pack)

    receipt = run_product_portfolio_prioritization_gauntlet(
        product_incarnation_marketing_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=False,
    )

    assert receipt.status == PRODUCT_PORTFOLIO_PRIORITIZATION_GAUNTLET_REFUSED_TOKEN
    assert receipt.executed is False
    assert receipt.next_build_selection_claim_authorized is False
    assert receipt.allowed_claim_tier == "T0_NO_PORTFOLIO_PRIORITY_CLAIM"


def test_refuses_when_product_incarnation_pack_not_ready(tmp_path):
    pack = tmp_path / "pack.json"
    _write_product_incarnation_pack(pack, status="NOT_READY")

    receipt = run_product_portfolio_prioritization_gauntlet(
        product_incarnation_marketing_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=True,
    )

    assert receipt.status == PRODUCT_PORTFOLIO_PRIORITIZATION_GAUNTLET_REFUSED_TOKEN
    assert receipt.candidate_products_inspected == 0
    assert receipt.adaptive_claim_authorized is False


def test_prioritizes_six_product_incarnations(tmp_path):
    pack = tmp_path / "pack.json"
    _write_product_incarnation_pack(pack)

    receipt = run_product_portfolio_prioritization_gauntlet(
        product_incarnation_marketing_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=True,
    )

    assert receipt.status == PRODUCT_PORTFOLIO_PRIORITIZATION_GAUNTLET_READY_TOKEN
    assert receipt.candidate_products_inspected == 6
    assert receipt.prioritized_products_written == 6
    assert receipt.governed_priority_mean_score > receipt.static_priority_baseline_mean_score
    assert receipt.governed_priority_minus_static_effect >= receipt.minimum_priority_effect
    assert receipt.governed_priority_mean_score >= receipt.minimum_governed_priority_score
    assert receipt.portfolio_prioritization_evidence is True
    assert receipt.next_build_selection_claim_authorized is True
    assert receipt.allowed_claim_tier == "T12_CANDIDATE_GOVERNED_PRODUCT_PORTFOLIO_PRIORITIZATION_EVIDENCE"


def test_priority_queue_preserves_claim_locks(tmp_path):
    pack = tmp_path / "pack.json"
    _write_product_incarnation_pack(pack)
    out = tmp_path / "out"

    receipt = run_product_portfolio_prioritization_gauntlet(
        product_incarnation_marketing_pack_path=pack,
        output_dir=out,
        execute=True,
    )

    queue = json.loads(Path(receipt.priority_queue_path).read_text())
    assert len(queue) == 6
    assert [item["priority_rank"] for item in queue] == [1, 2, 3, 4, 5, 6]
    assert all(item["product_market_fit_claim_authorized"] is False for item in queue)
    assert all(item["commercial_validation_claim_authorized"] is False for item in queue)
    assert all(item["autonomous_development_authorized"] is False for item in queue)
    assert all(item["authority_expansion_authorized"] is False for item in queue)


def test_next_build_selection_is_bounded(tmp_path):
    pack = tmp_path / "pack.json"
    _write_product_incarnation_pack(pack)
    out = tmp_path / "out"

    receipt = run_product_portfolio_prioritization_gauntlet(
        product_incarnation_marketing_pack_path=pack,
        output_dir=out,
        execute=True,
    )

    selection = json.loads(Path(receipt.build_selection_path).read_text())
    assert selection["selected_product_id"] == receipt.next_build_candidate_selected
    assert selection["product_market_fit_claim_authorized"] is False
    assert selection["commercial_validation_claim_authorized"] is False
    assert selection["autonomous_development_authorized"] is False
    assert "Human-reviewed" in selection["next_step"]


def test_summary_and_receipt_are_written(tmp_path):
    pack = tmp_path / "pack.json"
    _write_product_incarnation_pack(pack)
    out = tmp_path / "out"

    receipt = run_product_portfolio_prioritization_gauntlet(
        product_incarnation_marketing_pack_path=pack,
        output_dir=out,
        execute=True,
    )

    summary = json.loads(Path(receipt.summary_path).read_text())
    persisted = json.loads((out / "product_portfolio_prioritization_gauntlet_receipt.json").read_text())
    assert summary["portfolio_prioritization_evidence"] is True
    assert persisted["status"] == PRODUCT_PORTFOLIO_PRIORITIZATION_GAUNTLET_READY_TOKEN
    assert persisted["product_incarnation_marketing_pack_sha256"] == receipt.product_incarnation_marketing_pack_sha256


def test_cli_runner(tmp_path):
    pack = tmp_path / "pack.json"
    _write_product_incarnation_pack(pack)
    out = tmp_path / "out"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_product_portfolio_prioritization_gauntlet.py",
            "--product-incarnation-marketing-pack",
            str(pack),
            "--output",
            str(out),
            "--execute",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert PRODUCT_PORTFOLIO_PRIORITIZATION_GAUNTLET_READY_TOKEN in completed.stdout
    persisted = json.loads((out / "product_portfolio_prioritization_gauntlet_receipt.json").read_text())
    assert persisted["next_build_selection_claim_authorized"] is True


def test_asdict_round_trip_for_receipt(tmp_path):
    pack = tmp_path / "pack.json"
    _write_product_incarnation_pack(pack)

    receipt = run_product_portfolio_prioritization_gauntlet(
        product_incarnation_marketing_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=True,
    )

    payload = json.loads(json.dumps(asdict(receipt)))
    assert payload["status"] == PRODUCT_PORTFOLIO_PRIORITIZATION_GAUNTLET_READY_TOKEN
    assert payload["product_market_fit_claim_authorized"] is False
    assert payload["autonomous_development_authorized"] is False
