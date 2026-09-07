from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from experiments.metamorphic_adaptation.audience_morphology_recomposition_gauntlet import (
    AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_READY_TOKEN,
    AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_REFUSED_TOKEN,
    run_audience_morphology_recomposition_gauntlet,
)


def _write_t8_marketing_pack(path: Path, **overrides) -> None:
    data = {
        "status": "DIO_METAMORPHIC_ADAPTATION_ADAPTIVE_LINGUISTIC_MARKETING_PROOF_PACK_READY",
        "linguistic_marketing_language_authorized": True,
        "adaptive_claim_authorized": True,
        "commercial_validation_claim_authorized": False,
        "world_first_claim_authorized": False,
        "agi_claim_authorized": False,
        "autonomous_action_claim_authorized": False,
        "authority_expansion_authorized": False,
    }
    data.update(overrides)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def test_refuses_without_explicit_execute(tmp_path):
    pack = tmp_path / "pack.json"
    _write_t8_marketing_pack(pack)

    receipt = run_audience_morphology_recomposition_gauntlet(
        adaptive_linguistic_marketing_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=False,
    )

    assert receipt.status == AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_REFUSED_TOKEN
    assert receipt.executed is False
    assert receipt.morphologies_bound == 0
    assert receipt.adaptive_claim_authorized is False
    assert receipt.allowed_claim_tier == "T0_NO_AUDIENCE_MORPHOLOGY_RECOMPOSITION_CLAIM"


def test_refuses_when_t8_marketing_pack_not_ready(tmp_path):
    pack = tmp_path / "pack.json"
    _write_t8_marketing_pack(pack, status="NOT_READY")

    receipt = run_audience_morphology_recomposition_gauntlet(
        adaptive_linguistic_marketing_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=True,
    )

    assert receipt.status == AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_REFUSED_TOKEN
    assert receipt.morphology_recomposition_claim_authorized is False
    assert receipt.audience_morphology_evidence is False


def test_executes_eight_audience_morphologies(tmp_path):
    pack = tmp_path / "pack.json"
    _write_t8_marketing_pack(pack)

    receipt = run_audience_morphology_recomposition_gauntlet(
        adaptive_linguistic_marketing_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=True,
    )

    assert receipt.status == AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_READY_TOKEN
    assert receipt.morphologies_bound == 8
    assert receipt.recomposition_outputs_written == 8
    assert receipt.static_morphology_baseline_mean_score < receipt.adaptive_morphology_recomposition_mean_score
    assert receipt.adaptive_morphology_minus_static_effect >= receipt.minimum_morphology_recomposition_effect
    assert receipt.adaptive_morphology_recomposition_mean_score >= receipt.minimum_adaptive_morphology_score
    assert receipt.audience_morphology_evidence is True
    assert receipt.adaptive_claim_authorized is True
    assert receipt.allowed_claim_tier == "T9_CANDIDATE_AUDIENCE_MORPHOLOGY_SEMANTIC_RECOMPOSITION_EVIDENCE"


def test_outputs_bind_morphology_dimensions_and_lock_claims(tmp_path):
    pack = tmp_path / "pack.json"
    _write_t8_marketing_pack(pack)
    out = tmp_path / "out"

    receipt = run_audience_morphology_recomposition_gauntlet(
        adaptive_linguistic_marketing_pack_path=pack,
        output_dir=out,
        execute=True,
    )

    outputs = [json.loads(line) for line in Path(receipt.outputs_path).read_text().splitlines()]
    assert len(outputs) == 8
    assert all(item["morphology_dimensions_bound"] is True for item in outputs)
    assert all(item["required_terms_present_in_recomposition"] is True for item in outputs)
    assert all(item["forbidden_terms_absent_from_recomposition"] is True for item in outputs)
    assert all(item["commercial_validation_claim_authorized"] is False for item in outputs)
    assert all(item["world_first_claim_authorized"] is False for item in outputs)
    assert all(item["authority_expansion_authorized"] is False for item in outputs)


def test_registry_summary_and_receipt_are_written(tmp_path):
    pack = tmp_path / "pack.json"
    _write_t8_marketing_pack(pack)
    out = tmp_path / "out"

    receipt = run_audience_morphology_recomposition_gauntlet(
        adaptive_linguistic_marketing_pack_path=pack,
        output_dir=out,
        execute=True,
    )

    registry = json.loads(Path(receipt.registry_path).read_text())
    summary = json.loads(Path(receipt.summary_path).read_text())
    persisted = json.loads((out / "audience_morphology_recomposition_gauntlet_receipt.json").read_text())
    assert len(registry["audience_morphologies"]) == 8
    assert summary["audience_morphology_evidence"] is True
    assert persisted["status"] == AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_READY_TOKEN
    assert persisted["adaptive_linguistic_marketing_pack_sha256"] == receipt.adaptive_linguistic_marketing_pack_sha256


def test_cli_runner(tmp_path):
    pack = tmp_path / "pack.json"
    _write_t8_marketing_pack(pack)
    out = tmp_path / "out"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_audience_morphology_recomposition_gauntlet.py",
            "--adaptive-linguistic-marketing-pack",
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
    assert AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_READY_TOKEN in completed.stdout
    persisted = json.loads((out / "audience_morphology_recomposition_gauntlet_receipt.json").read_text())
    assert persisted["morphology_recomposition_claim_authorized"] is True


def test_asdict_round_trip_for_receipt(tmp_path):
    pack = tmp_path / "pack.json"
    _write_t8_marketing_pack(pack)

    receipt = run_audience_morphology_recomposition_gauntlet(
        adaptive_linguistic_marketing_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=True,
    )

    payload = json.loads(json.dumps(asdict(receipt)))
    assert payload["status"] == AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_READY_TOKEN
    assert payload["agi_claim_authorized"] is False
    assert payload["manipulation_claim_authorized"] is False
