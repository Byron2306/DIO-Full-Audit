from __future__ import annotations

import json
from pathlib import Path

from products.reference_gauntlet import ACCEPTANCE_TOKEN, REGISTRY_PATH, run_gauntlet


ROOT = Path(__file__).resolve().parents[1]


def test_reference_registry_names_exactly_four_canonical_incarnations() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    assert [row["product_id"] for row in registry["incarnations"]] == ["dio_contractproof", "dio_tenderproof", "dio_grantproof", "dio_permitproof"]
    assert {row["source_type"] for row in registry["incarnations"]} == {"contract", "tender", "grant", "permit"}
    assert len(registry["shared_core_guard"]) == 8


def test_full_reference_incarnation_gauntlet(tmp_path: Path) -> None:
    receipt = run_gauntlet(output_dir=tmp_path / "gauntlet")
    assert receipt["acceptance_token"] == ACCEPTANCE_TOKEN
    assert receipt["incarnation_count"] == 4
    assert receipt["provider_isolation"] == "PASS"
    assert receipt["source_type_isolation"] == "PASS"
    assert receipt["shared_core_integrity"] == "PASS"
    assert receipt["deterministic_compilation"] == "PASS"
    assert receipt["deterministic_execution"] == "PASS"
    assert receipt["authority_boundary"] == "PASS"
    assert receipt["external_release"] == "REFUSE"
    assert receipt["maturity_ceiling"] == "internal_proof"
    assert len({row["composition_fingerprint"] for row in receipt["incarnations"]}) == 4
    assert all(row["reproducible"] is True for row in receipt["incarnations"])
    assert all(row["mixed_truth_preserved"] is True for row in receipt["incarnations"])
    assert (tmp_path / "gauntlet" / "REFERENCE_INCARNATION_GAUNTLET_RECEIPT.json").is_file()


def test_gauntlet_is_observer_not_a_new_product_or_executor() -> None:
    source = (ROOT / "products" / "reference_gauntlet.py").read_text(encoding="utf-8")
    assert "run_contractproof" in source
    assert "run_family_proof" in source
    assert "authority_created" in source
    assert "external_effects" in source
    assert not (ROOT / "config" / "products" / "manifests" / "reference_gauntlet.json").exists()
