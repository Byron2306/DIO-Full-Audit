from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from experiments.metamorphic_adaptation.market_command_sensorium_pivot_gauntlet import (
    MARKET_COMMAND_SENSORIUM_PIVOT_GAUNTLET_READY_TOKEN,
    MARKET_COMMAND_SENSORIUM_PIVOT_GAUNTLET_REFUSED_TOKEN,
    run_market_command_sensorium_pivot_gauntlet,
)


def _write_marketing_pack(path: Path, ready: bool = True) -> None:
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_MARKETING_PROOF_BOUNDARY_PACK_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_MARKETING_PROOF_BOUNDARY_PACK_REFUSED"
        ),
        "marketing_claim_tier": (
            "T6_MARKETING_SAFE_CANDIDATE_RETAINED_ECOSYSTEM_ADAPTATION"
            if ready
            else "T0_NO_MARKETING_PROOF_CLAIM"
        ),
        "bounded_marketing_language_authorized": ready,
        "adaptive_claim_authorized": ready,
        "commercial_validation_claim_authorized": False,
        "professional_approval_claim_authorized": False,
        "publication_authorized": False,
        "spend_authorized": False,
        "fulfilment_authorized": False,
        "world_first_claim_authorized": False,
        "agi_claim_authorized": False,
        "autonomous_action_claim_authorized": False,
        "authority_expansion_authorized": False,
    }))


def test_market_command_sensorium_pivot_gauntlet_requires_explicit_execute(tmp_path):
    pack = tmp_path / "pack.json"
    _write_marketing_pack(pack)

    receipt = run_market_command_sensorium_pivot_gauntlet(
        marketing_proof_boundary_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=False,
    )

    assert receipt.status == MARKET_COMMAND_SENSORIUM_PIVOT_GAUNTLET_REFUSED_TOKEN
    assert receipt.executed is False
    assert receipt.pivots_executed == 0
    assert receipt.market_pivot_claim_authorized is False
    assert receipt.commercial_validation_claim_authorized is False


def test_market_command_sensorium_pivot_gauntlet_refuses_unready_marketing_pack(tmp_path):
    pack = tmp_path / "pack.json"
    _write_marketing_pack(pack, ready=False)

    receipt = run_market_command_sensorium_pivot_gauntlet(
        marketing_proof_boundary_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=True,
    )

    assert receipt.status == MARKET_COMMAND_SENSORIUM_PIVOT_GAUNTLET_REFUSED_TOKEN
    assert receipt.marketing_pack_status == "DIO_METAMORPHIC_ADAPTATION_MARKETING_PROOF_BOUNDARY_PACK_REFUSED"
    assert receipt.market_command_adaptive_evidence is False
    assert receipt.adaptive_claim_authorized is False


def test_market_command_sensorium_pivot_gauntlet_detects_signal_driven_pivots(tmp_path):
    pack = tmp_path / "pack.json"
    _write_marketing_pack(pack)

    receipt = run_market_command_sensorium_pivot_gauntlet(
        marketing_proof_boundary_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=True,
    )

    assert receipt.status == MARKET_COMMAND_SENSORIUM_PIVOT_GAUNTLET_READY_TOKEN
    assert receipt.executed is True
    assert receipt.pivots_executed == 5
    assert receipt.market_signals_processed == 5
    assert receipt.market_commands_issued == 5
    assert receipt.static_baseline_mean_score < receipt.pivoting_sensorium_mean_score
    assert receipt.pivoting_minus_static_effect >= receipt.minimum_pivot_effect
    assert receipt.market_command_adaptive_evidence is True
    assert receipt.market_pivot_claim_authorized is True
    assert receipt.allowed_claim_tier == "T7_CANDIDATE_MARKET_COMMAND_SENSORIUM_PIVOTING_ADAPTATION_EVIDENCE"


def test_market_command_sensorium_pivot_outputs_preserve_boundaries(tmp_path):
    pack = tmp_path / "pack.json"
    _write_marketing_pack(pack)
    output_dir = tmp_path / "out"

    receipt = run_market_command_sensorium_pivot_gauntlet(
        marketing_proof_boundary_pack_path=pack,
        output_dir=output_dir,
        execute=True,
    )

    outputs = [json.loads(line) for line in Path(receipt.pivot_outputs_path).read_text().splitlines()]
    assert len(outputs) == 5
    assert all(item["status"] == "MARKET_COMMAND_SENSORIUM_PIVOT_RECORDED" for item in outputs)
    assert all(item["market_signal_bound"] is True for item in outputs)
    assert all(item["wrong_route_abandoned"] is True for item in outputs)
    assert all(item["authority_expansion_authorized"] is False for item in outputs)
    assert all(item["commercial_validation_claim_authorized"] is False for item in outputs)
    assert all("pivot_command" in item for item in outputs)


def test_market_command_sensorium_pivot_writes_summary_and_receipt(tmp_path):
    pack = tmp_path / "pack.json"
    _write_marketing_pack(pack)
    output_dir = tmp_path / "out"

    receipt = run_market_command_sensorium_pivot_gauntlet(
        marketing_proof_boundary_pack_path=pack,
        output_dir=output_dir,
        execute=True,
    )

    summary = json.loads(Path(receipt.pivot_summary_path).read_text())
    written_receipt = json.loads((output_dir / "market_command_sensorium_pivot_gauntlet_receipt.json").read_text())
    assert summary["pivoting_minus_static_effect"] == receipt.pivoting_minus_static_effect
    assert written_receipt["status"] == MARKET_COMMAND_SENSORIUM_PIVOT_GAUNTLET_READY_TOKEN
    assert written_receipt["marketing_proof_boundary_pack_sha256"]


def test_market_command_sensorium_pivot_cli_runner(tmp_path):
    pack = tmp_path / "pack.json"
    _write_marketing_pack(pack)
    output_dir = tmp_path / "out"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_market_command_sensorium_pivot_gauntlet.py",
            "--marketing-proof-boundary-pack",
            str(pack),
            "--output",
            str(output_dir),
            "--execute",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert MARKET_COMMAND_SENSORIUM_PIVOT_GAUNTLET_READY_TOKEN in completed.stdout


def test_market_command_sensorium_pivot_forbidden_claims_remain_locked(tmp_path):
    pack = tmp_path / "pack.json"
    _write_marketing_pack(pack)

    receipt = run_market_command_sensorium_pivot_gauntlet(
        marketing_proof_boundary_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=True,
    )

    assert receipt.commercial_validation_claim_authorized is False
    assert receipt.world_first_claim_authorized is False
    assert receipt.agi_claim_authorized is False
    assert receipt.autonomous_action_claim_authorized is False
    assert receipt.authority_expansion_authorized is False
    assert "never authorizes commercial validation" in receipt.boundary
