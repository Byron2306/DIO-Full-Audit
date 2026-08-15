from __future__ import annotations

import ast
from pathlib import Path

import pytest

from products.paid_reference import PaidReferenceError, ROOT, run_paid_reference_journey, validate_intake


def _payload() -> dict:
    return {
        "name": "Byron Reference Tester", "email": "byron@example.invalid", "organisation": "DIO",
        "message": "Run the complete controlled ContractProof reference chain.",
        "page_viewed": True, "information_acknowledged": True,
        "controlled_test_payment_consented": True, "website_honeypot": "",
    }


def test_complete_website_mailer_payment_fulfilment_chain_resolves(tmp_path: Path) -> None:
    journey = run_paid_reference_journey(_payload(), output_dir=tmp_path)
    assert journey["resolution"] == "RESOLVED_CONTROLLED_TEST"
    assert set(journey["steps"].values()) == {"PASS"}
    assert journey["commercial_truth"]["phase10_truth_state"] == "CONTROLLED_OR_UNVERIFIED_PAYMENT"
    assert journey["commercial_truth"]["controlled"] is True
    assert journey["gates"]["external_delivery"] == "REFUSE"
    assert (tmp_path / "fulfilment" / "proof" / "PROOF_MANIFEST.json").exists()


def test_journey_is_deterministic(tmp_path: Path) -> None:
    first = run_paid_reference_journey(_payload(), output_dir=tmp_path / "a")
    second = run_paid_reference_journey(_payload(), output_dir=tmp_path / "b")
    assert first == second


@pytest.mark.parametrize("field", ["page_viewed", "information_acknowledged", "controlled_test_payment_consented"])
def test_every_customer_journey_acknowledgement_is_required(field: str) -> None:
    payload = _payload()
    payload[field] = False
    with pytest.raises(PaidReferenceError, match=field):
        validate_intake(payload)


@pytest.mark.parametrize("field", ["card_number", "cvv", "expiry", "bank_account"])
def test_mailer_refuses_payment_credentials(field: str) -> None:
    payload = _payload()
    payload[field] = "do-not-store"
    with pytest.raises(PaidReferenceError, match="credentials"):
        validate_intake(payload)


def test_controlled_payment_never_becomes_revenue_or_validation(tmp_path: Path) -> None:
    journey = run_paid_reference_journey(_payload(), output_dir=tmp_path)
    assert journey["commercial_truth"]["attributed_revenue"] is False
    assert journey["commercial_truth"]["qualified_demand"] is False
    assert journey["commercial_truth"]["market_validation"] is False
    assert all(value is False for value in journey["truth_boundaries"].values())


def test_storefront_is_localhost_only_and_posts_only_to_bounded_endpoint() -> None:
    html = (ROOT / "dashboard" / "paid-reference.html").read_text(encoding="utf-8")
    js = (ROOT / "dashboard" / "paid-reference.js").read_text(encoding="utf-8")
    server = (ROOT / "scripts" / "serve_paid_reference_phase11.py").read_text(encoding="utf-8")
    ast.parse(server)
    assert "never collects card or bank details" in html
    assert "/api/reference-journey" in js and 'method: "POST"' in js
    assert "localhost-only" in server
    assert "mailto:" not in js.lower() and "paypal" not in js.lower()


def test_phase11_does_not_weaken_phase10_laws() -> None:
    import json
    phase10 = json.loads((ROOT / "config" / "portfolio" / "commercial_truth.json").read_text(encoding="utf-8"))
    assert phase10["laws"]["internal_tests_are_not_market_validation"] is True
    assert phase10["laws"]["payment_is_not_revenue_attribution"] is True
