from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from experiments.metamorphic_adaptation.selected_product_sprint_planning_gauntlet import (
    SELECTED_PRODUCT_SPRINT_PLANNING_GAUNTLET_READY_TOKEN,
    SELECTED_PRODUCT_SPRINT_PLANNING_GAUNTLET_REFUSED_TOKEN,
    run_selected_product_sprint_planning_gauntlet,
)


def _write_portfolio_pack(path: Path, **overrides) -> None:
    data = {
        "status": "DIO_METAMORPHIC_ADAPTATION_PRODUCT_PORTFOLIO_MARKETING_PROOF_PACK_READY",
        "portfolio_prioritization_marketing_language_authorized": True,
        "next_build_selection_claim_authorized": True,
        "next_build_candidate_selected": "DIO_TRUST_DOSSIER_STUDIO",
        "commercial_validation_claim_authorized": False,
        "product_market_fit_claim_authorized": False,
        "autonomous_development_authorized": False,
        "authority_expansion_authorized": False,
    }
    data.update(overrides)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def test_refuses_without_explicit_execute(tmp_path):
    pack = tmp_path / "pack.json"
    _write_portfolio_pack(pack)

    receipt = run_selected_product_sprint_planning_gauntlet(
        product_portfolio_marketing_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=False,
    )

    assert receipt.status == SELECTED_PRODUCT_SPRINT_PLANNING_GAUNTLET_REFUSED_TOKEN
    assert receipt.executed is False
    assert receipt.sprint_planning_claim_authorized is False
    assert receipt.allowed_claim_tier == "T0_NO_SELECTED_PRODUCT_SPRINT_PLANNING_CLAIM"


def test_refuses_when_portfolio_pack_not_ready(tmp_path):
    pack = tmp_path / "pack.json"
    _write_portfolio_pack(pack, status="NOT_READY")

    receipt = run_selected_product_sprint_planning_gauntlet(
        product_portfolio_marketing_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=True,
    )

    assert receipt.status == SELECTED_PRODUCT_SPRINT_PLANNING_GAUNTLET_REFUSED_TOKEN
    assert receipt.work_packages_planned == 0
    assert receipt.adaptive_claim_authorized is False


def test_builds_sprint_plan_for_selected_candidate(tmp_path):
    pack = tmp_path / "pack.json"
    _write_portfolio_pack(pack)

    receipt = run_selected_product_sprint_planning_gauntlet(
        product_portfolio_marketing_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=True,
    )

    assert receipt.status == SELECTED_PRODUCT_SPRINT_PLANNING_GAUNTLET_READY_TOKEN
    assert receipt.selected_product == "DIO_TRUST_DOSSIER_STUDIO"
    assert receipt.sprint_plan_written is True
    assert receipt.work_packages_planned == 5
    assert receipt.acceptance_gates_planned >= 20
    assert receipt.evidence_receipts_planned >= 15
    assert receipt.governed_sprint_plan_mean_score >= receipt.minimum_governed_sprint_score
    assert receipt.governed_sprint_minus_static_effect >= receipt.minimum_sprint_planning_effect
    assert receipt.selected_product_sprint_planning_evidence is True
    assert receipt.allowed_claim_tier == "T13_CANDIDATE_SELECTED_PRODUCT_SPRINT_PLANNING_EVIDENCE"


def test_sprint_plan_preserves_claim_locks(tmp_path):
    pack = tmp_path / "pack.json"
    _write_portfolio_pack(pack)

    receipt = run_selected_product_sprint_planning_gauntlet(
        product_portfolio_marketing_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=True,
    )

    plan = json.loads(Path(receipt.sprint_plan_path).read_text())
    assert plan["claim_locks"]["commercial_validation_claim_authorized"] is False
    assert plan["claim_locks"]["product_market_fit_claim_authorized"] is False
    assert plan["claim_locks"]["autonomous_development_authorized"] is False
    assert plan["claim_locks"]["authority_expansion_authorized"] is False
    assert any("human" in gate for package in plan["work_packages"] for gate in package["acceptance_gates"])


def test_summary_and_receipt_are_written(tmp_path):
    pack = tmp_path / "pack.json"
    _write_portfolio_pack(pack)
    out = tmp_path / "out"

    receipt = run_selected_product_sprint_planning_gauntlet(
        product_portfolio_marketing_pack_path=pack,
        output_dir=out,
        execute=True,
    )

    summary = json.loads(Path(receipt.sprint_summary_path).read_text())
    persisted = json.loads((out / "selected_product_sprint_planning_gauntlet_receipt.json").read_text())
    assert summary["selected_product"] == "DIO_TRUST_DOSSIER_STUDIO"
    assert summary["selected_product_sprint_planning_evidence"] is True
    assert persisted["status"] == SELECTED_PRODUCT_SPRINT_PLANNING_GAUNTLET_READY_TOKEN


def test_cli_runner(tmp_path):
    pack = tmp_path / "pack.json"
    _write_portfolio_pack(pack)
    out = tmp_path / "out"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_selected_product_sprint_planning_gauntlet.py",
            "--product-portfolio-marketing-pack",
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
    assert SELECTED_PRODUCT_SPRINT_PLANNING_GAUNTLET_READY_TOKEN in completed.stdout
    persisted = json.loads((out / "selected_product_sprint_planning_gauntlet_receipt.json").read_text())
    assert persisted["sprint_planning_claim_authorized"] is True


def test_asdict_round_trip_for_receipt(tmp_path):
    pack = tmp_path / "pack.json"
    _write_portfolio_pack(pack)

    receipt = run_selected_product_sprint_planning_gauntlet(
        product_portfolio_marketing_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=True,
    )

    payload = json.loads(json.dumps(asdict(receipt)))
    assert payload["status"] == SELECTED_PRODUCT_SPRINT_PLANNING_GAUNTLET_READY_TOKEN
    assert payload["publication_authorized"] is False
    assert payload["agi_claim_authorized"] is False
