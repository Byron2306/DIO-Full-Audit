from pathlib import Path

import presence_core.fulfilment_egress as egress


def test_controlled_sophia_request_is_local_only(
    tmp_path: Path,
) -> None:
    assert hasattr(
        egress,
        "build_controlled_local_sophia_request",
    ), "controlled local Sophia request adapter is missing"

    case = {
        "case_id": "CASE-TEST-SOPHIA",
        "product_id": "Sophia Review",
        "stage": "PAYMENT_VERIFIED",
        "scope": {
            "attachment_id": "ATT-TEST-SOPHIA",
            "page_count": 27,
            "primary_scope_unit": "manuscript_page",
            "quantity": 27,
            "scope_scan_sha256": "",
        },
        "commercial": {
            "payment_state": "verified_controlled_test",
            "payment_evidence_ref": "controlled-test:CTS-TEST-001",
            "controlled_test_settlement": {
                "schema": "dio.controlled_test_settlement.v1",
                "receipt_id": "CTS-TEST-001",
                "controlled_test": True,
                "external_funds_moved": False,
                "revenue_recognised": False,
                "case_id": "CASE-TEST-SOPHIA",
                "attachment_id": "ATT-TEST-SOPHIA",
            },
        },
    }

    import hashlib

    source = tmp_path / "manuscript.pdf"
    source_bytes = b"controlled local Sophia manuscript"
    source.write_bytes(source_bytes)

    source_sha = hashlib.sha256(source_bytes).hexdigest()

    case["scope"]["scope_scan_sha256"] = source_sha

    request = egress.build_controlled_local_sophia_request(
        case,
        source_path=source,
        operator_id="operator:6.7G-gauntlet",
    )

    assert request["schema"] == "dio.sophia_review_request.v1"
    assert request["job_id"] == "SOPHIA-CASE-TEST-SOPHIA"

    assert request["document_path"] == str(source)

    assert request["external_retrieval"] is False
    assert request["reasoned_review_approved"] is True
    assert request["reasoned_provider"] == "local"
    assert request["reasoned_model"] == "qwen2.5:3b"

    assert request.get("gemini_review_approved") is not True
    assert request.get("gemini_model") in {None, ""}

    authority = request["controlled_test_authority"]

    assert authority["controlled_test"] is True
    assert authority["operator_id"] == "operator:6.7G-gauntlet"
    assert authority["case_id"] == "CASE-TEST-SOPHIA"
    assert authority["attachment_id"] == "ATT-TEST-SOPHIA"
    assert authority["source_sha256"] == source_sha

    assert authority["external_retrieval_authorized"] is False
    assert authority["remote_processing_authorized"] is False
    assert authority["customer_consent_claimed"] is False
    assert authority["authority_created"] is False


def test_controlled_sophia_request_refuses_without_controlled_settlement() -> None:
    import pytest

    case = {
        "case_id": "CASE-TEST-SOPHIA",
        "product_id": "Sophia Review",
        "stage": "QUOTE_READY",
        "scope": {
            "attachment_id": "ATT-TEST-SOPHIA",
            "scope_scan_sha256": "a" * 64,
        },
        "commercial": {
            "payment_state": "unverified",
        },
    }

    with pytest.raises(
        ValueError,
        match="controlled-test settlement",
    ):
        egress.build_controlled_local_sophia_request(
            case,
            source_path=Path("/tmp/test.pdf"),
            operator_id="operator:6.7G-gauntlet",
        )


def test_controlled_sophia_request_refuses_without_controlled_settlement() -> None:
    import pytest

    case = {
        "case_id": "CASE-TEST-SOPHIA",
        "product_id": "Sophia Review",
        "stage": "QUOTE_READY",
        "scope": {
            "attachment_id": "ATT-TEST-SOPHIA",
            "scope_scan_sha256": "a" * 64,
        },
        "commercial": {
            "payment_state": "unverified",
        },
    }

    with pytest.raises(
        ValueError,
        match="controlled-test settlement",
    ):
        egress.build_controlled_local_sophia_request(
            case,
            source_path=Path("/tmp/test.pdf"),
            operator_id="operator:6.7G-gauntlet",
        )


def test_controlled_sophia_request_refuses_settlement_lineage_mismatch() -> None:
    import pytest

    case = {
        "case_id": "CASE-TEST-SOPHIA",
        "product_id": "Sophia Review",
        "stage": "PAYMENT_VERIFIED",
        "scope": {
            "attachment_id": "ATT-TEST-SOPHIA",
            "scope_scan_sha256": "a" * 64,
        },
        "commercial": {
            "payment_state": "verified_controlled_test",
            "controlled_test_settlement": {
                "schema": "dio.controlled_test_settlement.v1",
                "receipt_id": "CTS-WRONG-001",
                "controlled_test": True,
                "external_funds_moved": False,
                "case_id": "CASE-SOMEONE-ELSE",
                "attachment_id": "ATT-WRONG",
            },
        },
    }

    with pytest.raises(
        ValueError,
        match="lineage",
    ):
        egress.build_controlled_local_sophia_request(
            case,
            source_path=Path("/tmp/test.pdf"),
            operator_id="operator:6.7G-gauntlet",
        )


def test_controlled_sophia_request_refuses_source_hash_mismatch(
    tmp_path: Path,
) -> None:
    import hashlib
    import pytest

    source = tmp_path / "manuscript.pdf"
    source.write_bytes(b"actual controlled manuscript bytes")

    expected_sha = hashlib.sha256(
        b"different manuscript bytes"
    ).hexdigest()

    case = {
        "case_id": "CASE-TEST-SOPHIA",
        "product_id": "Sophia Review",
        "stage": "PAYMENT_VERIFIED",
        "scope": {
            "attachment_id": "ATT-TEST-SOPHIA",
            "scope_scan_sha256": expected_sha,
        },
        "commercial": {
            "payment_state": "verified_controlled_test",
            "controlled_test_settlement": {
                "schema": "dio.controlled_test_settlement.v1",
                "receipt_id": "CTS-TEST-001",
                "controlled_test": True,
                "external_funds_moved": False,
                "case_id": "CASE-TEST-SOPHIA",
                "attachment_id": "ATT-TEST-SOPHIA",
            },
        },
    }

    with pytest.raises(
        ValueError,
        match="source SHA-256 mismatch",
    ):
        egress.build_controlled_local_sophia_request(
            case,
            source_path=source,
            operator_id="operator:6.7G-gauntlet",
        )


def test_controlled_sophia_request_refuses_missing_source() -> None:
    import pytest

    missing = Path("/tmp/definitely-not-present-sophia.pdf")

    case = {
        "case_id": "CASE-TEST-SOPHIA",
        "product_id": "Sophia Review",
        "stage": "PAYMENT_VERIFIED",
        "scope": {
            "attachment_id": "ATT-TEST-SOPHIA",
            "scope_scan_sha256": "a" * 64,
        },
        "commercial": {
            "payment_state": "verified_controlled_test",
            "controlled_test_settlement": {
                "schema": "dio.controlled_test_settlement.v1",
                "receipt_id": "CTS-TEST-001",
                "controlled_test": True,
                "external_funds_moved": False,
                "case_id": "CASE-TEST-SOPHIA",
                "attachment_id": "ATT-TEST-SOPHIA",
            },
        },
    }

    with pytest.raises(
        ValueError,
        match="source file",
    ):
        egress.build_controlled_local_sophia_request(
            case,
            source_path=missing,
            operator_id="operator:6.7G-gauntlet",
        )
