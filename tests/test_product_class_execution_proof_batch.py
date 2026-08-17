from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_product_class_execution_proof_batch import registered_products, run_batch


NOW = "2026-08-17T21:00:00+00:00"
OPERATOR = "human.product_class_batch_test"


def test_batch_runner_proves_all_currently_attached_products(tmp_path: Path) -> None:
    products = registered_products()
    assert len(products) == 18
    assert "dio_contractproof" in products
    assert "dio_regops" in products

    output = tmp_path / "proof-bundle"
    receipt = run_batch(output_root=output, operator_id=OPERATOR, now=NOW)
    assert receipt["schema"] == "dio.product_class.execution_proof_batch.v1"
    assert receipt["registered_proof_adapters"] == 18
    assert receipt["controlled_routes_proved"] == 18
    assert receipt["all_controlled_routes_proved"] is True
    assert receipt["public_launch_ready_products"] == []
    assert len(receipt["products"]) == 18
    assert all(row["execution_proof_state"] == "CONTROLLED_ROUTE_PROVED" for row in receipt["products"])
    assert all(row["human_review_gate"] == "NEEDS_YOU" for row in receipt["products"])
    assert all(row["external_release_gate"] == "REFUSE" for row in receipt["products"])
    assert all(row["public_launch_ready"] is False for row in receipt["products"])

    contract = next(row for row in receipt["products"] if row["product_id"] == "dio_contractproof")
    assert contract["adapter_family"] == "vesper_contractproof_attachment_journey"
    regops = next(row for row in receipt["products"] if row["product_id"] == "dio_regops")
    assert regops["adapter_family"] == "regops_controlled_readiness"

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
