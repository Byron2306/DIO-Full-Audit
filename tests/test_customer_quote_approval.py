from pathlib import Path

from presence_core.customer_cases import (
    create_or_attach_case,
    update_case,
)
from presence_core.customer_quotes import (
    approve_quote,
)


def test_quote_approval_creates_authority_object(
    tmp_path: Path,
) -> None:
    state_root = (
        tmp_path
        / "state"
        / "presence"
    )

    case = create_or_attach_case(
        state_root,
        conversation_id="CONV-TEST",
        channel="telegram",
        external_user_id="123",
        product_id="Sophia Integrity",
    )

    case = update_case(
        state_root,
        case,
        stage="PRICE_RECOMMENDED",
        patch={
            "attachments": [
                {
                    "attachment_id": "ATT-TEST",
                    "original_file_name": (
                        "manuscript.pdf"
                    ),
                    "sha256": "a" * 64,
                }
            ],
            "scope": {
                "quantity": 8,
                "primary_scope_unit":
                    "manuscript_page",
            },
            "commercial": {
                "recommended_amount_zar": 750,
                "scope_quantity": 8,
                "scope_unit":
                    "manuscript_page",
                "pricing_state": "HYPOTHESIS",
                "operator_review_required":
                    True,
                "quote_state":
                    "not_prepared",
            },
        },
        evidence_ref="test:pricing",
    )

    quote = approve_quote(
        state_root,
        case_id=case["case_id"],
        quote_id="DIO-Q-TEST-001",
        approved_by="operator:test",
    )

    assert quote["quote_state"] == "approved"
    assert quote["amount"] == 750
    assert quote["scope_quantity"] == 8
    assert quote["case_stage"] == "QUOTE_READY"
    assert (
        quote["fulfilment_authority_created"]
        is False
    )
    assert (
        quote["release_authority_created"]
        is False
    )


def test_bounded_professional_case_can_issue_quote_without_operator(
    tmp_path: Path,
) -> None:
    import presence_core.customer_quotes as customer_quotes

    assert hasattr(
        customer_quotes,
        "evaluate_bounded_quote_authority",
    ), "bounded quote authority evaluator is missing"

    assert hasattr(
        customer_quotes,
        "issue_bounded_quote",
    ), "bounded quote issuer is missing"

    state_root = (
        tmp_path
        / "state"
        / "presence"
    )

    dio_root = Path(__file__).resolve().parents[1]

    case = create_or_attach_case(
        state_root,
        conversation_id="CONV-BOUNDED-QUOTE",
        channel="telegram",
        external_user_id="123",
        product_id="Sophia Review",
    )

    case = update_case(
        state_root,
        case,
        stage="PRICE_RECOMMENDED",
        patch={
            "attachments": [
                {
                    "attachment_id": "ATT-SOPHIA-27",
                    "original_file_name": "article.pdf",
                    "sha256": "b" * 64,
                }
            ],
            "scope": {
                "quantity": 27,
                "primary_scope_unit": "manuscript_page",
                "scope_scan_sha256": "b" * 64,
                "semantic_analysis_performed": False,
                "embedded_content_executed": False,
            },
            "commercial": {
                "buyer_class": "C1",
                "recommended_amount_zar": 1000,
                "scope_quantity": 27,
                "scope_unit": "manuscript_page",
                "pricing_state": "HYPOTHESIS",
                "governed_reference_band_zar": {
                    "min": 450,
                    "max": 1500,
                },
                "operator_review_required": True,
                "quote_state": "not_prepared",
                "quote_issue_authority": False,
                "custom_discount_requested": False,
                "bespoke_terms_requested": False,
                "regulatory_exception": False,
            },
            "authority_created": False,
        },
        evidence_ref="test:bounded-pricing",
    )

    authority = (
        customer_quotes.evaluate_bounded_quote_authority(
            dio_root,
            case,
        )
    )

    assert authority["decision"] == "ALLOW"
    assert authority["buyer_class"] == "C1"
    assert authority["amount_zar"] == 1000
    assert authority["autonomous_ceiling_zar"] == 1500
    assert authority["operator_review_required"] is False
    assert authority["authority_created"] is False

    quote = customer_quotes.issue_bounded_quote(
        dio_root,
        state_root,
        case_id=case["case_id"],
        quote_id="DIO-Q-BOUNDED-001",
    )

    assert quote["quote_state"] == "approved"
    assert quote["amount"] == 1000
    assert quote["scope_quantity"] == 27
    assert quote["case_stage"] == "QUOTE_READY"

    assert (
        quote["approval"]["mode"]
        == "bounded_policy"
    )

    assert (
        quote["approval"]["approved_by"]
        == "policy:bounded_quote_authority"
    )

    assert quote["payment_state"] == "not_verified"

    assert (
        quote["fulfilment_authority_created"]
        is False
    )

    assert (
        quote["release_authority_created"]
        is False
    )

    assert quote["authority_created"] is False


def test_bounded_quote_requires_human_for_exception_case(
    tmp_path: Path,
) -> None:
    import json

    from presence_core.customer_quotes import (
        evaluate_bounded_quote_authority,
        issue_bounded_quote,
    )

    state_root = (
        tmp_path
        / "state"
        / "presence"
    )

    dio_root = Path(__file__).resolve().parents[1]

    case = create_or_attach_case(
        state_root,
        conversation_id="CONV-BOUNDED-REFUSE",
        channel="telegram",
        external_user_id="456",
        product_id="Sophia Review",
    )

    case = update_case(
        state_root,
        case,
        stage="PRICE_RECOMMENDED",
        patch={
            "attachments": [
                {
                    "attachment_id": "ATT-SOPHIA-REFUSE",
                    "original_file_name": "article.pdf",
                    "sha256": "c" * 64,
                }
            ],
            "scope": {
                "quantity": 27,
                "primary_scope_unit": "manuscript_page",
                "scope_scan_sha256": "c" * 64,
                "semantic_analysis_performed": False,
                "embedded_content_executed": False,
            },
            "commercial": {
                "buyer_class": "C4",
                "recommended_amount_zar": 1000,
                "scope_quantity": 27,
                "scope_unit": "manuscript_page",
                "pricing_state": "HYPOTHESIS",
                "governed_reference_band_zar": {
                    "min": 450,
                    "max": 1500,
                },
                "operator_review_required": True,
                "quote_state": "not_prepared",
                "quote_issue_authority": False,
                "custom_discount_requested": False,
                "bespoke_terms_requested": False,
                "regulatory_exception": False,
            },
            "authority_created": False,
        },
        evidence_ref="test:bounded-refusal",
    )

    authority = evaluate_bounded_quote_authority(
        dio_root,
        case,
    )

    assert authority["decision"] == "NEEDS_YOU"
    assert (
        authority["reason"]
        == "buyer_class_requires_operator"
    )

    try:
        issue_bounded_quote(
            dio_root,
            state_root,
            case_id=case["case_id"],
            quote_id="DIO-Q-BOUNDED-REFUSE-001",
        )
    except ValueError as exc:
        assert (
            "bounded quote authority denied"
            in str(exc)
        )
    else:
        raise AssertionError(
            "exception case must not issue bounded quote"
        )

    quote_path = (
        state_root
        / "customer_quotes"
        / "DIO-Q-BOUNDED-REFUSE-001.json"
    )

    assert not quote_path.exists()

    stored = json.loads(
        (
            state_root
            / "customer_cases"
            / "cases"
            / f"{case['case_id']}.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert stored["stage"] == "PRICE_RECOMMENDED"
    assert (
        stored["commercial"]["quote_state"]
        == "not_prepared"
    )
    assert (
        stored["commercial"]["quote_issue_authority"]
        is False
    )


def test_bounded_quote_accepts_governed_low_risk_buyer_scope(
    tmp_path: Path,
) -> None:
    from presence_core.customer_quotes import (
        evaluate_bounded_quote_authority,
    )

    state_root = (
        tmp_path
        / "state"
        / "presence"
    )

    dio_root = Path(__file__).resolve().parents[1]

    case = create_or_attach_case(
        state_root,
        conversation_id="CONV-BOUNDED-SCOPE",
        channel="telegram",
        external_user_id="789",
        product_id="Sophia Review",
    )

    case = update_case(
        state_root,
        case,
        stage="PRICE_RECOMMENDED",
        patch={
            "attachments": [
                {
                    "attachment_id": "ATT-SCOPE",
                    "original_file_name": "article.pdf",
                    "sha256": "e" * 64,
                }
            ],
            "scope": {
                "quantity": 27,
                "primary_scope_unit": "manuscript_page",
                "scope_scan_sha256": "e" * 64,
            },
            "commercial": {
                "buyer_scope": "individual_professional",
                "recommended_amount_zar": 1000,
                "scope_quantity": 27,
                "scope_unit": "manuscript_page",
                "pricing_state": "HYPOTHESIS",
                "governed_reference_band_zar": {
                    "min": 450,
                    "max": 1500,
                },
                "operator_review_required": True,
                "quote_state": "not_prepared",
                "quote_issue_authority": False,
                "custom_discount_requested": False,
                "bespoke_terms_requested": False,
                "regulatory_exception": False,
            },
        },
        evidence_ref="test:buyer-scope",
    )

    authority = evaluate_bounded_quote_authority(
        dio_root,
        case,
    )

    assert authority["decision"] == "ALLOW"
    assert (
        authority["buyer_scope"]
        == "individual_professional"
    )
    assert (
        authority["buyer_classes_evaluated"]
        == ["C0", "C1"]
    )
    assert authority["operator_review_required"] is False
