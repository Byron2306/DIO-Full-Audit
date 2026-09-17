from pathlib import Path
import hashlib

import scripts.serve_presence_bridge as bridge

from presence_core.customer_cases import (
    create_or_attach_case,
    load_case,
    update_case,
)
from presence_core.fulfilment_release import (
    create_release_authority,
)
from presence_core.needs_you import resolve_needs_you
from presence_core.state import create_needs_you


def test_bridge_completes_successful_product_fulfilment(
    tmp_path: Path,
):
    root = tmp_path / "state" / "presence"
    root.mkdir(parents=True)

    case = create_or_attach_case(
        root,
        conversation_id="CONV-BRIDGE-TEST",
        channel="telegram",
        external_user_id="TEST-USER",
        product_id="Sophia Integrity",
        contact_email=None,
    )

    case = update_case(
        root,
        case,
        stage="REVIEW_READY",
    )

    artifact_dir = (
        root
        / "customer_cases"
        / "artifacts"
        / case["case_id"]
    )
    artifact_dir.mkdir(parents=True)

    pdf = artifact_dir / "review.pdf"
    pdf.write_bytes(
        b"%PDF-1.4\nDIO BRIDGE DELIVERY TEST\n%%EOF\n"
    )

    sha = hashlib.sha256(
        pdf.read_bytes()
    ).hexdigest()

    item = create_needs_you(
        root,
        reason="fulfilment_release_review",
        conversation_id="CONV-BRIDGE-TEST",
        product="Sophia Integrity",
        summary=f"Approve exact artifact SHA-256 {sha}",
    )

    approval = resolve_needs_you(
        root,
        item["needs_you_id"],
        decision="APPROVE",
        resolved_by="human:test-operator",
        evidence_ref=f"sha256:{sha}",
    )

    authority = create_release_authority(
        root,
        case_id=case["case_id"],
        job_id="JOB-BRIDGE-TEST",
        needs_you_id=approval["needs_you_id"],
        artifact={
            "kind": "document",
            "path": str(pdf),
            "file_name": "review.pdf",
            "mime_type": "application/pdf",
            "sha256": sha,
            "release_state": "HELD",
        },
    )

    result = {
        "outbound_artifact": {
            "kind": "document",
            "purpose": "product_fulfilment",
            "path": str(pdf),
            "file_name": "review.pdf",
            "mime_type": "application/pdf",
            "sha256": sha,
            "release_state": "APPROVED",
            "release_authority_id": authority[
                "authority_id"
            ],
        }
    }

    reply_receipt = {
        "delivery_mode": "document",
        "external_action_type": (
            "telegram_document_reply"
        ),
        "document": {
            "purpose": "product_fulfilment",
            "file_name": "review.pdf",
            "mime_type": "application/pdf",
            "sha256": sha,
            "telegram_message_id": 91,
            "telegram_file_id": "TG-FILE-91",
            "release_state": "APPROVED",
        },
    }

    finalize = getattr(
        bridge,
        "finalize_fulfilment_delivery",
        None,
    )

    assert callable(finalize), (
        "finalize_fulfilment_delivery "
        "is not implemented"
    )

    completion = finalize(
        root,
        result=result,
        sent=True,
        reply_receipt=reply_receipt,
    )

    assert completion is not None
    assert completion["case"]["stage"] == "DELIVERED"
    assert completion["authority"]["consumed"] is True

    stored = load_case(
        root,
        case["case_id"],
    )

    assert stored is not None
    assert stored["stage"] == "DELIVERED"
    assert (
        stored["fulfilment"]
        ["delivery_receipt"]
        ["message_id"]
        == 91
    )


def test_bridge_does_not_complete_failed_product_fulfilment(
    tmp_path: Path,
):
    root = tmp_path / "state" / "presence"
    root.mkdir(parents=True)

    case = create_or_attach_case(
        root,
        conversation_id="CONV-BRIDGE-FAIL",
        channel="telegram",
        external_user_id="TEST-USER",
        product_id="Sophia Integrity",
        contact_email=None,
    )

    case = update_case(
        root,
        case,
        stage="REVIEW_READY",
    )

    artifact_dir = (
        root
        / "customer_cases"
        / "artifacts"
        / case["case_id"]
    )
    artifact_dir.mkdir(parents=True)

    pdf = artifact_dir / "review.pdf"
    pdf.write_bytes(
        b"%PDF-1.4\nDIO BRIDGE FAILED DELIVERY TEST\n%%EOF\n"
    )

    sha = hashlib.sha256(
        pdf.read_bytes()
    ).hexdigest()

    item = create_needs_you(
        root,
        reason="fulfilment_release_review",
        conversation_id="CONV-BRIDGE-FAIL",
        product="Sophia Integrity",
        summary=f"Approve exact artifact SHA-256 {sha}",
    )

    approval = resolve_needs_you(
        root,
        item["needs_you_id"],
        decision="APPROVE",
        resolved_by="human:test-operator",
        evidence_ref=f"sha256:{sha}",
    )

    authority = create_release_authority(
        root,
        case_id=case["case_id"],
        job_id="JOB-BRIDGE-FAIL",
        needs_you_id=approval["needs_you_id"],
        artifact={
            "kind": "document",
            "path": str(pdf),
            "file_name": "review.pdf",
            "mime_type": "application/pdf",
            "sha256": sha,
            "release_state": "HELD",
        },
    )

    result = {
        "outbound_artifact": {
            "kind": "document",
            "purpose": "product_fulfilment",
            "path": str(pdf),
            "file_name": "review.pdf",
            "mime_type": "application/pdf",
            "sha256": sha,
            "release_state": "APPROVED",
            "release_authority_id": authority[
                "authority_id"
            ],
        }
    }

    completion = bridge.finalize_fulfilment_delivery(
        root,
        result=result,
        sent=False,
        reply_receipt={
            "delivery_mode": "document",
            "document": {
                "sha256": sha,
            },
        },
    )

    assert completion is None

    stored = load_case(
        root,
        case["case_id"],
    )

    assert stored is not None
    assert stored["stage"] == "RELEASE_APPROVAL"

    authority_path = (
        root
        / "customer_cases"
        / "release_authorities"
        / f"{authority['authority_id']}.json"
    )

    import json

    stored_authority = json.loads(
        authority_path.read_text(
            encoding="utf-8",
        )
    )

    assert stored_authority["consumed"] is False


def test_bridge_orchestrates_send_bind_and_finalize(
    monkeypatch,
):
    envelope = {
        "channel": "telegram",
    }

    result = {
        "outbound_artifact": {
            "purpose": "product_fulfilment",
            "release_authority_id": "FRA-TEST",
            "sha256": "a" * 64,
        }
    }

    receipt = {
        "delivery_mode": "document",
        "document": {
            "sha256": "a" * 64,
        },
    }

    calls = []

    def fake_send(envelope_arg, result_arg):
        calls.append("send")
        assert envelope_arg is envelope
        assert result_arg is result
        return True, None, receipt

    def fake_bind(result_arg, receipt_arg, *, sent, error=None):
        calls.append("bind")
        assert result_arg is result
        assert receipt_arg is receipt
        assert sent is True
        assert error is None
        return result_arg

    def fake_finalize(
        state_root,
        *,
        result,
        sent,
        reply_receipt,
    ):
        calls.append("finalize")
        assert sent is True
        assert reply_receipt is receipt
        return {"ok": True}

    monkeypatch.setattr(
        bridge,
        "send_telegram_reply_from_core",
        fake_send,
    )
    monkeypatch.setattr(
        bridge,
        "bind_external_action_receipt",
        fake_bind,
    )
    monkeypatch.setattr(
        bridge,
        "finalize_fulfilment_delivery",
        fake_finalize,
    )

    orchestrate = getattr(
        bridge,
        "send_bind_and_finalize",
        None,
    )

    assert callable(orchestrate), (
        "send_bind_and_finalize is not implemented"
    )

    sent, error, reply_receipt = orchestrate(
        envelope,
        result,
        state_root=Path("/tmp/dio-test-state"),
    )

    assert sent is True
    assert error is None
    assert reply_receipt is receipt
    assert calls == [
        "send",
        "bind",
        "finalize",
    ]


def test_live_ingress_uses_send_bind_finalize(
    monkeypatch,
):
    from fastapi.testclient import TestClient

    bridge.REPLAY.clear()

    monkeypatch.setattr(
        bridge,
        "verify_body",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setitem(
        bridge.CFG,
        "state_root",
        "state/presence",
    )

    monkeypatch.setenv(
        "DIO_PRESENCE_PUBLIC_SHARED_SECRET",
        "test-secret",
    )

    result = {
        "decision": {
            "intent": "general_info",
        },
        "reply": {
            "text": "Delivery ready.",
        },
    }

    monkeypatch.setattr(
        bridge,
        "process_envelope",
        lambda envelope, root, cfg: result,
    )

    calls = []

    def fake_orchestrate(
        envelope,
        result_arg,
        *,
        state_root,
    ):
        calls.append(
            {
                "envelope": envelope,
                "result": result_arg,
                "state_root": state_root,
            }
        )
        return True, None, {
            "delivery_mode": "document",
        }

    monkeypatch.setattr(
        bridge,
        "send_bind_and_finalize",
        fake_orchestrate,
    )

    def old_path_forbidden(*args, **kwargs):
        raise AssertionError(
            "ingress must use send_bind_and_finalize"
        )

    monkeypatch.setattr(
        bridge,
        "send_telegram_reply_from_core",
        old_path_forbidden,
    )

    client = TestClient(bridge.app)

    response = client.post(
        "/api/presence/ingress",
        json={
            "channel": "telegram",
            "external_user_id": "TEST-USER",
            "text": "test",
        },
        headers={
            "x-dio-presence-signature": "test",
            "x-dio-presence-timestamp": "1",
            "x-dio-presence-nonce": "NONCE-BRIDGE-TEST",
            "x-dio-presence-key-id": "public-edge",
        },
    )

    assert response.status_code == 200
    assert len(calls) == 1
    assert calls[0]["result"] is result


def test_successful_send_survives_completion_reconciliation_failure(
    monkeypatch,
):
    envelope = {
        "channel": "telegram",
    }

    result = {
        "outbound_artifact": {
            "purpose": "product_fulfilment",
            "release_authority_id": "FRA-TEST",
            "sha256": "a" * 64,
        }
    }

    receipt = {
        "delivery_mode": "document",
        "document": {
            "sha256": "a" * 64,
            "telegram_message_id": 91,
        },
    }

    calls = []

    def fake_send(envelope_arg, result_arg):
        calls.append("send")
        return True, None, receipt

    def fake_bind(result_arg, receipt_arg, *, sent, error=None):
        calls.append("bind")
        assert sent is True
        assert error is None
        return result_arg

    def broken_finalize(*args, **kwargs):
        calls.append("finalize")
        raise RuntimeError(
            "simulated post-send reconciliation failure"
        )

    monkeypatch.setattr(
        bridge,
        "send_telegram_reply_from_core",
        fake_send,
    )
    monkeypatch.setattr(
        bridge,
        "bind_external_action_receipt",
        fake_bind,
    )
    monkeypatch.setattr(
        bridge,
        "finalize_fulfilment_delivery",
        broken_finalize,
    )

    sent, error, reply_receipt = (
        bridge.send_bind_and_finalize(
            envelope,
            result,
            state_root=Path("/tmp/dio-test-state"),
        )
    )

    assert sent is True
    assert error is None
    assert reply_receipt is receipt

    assert (
        result["fulfilment_completion_state"]
        == "post_send_reconciliation_failed"
    )

    assert (
        "simulated post-send reconciliation failure"
        in result["fulfilment_completion_error"]
    )

    assert calls == [
        "send",
        "bind",
        "finalize",
    ]
