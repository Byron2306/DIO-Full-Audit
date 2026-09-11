from __future__ import annotations

from pathlib import Path

from presence_core.pricing_governance import (
    build_pricing_intelligence,
    classify_pricing_evidence,
)


ROOT = Path(__file__).resolve().parents[1]


def _case(
    *,
    case_id: str,
    product_id: str = "sophia_integrity",
    amount: int = 1800,
    payment_state: str = "verified",
    wtp: str = "PROVED",
    validation: str = "PROVED",
    independent: bool = True,
    refund: str = "none",
    dispute: str = "none",
    quote_state: str = "accepted",
):
    return {
        "case_id": case_id,
        "product_id": product_id,
        "stage": "CLOSED",
        "commercial": {
            "amount": amount,
            "currency": "ZAR",
            "payment_state": payment_state,
            "willingness_to_pay": wtp,
            "commercial_validation": validation,
            "independent_customer": independent,
            "refund_state": refund,
            "dispute_state": dispute,
            "quote_state": quote_state,
        },
    }


def test_only_independent_verified_paid_acceptance_is_positive_wtp_evidence():
    clean = classify_pricing_evidence(_case(case_id="CLEAN"))
    assert clean["pricing_evidence_class"] == "VERIFIED_INDEPENDENT_WTP"
    assert clean["positive_wtp"] is True

    self_paid = classify_pricing_evidence(_case(case_id="SELF", independent=False))
    refunded = classify_pricing_evidence(_case(case_id="REFUND", refund="refunded"))
    disputed = classify_pricing_evidence(_case(case_id="DISPUTE", dispute="open"))
    unverified = classify_pricing_evidence(_case(case_id="UNVERIFIED", payment_state="marker_only"))

    for row in (self_paid, refunded, disputed, unverified):
        assert row["positive_wtp"] is False

    assert self_paid["pricing_evidence_class"] == "SELF_OR_NON_INDEPENDENT_PAYMENT"
    assert refunded["pricing_evidence_class"] == "REFUND_OR_DISPUTE"
    assert disputed["pricing_evidence_class"] == "REFUND_OR_DISPUTE"
    assert unverified["pricing_evidence_class"] == "UNVERIFIED_SETTLEMENT"


def test_verified_history_refines_recommendation_inside_existing_band_without_mutating_band():
    cases = [
        _case(case_id="A", amount=1200),
        _case(case_id="B", amount=1800),
        _case(case_id="C", amount=2200),
    ]

    intelligence = build_pricing_intelligence(ROOT, cases=cases)
    row = next(item for item in intelligence["products"] if item["product_id"] == "sophia_integrity")

    assert row["governed_reference_band_zar"] == {"min": 750, "max": 3500}
    assert row["recommended_amount_zar"] == 1800
    assert row["verified_independent_wtp_count"] == 3
    assert row["pricing_state"] == "EVIDENCE_ACCUMULATING"
    assert row["customers_will_pay"] == "EVIDENCE_SUPPORTED"
    assert row["band_mutated"] is False
    assert row["band_mutation_authority"] is False
    assert row["quote_issue_authority"] is False
    assert intelligence["authority_created"] is False
    assert intelligence["external_effects"] is False


def test_out_of_band_paid_evidence_requires_operator_review_instead_of_silent_band_expansion():
    intelligence = build_pricing_intelligence(
        ROOT,
        cases=[_case(case_id="OUTSIDE", amount=5000)],
    )
    row = next(item for item in intelligence["products"] if item["product_id"] == "sophia_integrity")

    assert row["governed_reference_band_zar"] == {"min": 750, "max": 3500}
    assert row["recommended_amount_zar"] <= 3500
    assert row["band_change_candidate"] is True
    assert row["operator_review_required"] is True
    assert row["band_mutated"] is False
    assert row["band_mutation_authority"] is False


def test_no_clean_evidence_preserves_hypothesis_truth_boundary():
    intelligence = build_pricing_intelligence(
        ROOT,
        cases=[_case(case_id="SELF", independent=False)],
    )
    row = next(item for item in intelligence["products"] if item["product_id"] == "sophia_integrity")

    assert row["pricing_state"] == "HYPOTHESIS"
    assert row["customers_will_pay"] == "UNPROVED"
    assert row["verified_independent_wtp_count"] == 0
    assert row["recommended_amount_zar"] >= row["governed_reference_band_zar"]["min"]
    assert row["recommended_amount_zar"] <= row["governed_reference_band_zar"]["max"]


def test_pricing_intelligence_covers_canonical_68_and_proposes_bounded_next_experiment():
    intelligence = build_pricing_intelligence(ROOT, cases=[])

    assert intelligence["schema"] == "dio.pricing_intelligence.v1"
    assert intelligence["product_count"] == 68
    assert len(intelligence["products"]) == 68
    assert intelligence["truth_class"] == "PRICING_HYPOTHESIS_AND_SETTLED_EVIDENCE"
    assert intelligence["authority_created"] is False
    assert intelligence["external_effects"] is False

    row = next(item for item in intelligence["products"] if item["product_id"] == "homs_assess")
    experiment = row["next_experiment"]
    assert experiment["mode"] == "BOUNDED_PRICE_TEST"
    assert row["governed_reference_band_zar"]["min"] <= experiment["test_amount_zar"] <= row["governed_reference_band_zar"]["max"]
    assert experiment["send_authority"] is False
    assert experiment["quote_issue_authority"] is False


def test_commercial_proof_receipt_projects_wtp_truth_into_customer_case(tmp_path):
    from presence_core.customer_cases import create_or_attach_case, load_case
    from presence_core.pricing_governance import apply_commercial_proof_to_case

    state_root = tmp_path / "presence"
    case = create_or_attach_case(
        state_root,
        conversation_id="CONV-1",
        channel="outlook",
        external_user_id="CUSTOMER-1",
        product_id="sophia_integrity",
    )
    receipt = {
        "schema": "dio.commercial_proof_gauntlet_receipt.v1.1",
        "product_id": "sophia_integrity",
        "payment": {
            "verified_payment": "PROVED",
            "willingness_to_pay": "PROVED",
            "wtp_corroboration": "INDEPENDENT_CUSTOMER_PAYMENT_AND_ACCEPTANCE",
        },
        "customer_acceptance": {
            "commercial_customer_acceptance": "PROVED",
            "independent_customer": True,
            "customer_originated": True,
            "source_kind": "outlook_customer_reply",
            "source_message_id": "MSG-1",
        },
        "commercial_validation": "PROVED",
        "receipt_fingerprint": "sha256:test",
        "authority_created": False,
        "external_effects": False,
    }

    result = apply_commercial_proof_to_case(state_root, case["case_id"], receipt)
    stored = load_case(state_root, case["case_id"])

    assert result["pricing_evidence_projected"] is True
    assert stored["commercial"]["willingness_to_pay"] == "PROVED"
    assert stored["commercial"]["commercial_validation"] == "PROVED"
    assert stored["commercial"]["independent_customer"] is True
    assert stored["commercial"]["customer_originated"] is True
    assert stored["commercial"]["commercial_proof_receipt_fingerprint"] == "sha256:test"
    assert stored["authority_created"] is False


def test_commercial_proof_projection_refuses_product_mismatch(tmp_path):
    from presence_core.customer_cases import create_or_attach_case
    from presence_core.pricing_governance import apply_commercial_proof_to_case

    state_root = tmp_path / "presence"
    case = create_or_attach_case(
        state_root,
        conversation_id="CONV-2",
        channel="outlook",
        external_user_id="CUSTOMER-2",
        product_id="homs_assess",
    )
    receipt = {
        "schema": "dio.commercial_proof_gauntlet_receipt.v1.1",
        "product_id": "sophia_integrity",
        "payment": {"verified_payment": "PROVED", "willingness_to_pay": "PROVED"},
        "customer_acceptance": {"commercial_customer_acceptance": "PROVED", "independent_customer": True},
        "commercial_validation": "PROVED",
        "authority_created": False,
        "external_effects": False,
    }

    try:
        apply_commercial_proof_to_case(state_root, case["case_id"], receipt)
    except ValueError as exc:
        assert "product mismatch" in str(exc).lower()
    else:
        raise AssertionError("commercial proof silently crossed product lineage")


def test_state_backed_pricing_intelligence_reads_canonical_customer_cases(tmp_path):
    from presence_core.customer_cases import create_or_attach_case, update_case
    from presence_core.pricing_governance import build_pricing_intelligence_from_state

    state_root = tmp_path / "presence"
    case = create_or_attach_case(
        state_root,
        conversation_id="CONV-3",
        channel="outlook",
        external_user_id="CUSTOMER-3",
        product_id="sophia_integrity",
    )
    update_case(
        state_root,
        case,
        patch={
            "commercial": {
                "amount": 1900,
                "currency": "ZAR",
                "payment_state": "verified",
                "willingness_to_pay": "PROVED",
                "commercial_validation": "PROVED",
                "independent_customer": True,
                "refund_state": "none",
                "dispute_state": "none",
            }
        },
    )

    intelligence = build_pricing_intelligence_from_state(ROOT, state_root=state_root)
    row = next(item for item in intelligence["products"] if item["product_id"] == "sophia_integrity")
    assert row["verified_independent_wtp_count"] == 1
    assert row["recommended_amount_zar"] == 1900


def test_control_deck_exposes_read_only_slice4_pricing_cockpit():
    source = (ROOT / "scripts" / "serve_business_workbench.py").read_text(encoding="utf-8")
    assert "build_pricing_intelligence_from_state" in source
    assert '"/api/business/pricing"' in source
    assert "/dashboard/pricing_slice4.js" in source

    browser = (ROOT / "dashboard" / "pricing_slice4.js").read_text(encoding="utf-8")
    for label in ("Pricing governance", "Evidence-supported", "Operator review", "WTP evidence"):
        assert label in browser
    assert "/api/business/pricing" in browser
    assert "Reference bands remain governed hypotheses" in browser
    assert "authority_created" in browser
