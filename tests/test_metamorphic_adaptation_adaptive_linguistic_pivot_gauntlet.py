from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from experiments.metamorphic_adaptation.adaptive_linguistic_pivot_gauntlet import (
    ADAPTIVE_LINGUISTIC_PIVOT_GAUNTLET_READY_TOKEN,
    ADAPTIVE_LINGUISTIC_PIVOT_GAUNTLET_REFUSED_TOKEN,
    run_adaptive_linguistic_pivot_gauntlet,
)


def _write_market_command_pack(path: Path, **overrides) -> None:
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


def test_refuses_without_explicit_execute(tmp_path):
    pack = tmp_path / "pack.json"
    _write_market_command_pack(pack)

    receipt = run_adaptive_linguistic_pivot_gauntlet(
        market_command_marketing_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=False,
    )

    assert receipt.status == ADAPTIVE_LINGUISTIC_PIVOT_GAUNTLET_REFUSED_TOKEN
    assert receipt.executed is False
    assert receipt.adaptive_claim_authorized is False
    assert receipt.allowed_claim_tier == "T0_NO_LINGUISTIC_PIVOT_CLAIM"


def test_refuses_when_t7_marketing_pack_not_ready(tmp_path):
    pack = tmp_path / "pack.json"
    _write_market_command_pack(pack, status="NOT_READY")

    receipt = run_adaptive_linguistic_pivot_gauntlet(
        market_command_marketing_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=True,
    )

    assert receipt.status == ADAPTIVE_LINGUISTIC_PIVOT_GAUNTLET_REFUSED_TOKEN
    assert receipt.audience_shifts_processed == 0
    assert receipt.linguistic_pivot_claim_authorized is False


def test_executes_five_audience_shift_pivots(tmp_path):
    pack = tmp_path / "pack.json"
    _write_market_command_pack(pack)

    receipt = run_adaptive_linguistic_pivot_gauntlet(
        market_command_marketing_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=True,
    )

    assert receipt.status == ADAPTIVE_LINGUISTIC_PIVOT_GAUNTLET_READY_TOKEN
    assert receipt.audience_shifts_processed == 5
    assert receipt.linguistic_pivots_executed == 5
    assert receipt.static_copy_variants_scored == 5
    assert receipt.adaptive_copy_variants_scored == 5
    assert receipt.adaptive_linguistic_pivot_mean_score > receipt.static_linguistic_baseline_mean_score
    assert receipt.adaptive_linguistic_minus_static_effect >= receipt.minimum_linguistic_pivot_effect
    assert receipt.adaptive_linguistic_pivot_mean_score >= receipt.minimum_adaptive_linguistic_score
    assert receipt.adaptive_linguistic_evidence is True
    assert receipt.adaptive_claim_authorized is True
    assert receipt.allowed_claim_tier == "T8_CANDIDATE_ADAPTIVE_LINGUISTIC_MARKET_RECOMPOSITION_EVIDENCE"


def test_outputs_preserve_forbidden_claim_locks(tmp_path):
    pack = tmp_path / "pack.json"
    _write_market_command_pack(pack)
    out = tmp_path / "out"

    receipt = run_adaptive_linguistic_pivot_gauntlet(
        market_command_marketing_pack_path=pack,
        output_dir=out,
        execute=True,
    )

    outputs = [json.loads(line) for line in Path(receipt.outputs_path).read_text().splitlines()]
    assert len(outputs) == 5
    assert all(item["required_terms_present_in_adaptive"] is True for item in outputs)
    assert all(item["forbidden_terms_absent_from_adaptive"] is True for item in outputs)
    assert all(item["commercial_validation_claim_authorized"] is False for item in outputs)
    assert all(item["world_first_claim_authorized"] is False for item in outputs)
    assert all(item["authority_expansion_authorized"] is False for item in outputs)


def test_summary_and_receipt_are_written(tmp_path):
    pack = tmp_path / "pack.json"
    _write_market_command_pack(pack)
    out = tmp_path / "out"

    receipt = run_adaptive_linguistic_pivot_gauntlet(
        market_command_marketing_pack_path=pack,
        output_dir=out,
        execute=True,
    )

    summary = json.loads(Path(receipt.summary_path).read_text())
    persisted = json.loads((out / "adaptive_linguistic_pivot_gauntlet_receipt.json").read_text())
    assert summary["adaptive_linguistic_evidence"] is True
    assert persisted["status"] == ADAPTIVE_LINGUISTIC_PIVOT_GAUNTLET_READY_TOKEN
    assert persisted["market_command_marketing_pack_sha256"] == receipt.market_command_marketing_pack_sha256


def test_cli_runner(tmp_path):
    pack = tmp_path / "pack.json"
    _write_market_command_pack(pack)
    out = tmp_path / "out"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_adaptive_linguistic_pivot_gauntlet.py",
            "--market-command-marketing-pack",
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
    assert ADAPTIVE_LINGUISTIC_PIVOT_GAUNTLET_READY_TOKEN in completed.stdout
    persisted = json.loads((out / "adaptive_linguistic_pivot_gauntlet_receipt.json").read_text())
    assert persisted["adaptive_claim_authorized"] is True


def test_asdict_round_trip_for_receipt(tmp_path):
    pack = tmp_path / "pack.json"
    _write_market_command_pack(pack)

    receipt = run_adaptive_linguistic_pivot_gauntlet(
        market_command_marketing_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=True,
    )

    payload = json.loads(json.dumps(asdict(receipt)))
    assert payload["status"] == ADAPTIVE_LINGUISTIC_PIVOT_GAUNTLET_READY_TOKEN
    assert payload["publication_authorized"] is False
    assert payload["agi_claim_authorized"] is False
