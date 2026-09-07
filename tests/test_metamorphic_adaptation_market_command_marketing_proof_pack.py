from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from experiments.metamorphic_adaptation.market_command_marketing_proof_pack import (
    MARKET_COMMAND_MARKETING_PROOF_PACK_READY_TOKEN,
    build_market_command_marketing_proof_pack,
)


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _write_marketing_pack(path: Path) -> None:
    _write_json(
        path,
        {
            "status": "DIO_METAMORPHIC_ADAPTATION_MARKETING_PROOF_BOUNDARY_PACK_READY",
            "adaptive_claim_authorized": True,
            "bounded_marketing_language_authorized": True,
            "commercial_validation_claim_authorized": False,
            "world_first_claim_authorized": False,
            "agi_claim_authorized": False,
            "authority_expansion_authorized": False,
        },
    )


def _write_pivot(path: Path, *, ready: bool = True) -> None:
    _write_json(
        path,
        {
            "status": (
                "DIO_METAMORPHIC_ADAPTATION_MARKET_COMMAND_SENSORIUM_PIVOT_GAUNTLET_READY"
                if ready
                else "DIO_METAMORPHIC_ADAPTATION_MARKET_COMMAND_SENSORIUM_PIVOT_GAUNTLET_REFUSED"
            ),
            "market_command_adaptive_evidence": ready,
            "market_pivot_claim_authorized": ready,
            "adaptive_claim_authorized": ready,
            "market_pivot_effect_threshold_met": ready,
            "market_signals_processed": 5 if ready else 0,
            "pivots_executed": 5 if ready else 0,
            "market_commands_issued": 5 if ready else 0,
            "static_baseline_mean_score": 0.524,
            "pivoting_sensorium_mean_score": 0.896,
            "pivoting_minus_static_effect": 0.372 if ready else 0.0,
            "minimum_pivot_effect": 0.25,
            "commercial_validation_claim_authorized": False,
            "world_first_claim_authorized": False,
            "agi_claim_authorized": False,
            "autonomous_action_claim_authorized": False,
            "authority_expansion_authorized": False,
        },
    )


def test_pack_authorizes_t7_marketing_language(tmp_path):
    marketing = tmp_path / "marketing.json"
    pivot = tmp_path / "pivot.json"
    out = tmp_path / "out"
    _write_marketing_pack(marketing)
    _write_pivot(pivot)

    receipt = build_market_command_marketing_proof_pack(
        marketing_proof_boundary_pack_path=marketing,
        market_command_pivot_gauntlet_path=pivot,
        output_dir=out,
    )

    assert receipt.status == MARKET_COMMAND_MARKETING_PROOF_PACK_READY_TOKEN
    assert receipt.marketing_claim_tier == "T7_MARKETING_SAFE_MARKET_COMMAND_SENSORIUM_PIVOTING_ADAPTATION"
    assert receipt.market_pivot_marketing_language_authorized is True
    assert receipt.adaptive_claim_authorized is True
    assert receipt.commercial_validation_claim_authorized is False
    assert receipt.world_first_claim_authorized is False
    assert receipt.allowed_public_claims_count >= 6
    assert receipt.forbidden_public_claims_count >= 12
    assert (out / "market_command_marketing_safe_copy.md").exists()
    copy = (out / "market_command_marketing_safe_copy.md").read_text()
    assert "pivoting adaptation" in copy.lower()
    assert "Not commercial validation" in copy


def test_pack_refuses_when_pivot_not_ready(tmp_path):
    marketing = tmp_path / "marketing.json"
    pivot = tmp_path / "pivot.json"
    out = tmp_path / "out"
    _write_marketing_pack(marketing)
    _write_pivot(pivot, ready=False)

    receipt = build_market_command_marketing_proof_pack(
        marketing_proof_boundary_pack_path=marketing,
        market_command_pivot_gauntlet_path=pivot,
        output_dir=out,
    )

    assert receipt.status == "DIO_METAMORPHIC_ADAPTATION_MARKET_COMMAND_MARKETING_PROOF_PACK_REFUSED"
    assert receipt.market_pivot_marketing_language_authorized is False
    assert receipt.adaptive_claim_authorized is False
    assert receipt.marketing_claim_tier == "T0_NO_MARKET_COMMAND_MARKETING_CLAIM"


def test_pack_blocks_overclaims_even_when_ready(tmp_path):
    marketing = tmp_path / "marketing.json"
    pivot = tmp_path / "pivot.json"
    out = tmp_path / "out"
    _write_marketing_pack(marketing)
    _write_pivot(pivot)

    receipt = build_market_command_marketing_proof_pack(
        marketing_proof_boundary_pack_path=marketing,
        market_command_pivot_gauntlet_path=pivot,
        output_dir=out,
    )

    assert receipt.commercial_validation_claim_authorized is False
    assert receipt.professional_approval_claim_authorized is False
    assert receipt.publication_authorized is False
    assert receipt.spend_authorized is False
    assert receipt.fulfilment_authorized is False
    assert receipt.world_first_claim_authorized is False
    assert receipt.agi_claim_authorized is False
    assert receipt.autonomous_action_claim_authorized is False
    assert receipt.authority_expansion_authorized is False


def test_cli_runner(tmp_path):
    marketing = tmp_path / "marketing.json"
    pivot = tmp_path / "pivot.json"
    out = tmp_path / "out"
    _write_marketing_pack(marketing)
    _write_pivot(pivot)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_market_command_marketing_proof_pack.py",
            "--marketing-proof-boundary-pack",
            str(marketing),
            "--market-command-pivot-gauntlet",
            str(pivot),
            "--output",
            str(out),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert MARKET_COMMAND_MARKETING_PROOF_PACK_READY_TOKEN in completed.stdout
