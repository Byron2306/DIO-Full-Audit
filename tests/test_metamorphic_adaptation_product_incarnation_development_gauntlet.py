from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from experiments.metamorphic_adaptation.product_incarnation_development_gauntlet import (
    PRODUCT_INCARNATION_DEVELOPMENT_GAUNTLET_READY_TOKEN,
    PRODUCT_INCARNATION_DEVELOPMENT_GAUNTLET_REFUSED_TOKEN,
    run_product_incarnation_development_gauntlet,
)


def _write_atlas_product_marketing_pack(path: Path, **overrides) -> None:
    data = {
        "status": "DIO_METAMORPHIC_ADAPTATION_ATLAS_PRODUCT_MARKETING_PROOF_PACK_READY",
        "product_evolution_marketing_language_authorized": True,
        "product_composition_claim_authorized": True,
        "adaptive_claim_authorized": True,
        "autonomous_development_authorized": False,
        "commercial_validation_claim_authorized": False,
        "product_market_fit_claim_authorized": False,
        "authority_expansion_authorized": False,
    }
    data.update(overrides)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def test_refuses_without_explicit_execute(tmp_path):
    pack = tmp_path / "pack.json"
    _write_atlas_product_marketing_pack(pack)

    receipt = run_product_incarnation_development_gauntlet(
        atlas_product_marketing_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=False,
    )

    assert receipt.status == PRODUCT_INCARNATION_DEVELOPMENT_GAUNTLET_REFUSED_TOKEN
    assert receipt.executed is False
    assert receipt.product_incarnation_development_evidence is False
    assert receipt.allowed_claim_tier == "T0_NO_PRODUCT_INCARNATION_DEVELOPMENT_CLAIM"


def test_refuses_when_t10_marketing_pack_not_ready(tmp_path):
    pack = tmp_path / "pack.json"
    _write_atlas_product_marketing_pack(pack, status="NOT_READY")

    receipt = run_product_incarnation_development_gauntlet(
        atlas_product_marketing_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=True,
    )

    assert receipt.status == PRODUCT_INCARNATION_DEVELOPMENT_GAUNTLET_REFUSED_TOKEN
    assert receipt.candidate_products_loaded == 0
    assert receipt.starter_implementation_claim_authorized is False


def test_writes_six_governed_product_incarnations(tmp_path):
    pack = tmp_path / "pack.json"
    _write_atlas_product_marketing_pack(pack)
    out = tmp_path / "out"

    receipt = run_product_incarnation_development_gauntlet(
        atlas_product_marketing_pack_path=pack,
        output_dir=out,
        execute=True,
    )

    assert receipt.status == PRODUCT_INCARNATION_DEVELOPMENT_GAUNTLET_READY_TOKEN
    assert receipt.candidate_products_loaded == 6
    assert receipt.starter_incarnations_written == 6
    assert receipt.manifests_written == 6
    assert receipt.evidence_contracts_written == 6
    assert receipt.acceptance_test_plans_written == 6
    assert receipt.readmes_written == 6
    assert receipt.governed_incarnation_mean_score >= receipt.minimum_governed_incarnation_score
    assert receipt.governed_incarnation_minus_static_effect >= receipt.minimum_incarnation_development_effect
    assert receipt.product_incarnation_development_evidence is True
    assert receipt.starter_implementation_claim_authorized is True
    assert receipt.allowed_claim_tier == "T11_CANDIDATE_GOVERNED_PRODUCT_INCARNATION_DEVELOPMENT_EVIDENCE"


def test_incarnation_files_preserve_authority_locks(tmp_path):
    pack = tmp_path / "pack.json"
    _write_atlas_product_marketing_pack(pack)

    receipt = run_product_incarnation_development_gauntlet(
        atlas_product_marketing_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=True,
    )

    index = json.loads(Path(receipt.incarnation_index_path).read_text())
    assert len(index["incarnations"]) == 6
    for item in index["incarnations"]:
        manifest = json.loads(Path(item["manifest_path"]).read_text())
        evidence = json.loads(Path(item["evidence_contract_path"]).read_text())
        acceptance = json.loads(Path(item["acceptance_test_plan_path"]).read_text())
        readme = Path(item["readme_path"]).read_text()
        assert manifest["authority_mode"] == "HUMAN_GATED"
        assert manifest["external_release"] == "NEEDS_YOU"
        assert evidence["authority_locks"]["autonomous_development_authorized"] is False
        assert evidence["authority_locks"]["authority_expansion_authorized"] is False
        assert acceptance["release_gate"] == "NEEDS_YOU"
        assert "does not prove product-market fit" in readme


def test_summary_and_receipt_are_written(tmp_path):
    pack = tmp_path / "pack.json"
    _write_atlas_product_marketing_pack(pack)
    out = tmp_path / "out"

    receipt = run_product_incarnation_development_gauntlet(
        atlas_product_marketing_pack_path=pack,
        output_dir=out,
        execute=True,
    )

    summary = json.loads(Path(receipt.incarnation_summary_path).read_text())
    persisted = json.loads((out / "product_incarnation_development_gauntlet_receipt.json").read_text())
    assert summary["product_incarnation_development_evidence"] is True
    assert persisted["status"] == PRODUCT_INCARNATION_DEVELOPMENT_GAUNTLET_READY_TOKEN
    assert persisted["atlas_product_marketing_pack_sha256"] == receipt.atlas_product_marketing_pack_sha256
    assert persisted["autonomous_development_authorized"] is False
    assert persisted["product_market_fit_claim_authorized"] is False


def test_cli_runner(tmp_path):
    pack = tmp_path / "pack.json"
    _write_atlas_product_marketing_pack(pack)
    out = tmp_path / "out"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_product_incarnation_development_gauntlet.py",
            "--atlas-product-marketing-pack",
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
    assert PRODUCT_INCARNATION_DEVELOPMENT_GAUNTLET_READY_TOKEN in completed.stdout
    persisted = json.loads((out / "product_incarnation_development_gauntlet_receipt.json").read_text())
    assert persisted["starter_implementation_claim_authorized"] is True


def test_asdict_round_trip_for_receipt(tmp_path):
    pack = tmp_path / "pack.json"
    _write_atlas_product_marketing_pack(pack)

    receipt = run_product_incarnation_development_gauntlet(
        atlas_product_marketing_pack_path=pack,
        output_dir=tmp_path / "out",
        execute=True,
    )

    payload = json.loads(json.dumps(asdict(receipt)))
    assert payload["status"] == PRODUCT_INCARNATION_DEVELOPMENT_GAUNTLET_READY_TOKEN
    assert payload["agi_claim_authorized"] is False
    assert payload["authority_expansion_authorized"] is False
