from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

from products.control_deck import ControlDeckError, ROOT, build_portfolio_snapshot, load_control_deck_config
from products.meta_runtime_gauntlet import run_meta_runtime_gauntlet


EXPECTED_SUITES = {
    "education_research",
    "evidence_assurance",
    "public_programme_ops",
    "ai_digital_trust",
    "enterprise_operations",
    "demand_presence",
}
EXPECTED_PRODUCTS = {"dio_contractproof", "dio_tenderproof", "dio_grantproof", "dio_permitproof", "dio_policyproof"}


@pytest.fixture(scope="module")
def runtime_receipt(tmp_path_factory: pytest.TempPathFactory) -> dict:
    return run_meta_runtime_gauntlet(output_dir=tmp_path_factory.mktemp("phase9-runtime"))


@pytest.fixture(scope="module")
def snapshot(runtime_receipt: dict) -> dict:
    return build_portfolio_snapshot(ROOT, runtime_receipt)


def test_control_deck_config_ports_goldeneye_without_merging_old_runtime() -> None:
    config = load_control_deck_config()
    assert config["surface_name"] == "GOLDENEYE"
    assert config["goldeneye"]["source_branch"] == "dio-c7-goldeneye-control-deck"
    assert config["goldeneye"]["history_merge_policy"] == "selective_port_only"
    assert "operator_first_needs_me" in config["goldeneye"]["reused_contracts"]
    assert config["laws"]["memory_is_permission"] is False


def test_snapshot_projects_all_six_suites_and_expanded_reference_products(snapshot: dict) -> None:
    assert {item["suite_id"] for item in snapshot["suites"]} == EXPECTED_SUITES
    assert {item["product_id"] for item in snapshot["products"]} == EXPECTED_PRODUCTS
    assert snapshot["summary"]["suite_count"] == 6
    assert snapshot["summary"]["registered_product_count"] == 5
    assert snapshot["summary"]["runtime_observed_product_count"] == 4


def test_snapshot_is_deterministic_and_source_bound(runtime_receipt: dict) -> None:
    first = build_portfolio_snapshot(ROOT, runtime_receipt)
    second = build_portfolio_snapshot(ROOT, runtime_receipt)
    assert first == second
    assert first["snapshot_fingerprint"].startswith("sha256:")
    assert len(first["source_fingerprints"]) >= 5


def test_control_deck_never_promotes_maturity_or_commercial_truth(snapshot: dict) -> None:
    assert snapshot["summary"]["internally_proven_count"] == 5
    assert snapshot["summary"]["externally_validated_count"] == 0
    assert snapshot["summary"]["revenue_proven_count"] == 0
    assert snapshot["summary"]["external_release_authorized_count"] == 0
    assert {item["maturity"]["state"] for item in snapshot["products"]} == {"internal_proof"}
    assert all(item["external_release_gate"] == "REFUSE" for item in snapshot["products"])


def test_needs_me_is_explicit_human_attention_not_an_action_queue(snapshot: dict) -> None:
    assert snapshot["summary"]["needs_you_count"] == 5
    assert len(snapshot["operator_attention"]) == 5
    for item in snapshot["operator_attention"]:
        assert item["state"] == "NEEDS_YOU"
        assert item["authorised_action"] == "inspect_bound_receipts_and_record_human_decision"
        assert item["may_execute"] is False
        assert item["may_release"] is False
        assert item["may_change_maturity"] is False


def test_unsafe_meta_runtime_receipt_is_refused(runtime_receipt: dict) -> None:
    tampered = copy.deepcopy(runtime_receipt)
    tampered["authority_created"] = True
    with pytest.raises(ControlDeckError, match="unsafe or untruthful"):
        build_portfolio_snapshot(ROOT, tampered)


def test_goldeneye_ui_is_portfolio_first_and_read_only() -> None:
    html = (ROOT / "dashboard" / "goldeneye-portfolio.html").read_text(encoding="utf-8")
    js = (ROOT / "dashboard" / "goldeneye-portfolio.js").read_text(encoding="utf-8")
    for label in (
        "DIO // GOLDENEYE", "Needs me now", "Portfolio truth", "Six-suite portfolio map",
        "Reference product state", "Consolidated META runtime", "Source integrity",
        "MEMORY ≠ PERMISSION",
    ):
        assert label in html
    assert "/api/control-deck/portfolio" in js
    assert "textContent" in js
    assert "fetch(\"/api/control-deck/portfolio\"" in js
    assert "method: \"POST\"" not in js
    assert "/api/control/" not in html + js


def test_goldeneye_server_is_valid_localhost_bound_and_rejects_post() -> None:
    source = (ROOT / "scripts" / "serve_goldeneye_portfolio.py").read_text(encoding="utf-8")
    ast.parse(source)
    assert 'args.host not in {"127.0.0.1", "localhost", "::1"}' in source
    assert "def do_POST" in source
    assert "METHOD_NOT_ALLOWED" in source
    assert "goldeneye_portfolio_is_projection_only" in source


def test_snapshot_schema_is_closed_and_truth_boundaries_are_false(snapshot: dict) -> None:
    schema = json.loads((ROOT / "schemas" / "dio_control_deck_snapshot.schema.json").read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert snapshot["truth_boundaries"]["projection_only"] is True
    for key, value in snapshot["truth_boundaries"].items():
        if key != "projection_only":
            assert value is False
