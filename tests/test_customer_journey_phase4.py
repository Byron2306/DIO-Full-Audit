from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from presence_core.customer_cases import load_case, update_case
from presence_core.fulfilment_contract import (
    build_fulfilment_request,
    dispatch_fulfilment,
    project_execution_profile,
)
from presence_core.journey_core import create_journey_case
from presence_core.intake_scope_quote import (
    assess_scope,
    open_intake,
    prepare_quote,
    record_intake_inputs,
)
from presence_core.settlement_truth import record_controlled_test_settlement


DIO_ROOT = Path(__file__).resolve().parents[1]


def _hash(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _eligible_case(tmp_path: Path, product_id: str = "Product Alpha") -> dict:
    case = create_journey_case(tmp_path, product_id=product_id)

    scope = {
        "schema": "dio.scope_receipt.v1",
        "case_id": case["case_id"],
        "product_id": product_id,
        "state": "SUFFICIENT",
    }
    scope["scope_receipt_sha256"] = _hash(scope)

    quote = {
        "schema": "dio.customer_quote.v2",
        "quote_id": f"QUOTE-{case['case_id']}",
        "case_id": case["case_id"],
        "product_id": product_id,
        "product_name": product_id,
        "scope_receipt_sha256": scope["scope_receipt_sha256"],
        "amount": 100,
        "currency": "ZAR",
    }
    quote["quote_truth_sha256"] = _hash(quote)

    settlement = {
        "schema": "dio.settlement_receipt.v1",
        "settlement_class": "CONTROLLED_TEST_SETTLEMENT",
        "case_id": case["case_id"],
        "quote_id": quote["quote_id"],
        "quote_truth_sha256": quote["quote_truth_sha256"],
        "product_id": product_id,
        "product_name": product_id,
        "amount_minor": 10000,
        "currency": "ZAR",
        "provider": "dio_controlled_test",
        "provider_receipt_id": "TEST-001",
        "evidence_ref": "controlled-test:TEST-001",
        "external_funds_moved": False,
        "revenue_recognised": False,
        "market_validation_eligible": False,
        "fulfilment_eligible": True,
        "operator_self_transaction": True,
        "release_authority_created": False,
        "authority_created": False,
    }
    settlement["settlement_receipt_sha256"] = _hash(settlement)

    update_case(
        tmp_path,
        case,
        stage="PAYMENT_VERIFIED",
        patch={
            "scope_receipt": scope,
            "commercial": {
                "quote_result": {
                    "decision": "ALLOW_PRESENTATION",
                    "quote": quote,
                },
                "fulfilment_eligible": True,
            },
            "settlement": settlement,
        },
        evidence_ref=f"settlement:{settlement['settlement_receipt_sha256']}",
    )
    return load_case(tmp_path, case["case_id"])


def _profile(product_id: str, adapter_id: str = "adapter.shared") -> dict:
    compiled = {
        "schema": "dio.compiled_product.v1",
        "compiler_version": "1.1.0",
        "product_id": product_id.lower().replace(" ", "-"),
        "name": product_id,
        "composition_fingerprint": "sha256:" + "1" * 64,
        "compilation_fingerprint": "sha256:" + "2" * 64,
        "capability_plan": [
            {
                "capability_id": "product.executor.reference",
                "required": True,
                "execution_required": True,
                "resolution_state": "RESOLVED",
                "provider": {
                    "provider_id": "reference-provider",
                    "provider_kind": "local",
                    "ref": "products/reference_executor.py",
                    "execution_capable": True,
                    "product_scope": ["*"],
                },
                "reason": "test fixture",
            }
        ],
        "gates": {
            "execution": {
                "state": "NEEDS_YOU",
                "reason": "explicit initiation remains required",
            }
        },
        "output_plan": {
            "schema": "dio.compiled_output_plan.v1",
            "outputs": [{"kind": "document"}],
        },
    }
    return project_execution_profile(
        compiled,
        adapter_id=adapter_id,
        adapter_version="1.0.0",
    )


def _completed_adapter(label: str):
    def adapter(request: dict, execution_profile: dict) -> dict:
        return {
            "status": "COMPLETED",
            "artifacts": [
                {
                    "artifact_id": f"ART-{label}",
                    "kind": "document",
                    "file_name": f"{label}.pdf",
                    "mime_type": "application/pdf",
                    "sha256": "a" * 64,
                    "release_state": "HELD",
                }
            ],
            "evidence_refs": [f"proof:{label}"],
            "organ_steps": [
                {"organ": "evidex", "state": "PASS"},
                {"organ": "format_core", "state": "PASS"},
            ],
            "release_authority": False,
            "external_send_authority": False,
            "authority_created": False,
        }

    return adapter


def test_fulfilment_request_requires_canonical_eligible_settlement(tmp_path: Path) -> None:
    case = create_journey_case(tmp_path, product_id="Product Alpha")
    profile = _profile("Product Alpha")

    with pytest.raises(ValueError, match="fulfilment-eligible settlement truth is required"):
        build_fulfilment_request(tmp_path, case["case_id"], profile)


def test_request_binds_case_scope_quote_settlement_and_profile_without_authority(
    tmp_path: Path,
) -> None:
    case = _eligible_case(tmp_path)
    profile = _profile("Product Alpha")

    request = build_fulfilment_request(tmp_path, case["case_id"], profile)

    assert request["schema"] == "dio.fulfilment_request.v1"
    assert request["case_id"] == case["case_id"]
    assert request["journey_product_id"] == "Product Alpha"
    assert request["scope_receipt_sha256"] == case["scope_receipt"]["scope_receipt_sha256"]
    assert request["quote_truth_sha256"] == case["settlement"]["quote_truth_sha256"]
    assert request["settlement_receipt_sha256"] == case["settlement"]["settlement_receipt_sha256"]
    assert request["execution_profile_sha256"] == profile["execution_profile_sha256"]
    assert request["adapter_id"] == "adapter.shared"
    assert request["authority_created"] is False
    assert request["release_authority_created"] is False
    assert len(request["fulfilment_request_sha256"]) == 64
    assert load_case(tmp_path, case["case_id"])["stage"] == "WORK_QUEUED"


def test_same_adapter_serves_different_products_without_product_branching(tmp_path: Path) -> None:
    adapters = {"adapter.shared": _completed_adapter("shared")}

    for product_id in ("Product Alpha", "Product Beta"):
        root = tmp_path / product_id.replace(" ", "-").lower()
        case = _eligible_case(root, product_id=product_id)
        profile = _profile(product_id, adapter_id="adapter.shared")
        request = build_fulfilment_request(root, case["case_id"], profile)
        result = dispatch_fulfilment(root, request, adapters)

        assert result["journey_product_id"] == product_id
        assert result["adapter_id"] == "adapter.shared"
        assert result["status"] == "COMPLETED"


def test_composite_adapter_returns_one_canonical_result_envelope(tmp_path: Path) -> None:
    case = _eligible_case(tmp_path)
    profile = _profile("Product Alpha", adapter_id="adapter.composite")
    request = build_fulfilment_request(tmp_path, case["case_id"], profile)

    result = dispatch_fulfilment(
        tmp_path,
        request,
        {"adapter.composite": _completed_adapter("composite")},
    )

    assert result["schema"] == "dio.fulfilment_result.v1"
    assert result["fulfilment_request_sha256"] == request["fulfilment_request_sha256"]
    assert [step["organ"] for step in result["organ_steps"]] == ["evidex", "format_core"]
    assert len(result["artifacts"]) == 1
    assert result["artifacts"][0]["release_state"] == "HELD"
    assert result["release_authority_created"] is False
    assert result["external_send_authority"] is False
    assert result["authority_created"] is False
    assert len(result["fulfilment_result_sha256"]) == 64


def test_adapter_cannot_self_grant_release_or_send_authority(tmp_path: Path) -> None:
    case = _eligible_case(tmp_path)
    profile = _profile("Product Alpha", adapter_id="adapter.rogue")
    request = build_fulfilment_request(tmp_path, case["case_id"], profile)

    def rogue_adapter(request: dict, execution_profile: dict) -> dict:
        return {
            "status": "COMPLETED",
            "artifacts": [],
            "evidence_refs": [],
            "organ_steps": [],
            "release_authority": True,
            "external_send_authority": True,
            "authority_created": True,
        }

    with pytest.raises(ValueError, match="adapter may not create release, send, or generic authority"):
        dispatch_fulfilment(tmp_path, request, {"adapter.rogue": rogue_adapter})


def test_successful_dispatch_drives_strict_lifecycle_to_review_ready(tmp_path: Path) -> None:
    case = _eligible_case(tmp_path)
    profile = _profile("Product Alpha")
    request = build_fulfilment_request(tmp_path, case["case_id"], profile)

    result = dispatch_fulfilment(
        tmp_path,
        request,
        {"adapter.shared": _completed_adapter("final")},
    )
    stored = load_case(tmp_path, case["case_id"])

    assert stored["stage"] == "REVIEW_READY"
    assert stored["fulfilment"]["state"] == "review_ready"
    assert stored["fulfilment"]["result"]["fulfilment_result_sha256"] == result["fulfilment_result_sha256"]
    assert stored["fulfilment"]["release_authority"] is False
    assert stored["fulfilment"]["external_send_authority"] is False
    assert stored["authority_created"] is False


def test_scope_identity_accepts_phase2_machine_id_with_canonical_product_name(tmp_path: Path) -> None:
    case = create_journey_case(tmp_path, product_id="Document Studio Edit")
    open_intake(DIO_ROOT, tmp_path, case["case_id"])
    record_intake_inputs(
        DIO_ROOT,
        tmp_path,
        case["case_id"],
        {
            "requested_outcome": "Edit one controlled technical document",
            "buyer_class": "C0",
            "scope_quantity": 1,
        },
        evidence_ref="customer:phase4-real-scope",
    )
    scope = assess_scope(DIO_ROOT, tmp_path, case["case_id"])
    quote = prepare_quote(DIO_ROOT, tmp_path, case["case_id"])
    record_controlled_test_settlement(
        tmp_path,
        case["case_id"],
        receipt_id="PHASE4-IDENTITY",
        authorized_by="operator:test",
        reason="Cross-phase identity regression",
    )

    assert scope["product_id"] == "document_studio_edit"
    assert scope["product_name"] == "Document Studio Edit"
    assert quote["decision"] == "ALLOW_PRESENTATION"

    profile = _profile("Document Studio Edit")
    request = build_fulfilment_request(tmp_path, case["case_id"], profile)
    assert request["journey_product_id"] == "Document Studio Edit"
