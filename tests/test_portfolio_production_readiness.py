from __future__ import annotations

import copy

import pytest

from products import portfolio_production_readiness as readiness


def _customer_surface_receipt() -> dict:
    contract = readiness.load_contract()
    crosswalk = readiness.load_crosswalk()
    internal = set(contract["internal_capabilities"])
    rows = []
    for incarnation in crosswalk:
        rows.append(
            {
                "surface_id": incarnation,
                "pipeline_state": "PASS",
                "engineering_surface_status": "REFUSE_NO_CUSTOMER_SURFACE" if incarnation in internal else "ENGINEERING_READY_NEEDS_BUYER_REVIEW",
                "surface_policy_id": "family-test",
                "surface_label": "customer artifact",
                "authority_created": False,
                "external_effects": False,
            }
        )
    for studio_id in contract["studio_ids"]:
        rows.append(
            {
                "surface_id": studio_id,
                "engineering_surface_status": "ENGINEERING_READY_NEEDS_BUYER_REVIEW",
                "authority_created": False,
                "external_effects": False,
            }
        )
    receipt = {
        "schema": "dio.portfolio.customer_surface_gauntlet_receipt.v1",
        "wave": "full57",
        "surface_count": 57,
        "rows": rows,
        "authority_created": False,
        "external_effects": False,
    }
    receipt["receipt_fingerprint"] = readiness._fingerprint(receipt)
    return receipt


def _studio_sellability_receipt() -> dict:
    contract = readiness.load_contract()
    studios = {}
    for studio_id in contract["studio_ids"]:
        studios[studio_id] = {
            "sellability_status": "PRODUCT_SELLABILITY_VERIFIED",
            "product_grade_status": "PRODUCT_GRADE_VERIFIED",
            "product_grade_score": 100,
            "buyer_grade_candidate": True,
            "critical_blockers": [],
            "semantic_visual_projection": {
                "baseline_bridge_verified": True,
                "unseen_bridge_verified": True,
                "semantic_input_changed": True,
                "semantic_visual_changed": True,
                "visual_artifact_changed": True,
                "role_does_not_select_geometry": True,
                "authority_created": False,
                "external_effects": False,
            },
        }
    receipt = {
        "schema": "dio.product_grade.sellability_portfolio_gauntlet_receipt.v1",
        "studio_count": 4,
        "studios": studios,
        "authority_created": False,
        "external_effects": False,
    }
    receipt["portfolio_fingerprint"] = readiness._fingerprint(receipt)
    return receipt


def _canonical_sellability_receipt() -> dict:
    contract = readiness.load_contract()
    internal = set(contract["internal_capabilities"])
    products = {
        incarnation: {
            "sellability_status": "PRODUCT_SELLABILITY_VERIFIED",
            "buyer_grade_candidate": True,
            "critical_blockers": [],
            "authority_created": False,
            "external_effects": False,
        }
        for incarnation in readiness.load_crosswalk()
        if incarnation not in internal
    }
    receipt = {
        "schema": "dio.portfolio.canonical_sellability_receipt.v1",
        "canonical_buyer_count": len(products),
        "products": products,
        "authority_created": False,
        "external_effects": False,
        "commercial_validation": "UNPROVED",
    }
    receipt["receipt_fingerprint"] = readiness._fingerprint(receipt)
    return receipt


def test_current_truth_keeps_47_canonical_buyer_products_unpromoted() -> None:
    receipt = readiness.evaluate_portfolio_production_readiness(
        customer_surface_receipt=_customer_surface_receipt(),
        studio_sellability_receipt=_studio_sellability_receipt(),
    )

    assert receipt["portfolio_production_ready"] is False
    assert receipt["acceptance_token"] == "DIO_PORTFOLIO_PRODUCTION_READINESS_MEASURED"
    assert receipt["surface_count"] == 57
    assert receipt["buyer_facing_surface_count"] == 51
    assert receipt["buyer_production_ready_count"] == 4
    assert receipt["buyer_needs_sellability_grade_count"] == 47
    assert receipt["buyer_refuse_count"] == 0
    assert receipt["internal_production_ready_count"] == 6
    assert receipt["internal_refuse_count"] == 0
    assert receipt["studio_sellability_verified_count"] == 4


def test_complete_canonical_sellability_can_promote_the_portfolio_without_commercial_overclaim() -> None:
    canonical = _canonical_sellability_receipt()
    receipt = readiness.evaluate_portfolio_production_readiness(
        customer_surface_receipt=_customer_surface_receipt(),
        studio_sellability_receipt=_studio_sellability_receipt(),
        canonical_sellability_receipt=canonical,
    )

    assert receipt["portfolio_production_ready"] is True
    assert receipt["acceptance_token"] == "DIO_PORTFOLIO_PRODUCTION_READY"
    assert receipt["buyer_production_ready_count"] == 51
    assert receipt["buyer_needs_sellability_grade_count"] == 0
    assert receipt["buyer_refuse_count"] == 0
    assert receipt["internal_production_ready_count"] == 6
    assert receipt["commercial_validation"] == "UNPROVED"
    assert receipt["authority_created"] is False
    assert receipt["external_effects"] is False
    assert receipt["input_evidence"]["canonical_sellability_receipt_fingerprint"] == canonical["receipt_fingerprint"]


def test_tampered_customer_surface_receipt_is_refused() -> None:
    customer_surface = _customer_surface_receipt()
    tampered = copy.deepcopy(customer_surface)
    tampered["rows"][0]["pipeline_state"] = "REFUSE"

    with pytest.raises(readiness.PortfolioProductionReadinessError, match="fingerprint mismatch"):
        readiness.evaluate_portfolio_production_readiness(
            customer_surface_receipt=tampered,
            studio_sellability_receipt=_studio_sellability_receipt(),
        )


def test_tampered_canonical_sellability_receipt_is_refused_before_promotion() -> None:
    tampered = _canonical_sellability_receipt()
    first = next(iter(tampered["products"]))
    tampered["products"][first]["sellability_status"] = "PRODUCT_SELLABILITY_REFUSE"

    with pytest.raises(readiness.PortfolioProductionReadinessError, match="canonical sellability receipt fingerprint mismatch"):
        readiness.evaluate_portfolio_production_readiness(
            customer_surface_receipt=_customer_surface_receipt(),
            studio_sellability_receipt=_studio_sellability_receipt(),
            canonical_sellability_receipt=tampered,
        )


def test_studio_sellability_failure_cannot_be_hidden_by_engineering_surface_readiness() -> None:
    studio_sellability = _studio_sellability_receipt()
    studio_sellability["studios"]["site_studio"]["sellability_status"] = "PRODUCT_SELLABILITY_REFUSE"
    studio_sellability["studios"]["site_studio"]["critical_blockers"] = ["BROKEN_CUSTOMER_ARTIFACT"]
    studio_sellability["portfolio_fingerprint"] = readiness._fingerprint(
        {key: value for key, value in studio_sellability.items() if key != "portfolio_fingerprint"}
    )

    receipt = readiness.evaluate_portfolio_production_readiness(
        customer_surface_receipt=_customer_surface_receipt(),
        studio_sellability_receipt=studio_sellability,
    )

    assert receipt["studio_sellability_verified_count"] == 3
    assert receipt["buyer_refuse_count"] == 1
    assert receipt["rows"]["site_studio"]["production_readiness_status"] == "REFUSE_PRODUCTION_READINESS"
    assert "BROKEN_CUSTOMER_ARTIFACT" in receipt["rows"]["site_studio"]["critical_blockers"]
