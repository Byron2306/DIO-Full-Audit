from __future__ import annotations

import ast
import json
import zipfile
from pathlib import Path

import pytest

from products.paid_reference import PaidReferenceError, ROOT, run_paid_reference_journey, validate_intake


def _payload() -> dict:
    return {
        "name": "Byron Reference Tester", "email": "byron@example.invalid", "organisation": "DIO",
        "message": "Run the complete controlled ContractProof reference chain.",
        "review_title": "Monthly service report review",
        "contract_text": "The Supplier shall provide the monthly service report by the fifth business day. The Customer must retain acceptance records for twelve months.",
        "evidence_notes": "The report and acceptance register have not yet been bound.",
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
    proof_dir = tmp_path / "fulfilment" / "proof"
    html = (proof_dir / "EVIDENCE_PACK.html").read_text(encoding="utf-8")
    assert "Executive summary" in html and "Priority actions" in html and "Obligation review" in html
    assert "The Supplier shall provide" in html
    assert "<pre>" not in html and "fixture://" not in html
    with zipfile.ZipFile(proof_dir / "EVIDENCE_PACK.docx") as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
    assert "Executive summary" in document_xml and "The Supplier shall provide" in document_xml
    assert "fixture://" not in document_xml
    bundle = json.loads((proof_dir / "OBLIGATION_BUNDLE.json").read_text(encoding="utf-8"))
    assert bundle["source"]["source_ref"].startswith("intake://")
    assert bundle["source"]["sha256"] == __import__("hashlib").sha256(_payload()["contract_text"].encode()).hexdigest()


def test_journey_is_deterministic(tmp_path: Path) -> None:
    first = run_paid_reference_journey(_payload(), output_dir=tmp_path / "a")
    second = run_paid_reference_journey(_payload(), output_dir=tmp_path / "b")
    assert first == second


def test_contract_content_changes_journey_identity(tmp_path: Path) -> None:
    first = run_paid_reference_journey(_payload(), output_dir=tmp_path / "a")
    changed = _payload()
    changed["contract_text"] = "The Supplier shall deliver a signed inspection record within seven calendar days."
    second = run_paid_reference_journey(changed, output_dir=tmp_path / "b")
    assert first["journey_id"] != second["journey_id"]


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
    assert 'name="contract_text"' in html and 'name="review_title"' in html
    assert "/api/reference-journey" in js and 'method: "POST"' in js
    assert "localhost-only" in server
    assert "mailto:" not in js.lower() and "paypal" not in js.lower()


def test_phase11_does_not_weaken_phase10_laws() -> None:
    import json
    phase10 = json.loads((ROOT / "config" / "portfolio" / "commercial_truth.json").read_text(encoding="utf-8"))
    assert phase10["laws"]["internal_tests_are_not_market_validation"] is True
    assert phase10["laws"]["payment_is_not_revenue_attribution"] is True
