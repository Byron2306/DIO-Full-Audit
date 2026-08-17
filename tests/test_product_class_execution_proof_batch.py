from __future__ import annotations

import json
from pathlib import Path

import pytest

from products.high_risk_execution_proof import high_risk_profiles_by_product
from scripts.run_product_class_execution_proof_batch import registered_products, run_batch


NOW = "2026-08-17T21:00:00+00:00"
OPERATOR = "human.product_class_batch_test"


def test_batch_runner_proves_all_currently_attached_products(tmp_path: Path) -> None:
    products = registered_products()
    assert len(products) == 36
    for product_id in (
        "dio_contractproof",
        "dio_regops",
        "dio_accreditation",
        "dio_agentauthority",
        "dio_dossierops",
        "dio_homs_moderate",
        "dio_homs_curriculum",
        "dio_sophia_integrity",
        "dio_sophia_research",
        "dio_sophia_supervisor",
        "dio_sophia_tutor",
    ):
        assert product_id in products
    assert set(high_risk_profiles_by_product()).issubset(set(products))
    assert len(high_risk_profiles_by_product()) == 9

    output = tmp_path / "proof-bundle"
    receipt = run_batch(output_root=output, operator_id=OPERATOR, now=NOW)
    assert receipt["schema"] == "dio.product_class.execution_proof_batch.v1"
    assert receipt["registered_proof_adapters"] == 36
    assert receipt["controlled_routes_proved"] == 36
    assert receipt["all_controlled_routes_proved"] is True
    assert receipt["public_launch_ready_products"] == []
    assert len(receipt["products"]) == 36
    assert all(row["execution_proof_state"] == "CONTROLLED_ROUTE_PROVED" for row in receipt["products"])
    assert all(row["human_review_gate"] == "NEEDS_YOU" for row in receipt["products"])
    assert all(row["external_release_gate"] == "REFUSE" for row in receipt["products"])
    assert all(row["public_launch_ready"] is False for row in receipt["products"])

    by_id = {row["product_id"]: row for row in receipt["products"]}
    assert by_id["dio_contractproof"]["adapter_family"] == "vesper_contractproof_attachment_journey"
    assert by_id["dio_regops"]["adapter_family"] == "regops_controlled_readiness"
    assert by_id["dio_accreditation"]["atlas_product_class"] == "homs_accreditation"
    assert by_id["dio_accreditation"]["adapter_family"] == "accreditation_controlled_review"
    assert by_id["dio_agentauthority"]["atlas_product_class"] == "agent_authority"
    assert by_id["dio_agentauthority"]["adapter_family"] == "ai_trust_agent_authority"
    assert by_id["dio_dossierops"]["adapter_family"] == "controlled_dossier_assembly"
    for product_id in (
        "dio_homs_moderate",
        "dio_homs_curriculum",
        "dio_sophia_integrity",
        "dio_sophia_research",
        "dio_sophia_supervisor",
        "dio_sophia_tutor",
    ):
        assert by_id[product_id]["adapter_family"] == "homs_sophia_controlled_review"
    for product_id in high_risk_profiles_by_product():
        assert by_id[product_id]["adapter_family"] == "high_risk_controlled_review_no_engine"

    persisted = json.loads((output / "BATCH_EXECUTION_PROOF_RECEIPT.json").read_text(encoding="utf-8"))
    assert persisted == receipt
    for row in receipt["products"]:
        assert (output / row["relative_path"]).is_file()


def test_batch_runner_refuses_dirty_output_and_missing_operator(tmp_path: Path) -> None:
    dirty = tmp_path / "dirty"
    dirty.mkdir()
    (dirty / "stale.txt").write_text("stale\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be empty"):
        run_batch(output_root=dirty, operator_id=OPERATOR, now=NOW)

    with pytest.raises(ValueError, match="operator_id"):
        run_batch(output_root=tmp_path / "no-operator", operator_id="", now=NOW)
