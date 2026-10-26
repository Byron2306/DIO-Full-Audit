from __future__ import annotations

from pathlib import Path

import pytest

from presence_core.customer_cases import load_case
from presence_core.intake_scope_quote import (
    assess_scope,
    open_intake,
    prepare_quote,
    record_intake_inputs,
)
from presence_core.journey_core import create_journey_case
from presence_core.settlement_truth import (
    record_controlled_test_settlement,
    record_real_settlement,
    record_waived_settlement,
    settlement_truth,
)


DIO_ROOT = Path(__file__).resolve().parents[1]


def _quoted_case(tmp_path: Path) -> tuple[dict, dict]:
    case = create_journey_case(
        tmp_path,
        product_id="Professional Correspondence",
    )
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
        evidence_ref="customer:phase3-intake",
    )
    assess_scope(DIO_ROOT, tmp_path, case["case_id"])
    result = prepare_quote(DIO_ROOT, tmp_path, case["case_id"])
    assert result["decision"] == "ALLOW_PRESENTATION"
    return load_case(tmp_path, case["case_id"]), result["quote"]


def test_real_settlement_records_money_revenue_market_and_fulfilment_truth(
    tmp_path: Path,
) -> None:
    case, quote = _quoted_case(tmp_path)

    receipt = record_real_settlement(
        tmp_path,
        case["case_id"],
        provider="paypal",
        provider_receipt_id="PAYPAL-REAL-001",
        amount_minor=15000,
        currency="ZAR",
        external_funds_moved=True,
        evidence_ref="paypal:capture:PAYPAL-REAL-001",
    )

    stored = load_case(tmp_path, case["case_id"])

    assert receipt["schema"] == "dio.settlement_receipt.v1"
    assert receipt["settlement_class"] == "REAL_SETTLEMENT"
    assert receipt["quote_id"] == quote["quote_id"]
    assert receipt["quote_truth_sha256"] == quote["quote_truth_sha256"]
    assert receipt["external_funds_moved"] is True
    assert receipt["revenue_recognised"] is True
    assert receipt["market_validation_eligible"] is True
    assert receipt["fulfilment_eligible"] is True
    assert receipt["release_authority_created"] is False
    assert receipt["authority_created"] is False
    assert len(receipt["settlement_receipt_sha256"]) == 64
    assert stored["stage"] == "PAYMENT_VERIFIED"
    assert settlement_truth(stored)["settlement_class"] == "REAL_SETTLEMENT"


def test_controlled_test_can_unlock_test_fulfilment_without_money_or_revenue(
    tmp_path: Path,
) -> None:
    case, _quote = _quoted_case(tmp_path)

    receipt = record_controlled_test_settlement(
        tmp_path,
        case["case_id"],
        receipt_id="TEST-001",
        authorized_by="operator:byron",
        reason="Phase 3 controlled journey gauntlet",
    )

    stored = load_case(tmp_path, case["case_id"])

    assert receipt["settlement_class"] == "CONTROLLED_TEST_SETTLEMENT"
    assert receipt["external_funds_moved"] is False
    assert receipt["revenue_recognised"] is False
    assert receipt["market_validation_eligible"] is False
    assert receipt["fulfilment_eligible"] is True
    assert receipt["operator_self_transaction"] is True
    assert receipt["release_authority_created"] is False
    assert stored["stage"] == "PAYMENT_VERIFIED"
    assert stored["commercial"]["revenue_recognised"] is False


def test_waived_settlement_is_explicit_non_payment_and_non_revenue(
    tmp_path: Path,
) -> None:
    case, _quote = _quoted_case(tmp_path)

    receipt = record_waived_settlement(
        tmp_path,
        case["case_id"],
        receipt_id="WAIVE-001",
        waived_by="operator:byron",
        reason="Approved reference-customer waiver",
    )

    assert receipt["settlement_class"] == "WAIVED"
    assert receipt["external_funds_moved"] is False
    assert receipt["revenue_recognised"] is False
    assert receipt["market_validation_eligible"] is False
    assert receipt["fulfilment_eligible"] is True
    assert receipt["waived_by"] == "operator:byron"
    assert receipt["release_authority_created"] is False

    case2, _ = _quoted_case(tmp_path / "missing-reason")
    with pytest.raises(ValueError, match="reason is required"):
        record_waived_settlement(
            tmp_path / "missing-reason",
            case2["case_id"],
            receipt_id="WAIVE-002",
            waived_by="operator:byron",
            reason="",
        )


def test_real_settlement_refuses_false_or_mismatched_payment_truth(
    tmp_path: Path,
) -> None:
    case, _quote = _quoted_case(tmp_path)

    with pytest.raises(ValueError, match="external funds must be verified as moved"):
        record_real_settlement(
            tmp_path,
            case["case_id"],
            provider="paypal",
            provider_receipt_id="PAYPAL-FAKE-001",
            amount_minor=15000,
            currency="ZAR",
            external_funds_moved=False,
            evidence_ref="paypal:capture:PAYPAL-FAKE-001",
        )

    with pytest.raises(ValueError, match="settlement amount does not match quote"):
        record_real_settlement(
            tmp_path,
            case["case_id"],
            provider="paypal",
            provider_receipt_id="PAYPAL-WRONG-001",
            amount_minor=14999,
            currency="ZAR",
            external_funds_moved=True,
            evidence_ref="paypal:capture:PAYPAL-WRONG-001",
        )

    with pytest.raises(ValueError, match="settlement currency does not match quote"):
        record_real_settlement(
            tmp_path,
            case["case_id"],
            provider="paypal",
            provider_receipt_id="PAYPAL-WRONG-002",
            amount_minor=15000,
            currency="USD",
            external_funds_moved=True,
            evidence_ref="paypal:capture:PAYPAL-WRONG-002",
        )


def test_settlement_requires_canonical_phase2_quote_truth(tmp_path: Path) -> None:
    case = create_journey_case(
        tmp_path,
        product_id="Professional Correspondence",
    )

    with pytest.raises(ValueError, match="canonical Phase 2 quote truth is required"):
        record_controlled_test_settlement(
            tmp_path,
            case["case_id"],
            receipt_id="TEST-NO-QUOTE",
            authorized_by="operator:byron",
            reason="must not bypass quote truth",
        )
