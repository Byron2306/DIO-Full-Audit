from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from experiments.metamorphic_adaptation.atlas_guided_product_composition_gauntlet import (
    ATLAS_PRODUCT_COMPOSITION_GAUNTLET_READY_TOKEN,
    ATLAS_PRODUCT_COMPOSITION_GAUNTLET_REFUSED_TOKEN,
    run_atlas_guided_product_composition_gauntlet,
)


def _write_t9_receipt(path: Path, **overrides) -> None:
    data = {
        "status": "DIO_METAMORPHIC_ADAPTATION_AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_READY",
        "audience_morphology_evidence": True,
        "adaptive_claim_authorized": True,
        "commercial_validation_claim_authorized": False,
        "authority_expansion_authorized": False,
    }
    data.update(overrides)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def test_refuses_without_explicit_execute(tmp_path):
    t9 = tmp_path / "t9.json"
    _write_t9_receipt(t9)

    receipt = run_atlas_guided_product_composition_gauntlet(
        audience_morphology_gauntlet_path=t9,
        output_dir=tmp_path / "out",
        execute=False,
    )

    assert receipt.status == ATLAS_PRODUCT_COMPOSITION_GAUNTLET_REFUSED_TOKEN
    assert receipt.executed is False
    assert receipt.product_composition_claim_authorized is False
    assert receipt.allowed_claim_tier == "T0_NO_ATLAS_PRODUCT_COMPOSITION_CLAIM"


def test_refuses_when_t9_receipt_not_ready(tmp_path):
    t9 = tmp_path / "t9.json"
    _write_t9_receipt(t9, status="NOT_READY")

    receipt = run_atlas_guided_product_composition_gauntlet(
        audience_morphology_gauntlet_path=t9,
        output_dir=tmp_path / "out",
        execute=True,
    )

    assert receipt.status == ATLAS_PRODUCT_COMPOSITION_GAUNTLET_REFUSED_TOKEN
    assert receipt.opportunities_processed == 0
    assert receipt.adaptive_claim_authorized is False


def test_executes_six_domain_product_compositions(tmp_path):
    t9 = tmp_path / "t9.json"
    _write_t9_receipt(t9)

    receipt = run_atlas_guided_product_composition_gauntlet(
        audience_morphology_gauntlet_path=t9,
        output_dir=tmp_path / "out",
        execute=True,
    )

    assert receipt.status == ATLAS_PRODUCT_COMPOSITION_GAUNTLET_READY_TOKEN
    assert receipt.opportunities_processed == 6
    assert receipt.atlas_work_maps_bound == 6
    assert receipt.development_ready_specs_written == 6
    assert receipt.static_products_scored == 6
    assert receipt.adaptive_products_scored == 6
    assert receipt.adaptive_atlas_product_mean_score > receipt.static_product_baseline_mean_score
    assert receipt.adaptive_atlas_minus_static_effect >= receipt.minimum_atlas_product_effect
    assert receipt.adaptive_atlas_product_mean_score >= receipt.minimum_adaptive_atlas_product_score
    assert receipt.atlas_guided_product_composition_evidence is True
    assert receipt.higher_grade_product_composition_evidence is True
    assert receipt.allowed_claim_tier == "T10_CANDIDATE_ATLAS_GUIDED_DOMAIN_PRODUCT_COMPOSITION_EVIDENCE"


def test_specs_bind_topology_and_preserve_locks(tmp_path):
    t9 = tmp_path / "t9.json"
    _write_t9_receipt(t9)
    out = tmp_path / "out"

    receipt = run_atlas_guided_product_composition_gauntlet(
        audience_morphology_gauntlet_path=t9,
        output_dir=out,
        execute=True,
    )

    specs = [json.loads(line) for line in Path(receipt.specs_path).read_text().splitlines()]
    assert len(specs) == 6
    assert all(item["required_terms_present"] is True for item in specs)
    assert all(item["forbidden_terms_absent"] is True for item in specs)
    assert all(item["atlas_work_map_bound"] is True for item in specs)
    assert all(item["adaptive_product_spec"]["target_grade"] == "DEVELOPMENT_READY_DOMAIN_INCARNATION" for item in specs)
    assert all(item["commercial_validation_claim_authorized"] is False for item in specs)
    assert all(item["autonomous_development_authorized"] is False for item in specs)
    assert all(item["authority_expansion_authorized"] is False for item in specs)


def test_summary_registry_and_receipt_are_written(tmp_path):
    t9 = tmp_path / "t9.json"
    _write_t9_receipt(t9)
    out = tmp_path / "out"

    receipt = run_atlas_guided_product_composition_gauntlet(
        audience_morphology_gauntlet_path=t9,
        output_dir=out,
        execute=True,
    )

    summary = json.loads(Path(receipt.summary_path).read_text())
    registry = json.loads(Path(receipt.registry_path).read_text())
    persisted = json.loads((out / "atlas_guided_product_composition_gauntlet_receipt.json").read_text())
    assert summary["atlas_guided_product_composition_evidence"] is True
    assert len(registry["opportunities"]) == 6
    assert persisted["status"] == ATLAS_PRODUCT_COMPOSITION_GAUNTLET_READY_TOKEN
    assert persisted["audience_morphology_gauntlet_sha256"] == receipt.audience_morphology_gauntlet_sha256


def test_cli_runner(tmp_path):
    t9 = tmp_path / "t9.json"
    _write_t9_receipt(t9)
    out = tmp_path / "out"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_atlas_guided_product_composition_gauntlet.py",
            "--audience-morphology-gauntlet",
            str(t9),
            "--output",
            str(out),
            "--execute",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert ATLAS_PRODUCT_COMPOSITION_GAUNTLET_READY_TOKEN in completed.stdout
    persisted = json.loads((out / "atlas_guided_product_composition_gauntlet_receipt.json").read_text())
    assert persisted["adaptive_claim_authorized"] is True


def test_asdict_round_trip_preserves_overclaim_locks(tmp_path):
    t9 = tmp_path / "t9.json"
    _write_t9_receipt(t9)

    receipt = run_atlas_guided_product_composition_gauntlet(
        audience_morphology_gauntlet_path=t9,
        output_dir=tmp_path / "out",
        execute=True,
    )

    payload = json.loads(json.dumps(asdict(receipt)))
    assert payload["status"] == ATLAS_PRODUCT_COMPOSITION_GAUNTLET_READY_TOKEN
    assert payload["publication_authorized"] is False
    assert payload["spend_authorized"] is False
    assert payload["autonomous_development_authorized"] is False
    assert payload["agi_claim_authorized"] is False
    assert payload["authority_expansion_authorized"] is False
