from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from experiments.metamorphic_adaptation.adaptive_linguistic_marketing_proof_pack import (
    ADAPTIVE_LINGUISTIC_MARKETING_PROOF_PACK_READY_TOKEN,
    ADAPTIVE_LINGUISTIC_MARKETING_PROOF_PACK_REFUSED_TOKEN,
    build_adaptive_linguistic_marketing_proof_pack,
)


def _write_market_pack(path: Path, **overrides) -> None:
    data = {
        "status": "DIO_METAMORPHIC_ADAPTATION_MARKET_COMMAND_MARKETING_PROOF_PACK_READY",
        "market_pivot_marketing_language_authorized": True,
        "adaptive_claim_authorized": True,
        "commercial_validation_claim_authorized": False,
        "world_first_claim_authorized": False,
        "agi_claim_authorized": False,
        "authority_expansion_authorized": False,
    }
    data.update(overrides)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _write_linguistic_gauntlet(path: Path, **overrides) -> None:
    data = {
        "status": "DIO_METAMORPHIC_ADAPTATION_ADAPTIVE_LINGUISTIC_PIVOT_GAUNTLET_READY",
        "adaptive_linguistic_evidence": True,
        "linguistic_pivot_claim_authorized": True,
        "adaptive_claim_authorized": True,
        "audience_shifts_processed": 5,
        "linguistic_pivots_executed": 5,
        "static_linguistic_baseline_mean_score": 0.3425,
        "adaptive_linguistic_pivot_mean_score": 0.93,
        "adaptive_linguistic_minus_static_effect": 0.5875,
        "minimum_linguistic_pivot_effect": 0.3,
        "minimum_adaptive_linguistic_score": 0.82,
        "commercial_validation_claim_authorized": False,
        "world_first_claim_authorized": False,
        "agi_claim_authorized": False,
        "authority_expansion_authorized": False,
    }
    data.update(overrides)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def test_builds_t8_marketing_safe_pack(tmp_path):
    market = tmp_path / "market.json"
    linguistic = tmp_path / "linguistic.json"
    _write_market_pack(market)
    _write_linguistic_gauntlet(linguistic)

    receipt = build_adaptive_linguistic_marketing_proof_pack(
        market_command_marketing_pack_path=market,
        adaptive_linguistic_gauntlet_path=linguistic,
        output_dir=tmp_path / "out",
    )

    assert receipt.status == ADAPTIVE_LINGUISTIC_MARKETING_PROOF_PACK_READY_TOKEN
    assert receipt.marketing_claim_tier == "T8_MARKETING_SAFE_ADAPTIVE_LINGUISTIC_MARKET_RECOMPOSITION"
    assert receipt.linguistic_marketing_language_authorized is True
    assert receipt.adaptive_claim_authorized is True
    assert receipt.audience_shifts_processed == 5
    assert receipt.adaptive_linguistic_minus_static_effect == 0.5875
    assert receipt.allowed_public_claims_count == 7
    assert receipt.forbidden_public_claims_count == 12


def test_refuses_if_market_pack_not_ready(tmp_path):
    market = tmp_path / "market.json"
    linguistic = tmp_path / "linguistic.json"
    _write_market_pack(market, status="NOT_READY")
    _write_linguistic_gauntlet(linguistic)

    receipt = build_adaptive_linguistic_marketing_proof_pack(
        market_command_marketing_pack_path=market,
        adaptive_linguistic_gauntlet_path=linguistic,
        output_dir=tmp_path / "out",
    )

    assert receipt.status == ADAPTIVE_LINGUISTIC_MARKETING_PROOF_PACK_REFUSED_TOKEN
    assert receipt.linguistic_marketing_language_authorized is False
    assert receipt.adaptive_claim_authorized is False
    assert receipt.marketing_claim_tier == "T0_NO_ADAPTIVE_LINGUISTIC_MARKETING_CLAIM"


def test_refuses_if_linguistic_thresholds_not_met(tmp_path):
    market = tmp_path / "market.json"
    linguistic = tmp_path / "linguistic.json"
    _write_market_pack(market)
    _write_linguistic_gauntlet(linguistic, adaptive_linguistic_minus_static_effect=0.01)

    receipt = build_adaptive_linguistic_marketing_proof_pack(
        market_command_marketing_pack_path=market,
        adaptive_linguistic_gauntlet_path=linguistic,
        output_dir=tmp_path / "out",
    )

    assert receipt.status == ADAPTIVE_LINGUISTIC_MARKETING_PROOF_PACK_REFUSED_TOKEN
    assert receipt.allowed_public_claims_count == 0


def test_writes_claims_and_copy_with_locks(tmp_path):
    market = tmp_path / "market.json"
    linguistic = tmp_path / "linguistic.json"
    _write_market_pack(market)
    _write_linguistic_gauntlet(linguistic)
    out = tmp_path / "out"

    receipt = build_adaptive_linguistic_marketing_proof_pack(
        market_command_marketing_pack_path=market,
        adaptive_linguistic_gauntlet_path=linguistic,
        output_dir=out,
    )

    claims = json.loads(Path(receipt.linguistic_claims_path).read_text())
    copy = Path(receipt.linguistic_copy_path).read_text()
    assert claims["claim_locks"]["commercial_validation_claim_authorized"] is False
    assert claims["claim_locks"]["authority_expansion_authorized"] is False
    assert "adaptive linguistic market recomposition" in copy
    assert "Not AGI" in copy
    assert "not external demand proof" in copy


def test_cli_runner(tmp_path):
    market = tmp_path / "market.json"
    linguistic = tmp_path / "linguistic.json"
    _write_market_pack(market)
    _write_linguistic_gauntlet(linguistic)
    out = tmp_path / "out"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_adaptive_linguistic_marketing_proof_pack.py",
            "--market-command-marketing-pack",
            str(market),
            "--adaptive-linguistic-gauntlet",
            str(linguistic),
            "--output",
            str(out),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert ADAPTIVE_LINGUISTIC_MARKETING_PROOF_PACK_READY_TOKEN in completed.stdout
    persisted = json.loads((out / "adaptive_linguistic_marketing_proof_pack_receipt.json").read_text())
    assert persisted["adaptive_claim_authorized"] is True


def test_asdict_round_trip_for_receipt(tmp_path):
    market = tmp_path / "market.json"
    linguistic = tmp_path / "linguistic.json"
    _write_market_pack(market)
    _write_linguistic_gauntlet(linguistic)

    receipt = build_adaptive_linguistic_marketing_proof_pack(
        market_command_marketing_pack_path=market,
        adaptive_linguistic_gauntlet_path=linguistic,
        output_dir=tmp_path / "out",
    )

    payload = json.loads(json.dumps(asdict(receipt)))
    assert payload["status"] == ADAPTIVE_LINGUISTIC_MARKETING_PROOF_PACK_READY_TOKEN
    assert payload["publication_authorized"] is False
    assert payload["autonomous_action_claim_authorized"] is False
