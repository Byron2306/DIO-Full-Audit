from __future__ import annotations

from pathlib import Path

import pytest

from presence_core.customer_cases import load_case
from presence_core.journey_core import create_journey_case
from presence_core.intake_scope_quote import (
    approve_operator_review_quote,
    build_intake_requirement,
    open_intake,
    record_intake_inputs,
    assess_scope,
    prepare_quote,
)
from products.commercial_pricing_registry import build_commercial_pricing_registry


DIO_ROOT = Path(__file__).resolve().parents[1]


def test_all_68_products_expose_declarative_journey_intake_profiles() -> None:
    registry = build_commercial_pricing_registry(DIO_ROOT)
    products = registry["products"]

    assert len(products) == 68

    for product in products:
        profile = build_intake_requirement(DIO_ROOT, product["name"])
        required = {row["field_id"] for row in profile["required_inputs"]}

        assert required == {"requested_outcome", "buyer_class", "scope_quantity"}
        assert profile["scope"]["primary_unit"] == product["primary_scope_unit"]
        assert profile["quote_policy"]["mode"] == product["quote_authority"]["mode"]
        assert profile["quote_policy"]["autonomous_ceiling_zar"] == product["quote_authority"]["autonomous_ceiling_zar"]
        assert profile["authority_created"] is False


def test_intake_only_reports_missing_typed_inputs(tmp_path: Path) -> None:
    case = create_journey_case(tmp_path, product_id="Professional Correspondence")
    requirement = open_intake(DIO_ROOT, tmp_path, case["case_id"])

    assert requirement["schema"] == "dio.intake_requirement.v1"
    assert requirement["missing_input_ids"] == [
        "requested_outcome",
        "buyer_class",
        "scope_quantity",
    ]

    record_intake_inputs(
        DIO_ROOT,
        tmp_path,
        case["case_id"],
        {
            "requested_outcome": "Polish one client response",
            "buyer_class": "C1",
        },
        evidence_ref="customer:typed-intake-1",
    )

    requirement = build_intake_requirement(
        DIO_ROOT,
        "Professional Correspondence",
        provided_inputs=(load_case(tmp_path, case["case_id"]) or {})
        .get("intake", {})
        .get("provided_inputs", {}),
    )

    assert requirement["missing_input_ids"] == ["scope_quantity"]
    assert "requested_outcome" not in requirement["missing_input_ids"]
    assert "buyer_class" not in requirement["missing_input_ids"]

    with pytest.raises(ValueError, match="unknown intake field"):
        record_intake_inputs(
            DIO_ROOT,
            tmp_path,
            case["case_id"],
            {"chat_guess": "probably one page"},
            evidence_ref="conversation:free-text",
        )


def test_quote_is_blocked_until_scope_is_sufficient(tmp_path: Path) -> None:
    case = create_journey_case(tmp_path, product_id="Professional Correspondence")
    open_intake(DIO_ROOT, tmp_path, case["case_id"])
    record_intake_inputs(
        DIO_ROOT,
        tmp_path,
        case["case_id"],
        {
            "requested_outcome": "Polish one client response",
            "buyer_class": "C1",
        },
        evidence_ref="customer:typed-intake-2",
    )

    receipt = assess_scope(DIO_ROOT, tmp_path, case["case_id"])

    assert receipt["schema"] == "dio.scope_receipt.v1"
    assert receipt["state"] == "INCOMPLETE"
    assert receipt["missing_input_ids"] == ["scope_quantity"]
    assert (load_case(tmp_path, case["case_id"]) or {})["stage"] == "INTAKE_OPEN"

    with pytest.raises(ValueError, match="scope receipt is not sufficient"):
        prepare_quote(DIO_ROOT, tmp_path, case["case_id"])


def test_bounded_estimate_uses_registry_reference_and_never_invents_price(tmp_path: Path) -> None:
    case = create_journey_case(tmp_path, product_id="Professional Correspondence")
    open_intake(DIO_ROOT, tmp_path, case["case_id"])
    record_intake_inputs(
        DIO_ROOT,
        tmp_path,
        case["case_id"],
        {
            "requested_outcome": "Polish one client response",
            "buyer_class": "C1",
            "scope_quantity": 1,
        },
        evidence_ref="customer:typed-intake-3",
    )

    receipt = assess_scope(DIO_ROOT, tmp_path, case["case_id"])
    result = prepare_quote(DIO_ROOT, tmp_path, case["case_id"])
    quote = result["quote"]

    assert receipt["state"] == "SUFFICIENT"
    assert receipt["primary_scope_unit"] == "correspondence_item"
    assert result["schema"] == "dio.quote_result.v1"
    assert result["decision"] == "ALLOW_PRESENTATION"
    assert result["quote_request"]["schema"] == "dio.quote_request.v1"
    assert quote["schema"] == "dio.customer_quote.v2"
    assert quote["amount"] == 150
    assert quote["currency"] == "ZAR"
    assert quote["pricing_truth"] == "GOVERNED_REFERENCE_POINT"
    assert quote["commercial_validation"] == "UNPROVED"
    assert quote["quote_authority_mode"] == "bounded_estimate"
    assert quote["presentation_authority"] is True
    assert quote["invoice_issue_authority"] is False
    assert quote["fulfilment_authority_created"] is False
    assert quote["release_authority_created"] is False
    assert quote["authority_created"] is False
    assert (load_case(tmp_path, case["case_id"]) or {})["stage"] == "QUOTE_READY"


def test_operator_review_profile_returns_needs_you_without_customer_quote(tmp_path: Path) -> None:
    case = create_journey_case(tmp_path, product_id="DIO AI Assurance")
    open_intake(DIO_ROOT, tmp_path, case["case_id"])
    record_intake_inputs(
        DIO_ROOT,
        tmp_path,
        case["case_id"],
        {
            "requested_outcome": "Assess one AI system",
            "buyer_class": "C4",
            "scope_quantity": 1,
        },
        evidence_ref="customer:typed-intake-4",
    )

    receipt = assess_scope(DIO_ROOT, tmp_path, case["case_id"])
    result = prepare_quote(DIO_ROOT, tmp_path, case["case_id"])

    assert receipt["state"] == "SUFFICIENT"
    assert result["decision"] == "NEEDS_YOU"
    assert result["reason"] == "quote_authority_requires_operator_review"
    assert result["quote"] is None
    assert result["pricing_reference"]["amount_zar"] == 40000
    assert result["pricing_reference"]["customer_presentable"] is False
    assert result["authority_created"] is False
    assert (load_case(tmp_path, case["case_id"]) or {})["stage"] == "NEEDS_YOU"


def test_operator_review_can_resume_to_canonical_quote_ready(tmp_path: Path) -> None:
    case = create_journey_case(tmp_path, product_id="DIO AI Assurance")
    open_intake(DIO_ROOT, tmp_path, case["case_id"])
    record_intake_inputs(
        DIO_ROOT,
        tmp_path,
        case["case_id"],
        {
            "requested_outcome": "Assess one AI system",
            "buyer_class": "C4",
            "scope_quantity": 1,
        },
        evidence_ref="customer:operator-resume",
    )
    assess_scope(DIO_ROOT, tmp_path, case["case_id"])
    pending = prepare_quote(DIO_ROOT, tmp_path, case["case_id"])
    assert pending["decision"] == "NEEDS_YOU"

    approved = approve_operator_review_quote(
        DIO_ROOT,
        tmp_path,
        case["case_id"],
        approved_by="human:test-operator",
        approved_amount_zar=int(pending["pricing_reference"]["amount_zar"]),
        evidence_ref="operator:test-approval",
    )

    stored = load_case(tmp_path, case["case_id"])
    assert approved["decision"] == "ALLOW_PRESENTATION"
    assert approved["quote"]["quote_authority_mode"] == "operator_review"
    assert stored["stage"] == "QUOTE_READY"
