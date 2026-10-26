import pytest

from presence_core.commercial_fx import (
    CommercialFXError,
    build_fx_receipt,
)


def test_fx_receipt_preserves_both_currency_truths():
    receipt = build_fx_receipt(
        quoted_amount_minor=75000,
        quoted_currency="ZAR",
        settlement_currency="USD",
        rate="0.055",
        rate_source="test-source",
        observed_at="2026-09-16T16:30:00+02:00",
    )

    assert receipt["quoted_amount_minor"] == 75000
    assert receipt["quoted_currency"] == "ZAR"
    assert receipt["settlement_amount_minor"] == 4125
    assert receipt["settlement_currency"] == "USD"
    assert receipt["authority_created"] is False
    assert receipt["payment_verified"] is False
    assert receipt["fulfilment_released"] is False
    assert len(receipt["receipt_sha256"]) == 64


def test_fx_rounding_is_explicit():
    receipt = build_fx_receipt(
        quoted_amount_minor=75000,
        quoted_currency="ZAR",
        settlement_currency="USD",
        rate="0.054321",
        rate_source="test-source",
        observed_at="2026-09-16T16:30:00+02:00",
    )

    assert receipt["settlement_amount_minor"] == 4074
    assert receipt["rounding"] == "ROUND_HALF_UP_TO_MINOR_UNIT"


def test_invalid_fx_rate_refused():
    with pytest.raises(CommercialFXError):
        build_fx_receipt(
            quoted_amount_minor=75000,
            quoted_currency="ZAR",
            settlement_currency="USD",
            rate="0",
            rate_source="test-source",
            observed_at="2026-09-16T16:30:00+02:00",
        )
