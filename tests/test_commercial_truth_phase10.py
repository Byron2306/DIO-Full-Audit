from __future__ import annotations

import ast
import copy
from pathlib import Path

import pytest

from products.commercial_truth import (
    CommercialTruthError,
    ROOT,
    build_commercial_truth_snapshot,
    discover_observations,
    evaluate_product,
    load_config,
)
from products.control_deck_gauntlet import run_control_deck_gauntlet


PRODUCTS = {"dio_contractproof", "dio_tenderproof", "dio_grantproof", "dio_permitproof"}


@pytest.fixture(scope="module")
def control_snapshot(tmp_path_factory: pytest.TempPathFactory) -> dict:
    out = tmp_path_factory.mktemp("phase10-control")
    run_control_deck_gauntlet(output_dir=out)
    import json
    return json.loads((out / "CONTROL_DECK_PORTFOLIO_SNAPSHOT.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def snapshot(control_snapshot: dict) -> dict:
    return build_commercial_truth_snapshot(ROOT, control_snapshot)


def _evidence(category: str, case_id: str, customer: str, *, amount: int | None = None, currency: str | None = None) -> dict:
    return {
        "observation_id": f"synthetic:{case_id}:{category}",
        "category": category,
        "source_class": "customer_attestation" if category == "customer_value_confirmed" else "bound_receipt",
        "environment": "live",
        "product_id": "dio_contractproof",
        "case_id": case_id,
        "customer_ref": customer,
        "amount_minor": amount,
        "currency": currency,
        "verified": True,
        "controlled": False,
        "attribution_complete": True,
        "qualifying": True,
        "truth_state": "QUALIFYING_EXTERNAL_EVIDENCE",
        "source_ref": "synthetic-test",
    }


def _economic_case(case_id: str, customer: str, currency: str) -> list[dict]:
    return [
        _evidence("payment_verified", case_id, customer, amount=10000, currency=currency),
        _evidence("fulfilment_completed", case_id, customer),
        _evidence("delivery_accepted", case_id, customer),
        _evidence("customer_value_confirmed", case_id, customer),
        _evidence("cost_recorded", case_id, customer, amount=2000, currency=currency),
        _evidence("labour_recorded", case_id, customer, amount=3000, currency=currency),
    ]


def test_existing_live_payment_is_preserved_but_not_laundered_into_revenue(snapshot: dict) -> None:
    assert snapshot["summary"]["live_verified_payment_count"] >= 1
    assert snapshot["summary"]["attributed_paid_case_count"] == 0
    assert snapshot["unattributed_value_minor_by_currency"]["USD"] >= 100
    assert snapshot["attributed_revenue_minor_by_currency"] == {}
    assert any(row["truth_state"] == "VERIFIED_UNATTRIBUTED_PAYMENT" for row in snapshot["observations"])


def test_controlled_transactions_never_become_market_validation(snapshot: dict) -> None:
    assert snapshot["summary"]["controlled_observation_count"] >= 1
    assert snapshot["summary"]["customer_validated_product_count"] == 0
    assert snapshot["summary"]["repeatable_product_count"] == 0
    assert snapshot["summary"]["economically_proven_product_count"] == 0


def test_absence_is_unknown_not_zero_or_failure(snapshot: dict) -> None:
    for product in snapshot["products"]:
        assert product["product_id"] in PRODUCTS
        assert product["claims"]["customer_validation"] == "UNKNOWN"
        assert product["claims"]["repeatability"] == "UNKNOWN"
        assert product["claims"]["economic_proof"] == "UNKNOWN"


def test_payment_alone_does_not_imply_downstream_claims() -> None:
    config = load_config()
    result = evaluate_product("dio_contractproof", [_evidence("payment_verified", "CASE-1", "CUST-1", amount=5000, currency="USD")], config)
    assert result["claims"]["paid_customer"] == "SUPPORTED"
    assert result["claims"]["fulfilment"] == "UNKNOWN"
    assert result["claims"]["delivery_acceptance"] == "UNKNOWN"
    assert result["claims"]["customer_validation"] == "UNKNOWN"
    assert result["claims"]["repeatability"] == "UNKNOWN"
    assert result["claims"]["economic_proof"] == "UNKNOWN"


def test_repeatability_and_economic_proof_require_two_independent_complete_cases() -> None:
    config = load_config()
    rows = _economic_case("CASE-1", "CUST-1", "USD") + _economic_case("CASE-2", "CUST-2", "ZAR")
    rows.append(_evidence("commercial_review_confirmed", "CASE-2", "CUST-2"))
    result = evaluate_product("dio_contractproof", rows, config)
    assert result["claims"]["customer_validation"] == "SUPPORTED"
    assert result["claims"]["repeatability"] == "SUPPORTED"
    assert result["claims"]["economic_proof"] == "SUPPORTED"
    assert result["same_currency_net_minor"] == {"USD": 5000, "ZAR": 5000}
    assert "TOTAL" not in result["same_currency_net_minor"]
    assert result["maturity_changed"] is False


def test_economic_evidence_without_human_review_is_not_economic_proof() -> None:
    rows = _economic_case("CASE-1", "CUST-1", "USD") + _economic_case("CASE-2", "CUST-2", "USD")
    result = evaluate_product("dio_contractproof", rows, load_config())
    assert result["claims"]["repeatability"] == "SUPPORTED"
    assert result["claims"]["economic_proof"] == "UNKNOWN"
    assert result["human_commercial_review"] is False


def test_projection_is_deterministic_and_refuses_unsafe_phase9(control_snapshot: dict) -> None:
    assert build_commercial_truth_snapshot(ROOT, control_snapshot) == build_commercial_truth_snapshot(ROOT, control_snapshot)
    unsafe = copy.deepcopy(control_snapshot)
    unsafe["truth_boundaries"]["authority_created"] = True
    with pytest.raises(CommercialTruthError, match="unsafe Phase 9"):
        build_commercial_truth_snapshot(ROOT, unsafe)


def test_goldeneye_surfaces_commercial_truth_without_action_endpoint() -> None:
    html = (ROOT / "dashboard" / "goldeneye-portfolio.html").read_text(encoding="utf-8")
    js = (ROOT / "dashboard" / "goldeneye-portfolio.js").read_text(encoding="utf-8")
    server = (ROOT / "scripts" / "serve_goldeneye_portfolio.py").read_text(encoding="utf-8")
    ast.parse(server)
    assert "Commercial Truth Layer" in html
    assert "Verified payment ≠ attributed revenue" in html
    assert "/api/commercial-truth" in js
    assert "/api/commercial-truth" in server
    assert "method: \"POST\"" not in js
    assert "METHOD_NOT_ALLOWED" in server


def test_truth_boundaries_all_remain_false(snapshot: dict) -> None:
    assert snapshot["truth_boundaries"]
    assert all(value is False for value in snapshot["truth_boundaries"].values())
