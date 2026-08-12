from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from products.meta import (
    EXPECTED_META_PRODUCTS,
    MetaProductError,
    compose_all_vertical_products,
    compose_vertical_product,
    load_meta_registry,
    validate_meta_registry,
    validate_vertical_composition,
)
from products.registry import load_portfolio

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_IDS = [
    "dio_assurance",
    "dio_agent_authority",
    "dio_vendorproof",
    "dio_accreditation",
    "dio_tenderproof",
    "dio_grantproof",
    "dio_research_integrity",
    "dio_regops",
    "dio_capitalroom",
]


def test_meta_registry_json_schema_is_valid_and_payload_conforms() -> None:
    schema = json.loads((ROOT / "schemas" / "dio_meta_products.schema.json").read_text(encoding="utf-8"))
    payload = json.loads((ROOT / "config" / "dio_meta_products.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)


def test_meta_registry_has_exact_four_products() -> None:
    registry = load_meta_registry()
    assert {row["id"] for row in registry["meta_products"]} == EXPECTED_META_PRODUCTS


def test_meta_registry_covers_governed_product_portfolio_exactly() -> None:
    registry = load_meta_registry()
    portfolio = load_portfolio()
    assert {row["product_id"] for row in registry["vertical_compositions"]} == {row["id"] for row in portfolio["products"]}


def test_every_meta_component_ref_exists_on_current_core() -> None:
    registry = load_meta_registry()
    refs = {ref for row in registry["meta_products"] for ref in row["component_refs"]}
    missing = sorted(ref for ref in refs if not (ROOT / ref).is_file())
    assert missing == []


def test_meta_layer_preserves_valinor_and_arda_roles() -> None:
    laws = load_meta_registry()["laws"]
    assert laws["kernel_authority"] == "Valinor"
    assert laws["execution_identity_authority"] == "ARDA"


def test_meta_products_have_no_independent_authority_execution_or_release() -> None:
    for row in load_meta_registry()["meta_products"]:
        assert row["authority"] is False
        assert row["execution"] is False
        assert row["external_release"] is False


def test_customer_facing_verticals_keep_meta_authority_as_release_guard() -> None:
    registry = load_meta_registry()
    portfolio = {row["id"]: row for row in load_portfolio()["products"]}
    for row in registry["vertical_compositions"]:
        if portfolio[row["product_id"]]["customer_facing"] is True:
            assert row["release_guard_meta_product"] == "meta_authority"


def test_capitalroom_remains_internal_and_has_no_release_guard() -> None:
    registry = load_meta_registry()
    row = next(item for item in registry["vertical_compositions"] if item["product_id"] == "dio_capitalroom")
    assert row["surface_mode"] == "internal"
    assert row["release_guard_meta_product"] is None
    assert row["primary_meta_product"] == "meta_room"


def test_regops_composes_all_four_meta_products() -> None:
    composition = compose_vertical_product("dio_regops")
    assert set(composition["required_meta_products"]) == EXPECTED_META_PRODUCTS


def test_tenderproof_composes_all_four_meta_products() -> None:
    composition = compose_vertical_product("dio_tenderproof")
    assert set(composition["required_meta_products"]) == EXPECTED_META_PRODUCTS


def test_agent_authority_is_meta_authority_led() -> None:
    composition = compose_vertical_product("dio_agent_authority")
    assert composition["primary_meta_product"] == "meta_authority"
    assert "meta_authority" in composition["required_meta_products"]


def test_assurance_is_meta_assurance_led() -> None:
    composition = compose_vertical_product("dio_assurance")
    assert composition["primary_meta_product"] == "meta_assurance"
    assert set(composition["required_meta_products"]) == {"meta_evidence", "meta_assurance", "meta_room"}


def test_all_compositions_are_unique_and_complete() -> None:
    compositions = compose_all_vertical_products()
    assert len(compositions) == 9
    assert {row["product_id"] for row in compositions} == set(PRODUCT_IDS)
    assert len({row["fingerprint"] for row in compositions}) == 9


def test_composition_is_deterministic() -> None:
    first = compose_vertical_product("dio_vendorproof")
    second = compose_vertical_product("dio_vendorproof")
    assert first == second


@pytest.mark.parametrize("product_id", PRODUCT_IDS)
def test_vertical_composition_preserves_portfolio_truth(product_id: str) -> None:
    portfolio = {row["id"]: row for row in load_portfolio()["products"]}
    composition = compose_vertical_product(product_id)
    profile = portfolio[product_id]
    assert composition["source_product_status"] == profile["status"]
    assert composition["runtime_mode"] == profile["runtime_mode"]
    assert composition["customer_facing"] == profile["customer_facing"]
    assert composition["campaign_enabled"] == profile["campaign_enabled"]
    assert composition["risk_boundary"] == profile["risk_boundary"]
    assert composition["activation_gates"] == profile["activation_gates"]
    assert composition["expected_outputs"] == profile["expected_outputs"]
    assert composition["authority_created"] is False
    assert composition["executor_created"] is False
    assert composition["external_release_authorized"] is False
    assert composition["market_validation_created"] is False
    assert composition["maturity_changed"] is False


def test_unknown_product_is_rejected() -> None:
    with pytest.raises(MetaProductError):
        compose_vertical_product("dio_magic_money_machine")


def test_tampered_composition_is_rejected() -> None:
    composition = compose_vertical_product("dio_assurance")
    composition["source_product_status"] = "market_dominating_cash_cannon"
    with pytest.raises(MetaProductError):
        validate_vertical_composition(composition)


def test_registry_rejects_authority_creation() -> None:
    registry = copy.deepcopy(load_meta_registry())
    registry["laws"]["meta_product_creates_authority"] = True
    with pytest.raises(MetaProductError):
        validate_meta_registry(registry)


def test_registry_rejects_maturity_rewrite_power() -> None:
    registry = copy.deepcopy(load_meta_registry())
    registry["laws"]["meta_product_changes_vertical_maturity"] = True
    with pytest.raises(MetaProductError):
        validate_meta_registry(registry)


def test_registry_rejects_unknown_meta_reference() -> None:
    registry = copy.deepcopy(load_meta_registry())
    registry["vertical_compositions"][0]["required_meta_products"].append("meta_unicorn")
    with pytest.raises(MetaProductError):
        validate_meta_registry(registry)


def test_registry_rejects_primary_product_not_in_required_composition() -> None:
    registry = copy.deepcopy(load_meta_registry())
    row = registry["vertical_compositions"][0]
    row["primary_meta_product"] = "meta_authority"
    with pytest.raises(MetaProductError):
        validate_meta_registry(registry)


def test_registry_rejects_customer_surface_without_authority_release_guard() -> None:
    registry = copy.deepcopy(load_meta_registry())
    row = next(item for item in registry["vertical_compositions"] if item["product_id"] == "dio_assurance")
    row["release_guard_meta_product"] = None
    with pytest.raises(MetaProductError):
        validate_meta_registry(registry)


def test_registry_rejects_capitalroom_becoming_customer_facing() -> None:
    registry = copy.deepcopy(load_meta_registry())
    row = next(item for item in registry["vertical_compositions"] if item["product_id"] == "dio_capitalroom")
    row["surface_mode"] = "customer_facing"
    with pytest.raises(MetaProductError):
        validate_meta_registry(registry)


def test_registry_rejects_duplicate_meta_capability() -> None:
    registry = copy.deepcopy(load_meta_registry())
    row = registry["meta_products"][0]
    row["capabilities"].append(row["capabilities"][0])
    with pytest.raises(MetaProductError):
        validate_meta_registry(registry)
