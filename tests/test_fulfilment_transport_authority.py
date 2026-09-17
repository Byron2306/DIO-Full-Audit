from pathlib import Path
import hashlib

from presence_core.telegram_transport import send_telegram_reply


def _envelope():
    return {
        "channel": "telegram",
        "external_user_id": "TEST-USER",
        "text": "test",
        "metadata": {
            "telegram_bot_surface": "public",
            "telegram_chat_id": "456",
        },
    }


def _result(pdf: Path, sha: str):
    return {
        "decision": {
            "intent": "general_info",
        },
        "authority": {
            "spend_authorized": False,
            "fulfilment_released": False,
            "attachment_processed": False,
        },
        "reply": {
            "text": "Your completed review is ready.",
            "voice_eligible": False,
        },
        "outbound_artifact": {
            "kind": "document",
            "purpose": "product_fulfilment",
            "path": str(pdf),
            "file_name": "review.pdf",
            "mime_type": "application/pdf",
            "sha256": sha,
            "release_state": "APPROVED",
        },
    }


def test_product_fulfilment_requires_release_authority(
    tmp_path,
    monkeypatch,
):
    root = tmp_path

    state_root = (
        root
        / "state"
        / "presence"
    )

    artifact_dir = (
        state_root
        / "customer_cases"
        / "artifacts"
        / "CASE-TEST"
    )
    artifact_dir.mkdir(parents=True)

    pdf = artifact_dir / "review.pdf"
    pdf.write_bytes(
        b"%PDF-1.4\nDIO FULFILMENT AUTHORITY TEST\n%%EOF\n"
    )

    sha = hashlib.sha256(
        pdf.read_bytes()
    ).hexdigest()

    monkeypatch.setenv(
        "DIO_PRESENCE_CORE_TELEGRAM_REPLIES",
        "1",
    )
    monkeypatch.setenv(
        "DIO_TELEGRAM_PUBLIC_BOT_TOKEN",
        "test-token",
    )

    def forbidden_post(*args, **kwargs):
        raise AssertionError(
            "network send must not occur without "
            "release authority"
        )

    monkeypatch.setattr(
        "presence_core.telegram_transport.httpx.post",
        forbidden_post,
    )

    sent, error, receipt = send_telegram_reply(
        _envelope(),
        _result(pdf, sha),
        root=root,
        state_root=state_root,
    )

    assert sent is False
    assert error == (
        "fulfilment_release_authority_missing"
    )
    assert receipt["authorized"] is False
    assert (
        "fulfilment_release_authority_missing"
        in receipt["reasons"]
    )


def test_product_fulfilment_with_valid_release_authority_sends(
    tmp_path,
    monkeypatch,
):
    import json

    root = tmp_path
    state_root = root / "state" / "presence"

    artifact_dir = (
        state_root
        / "customer_cases"
        / "artifacts"
        / "CASE-TEST"
    )
    artifact_dir.mkdir(parents=True)

    pdf = artifact_dir / "review.pdf"
    pdf.write_bytes(
        b"%PDF-1.4\nDIO VALID FULFILMENT AUTHORITY TEST\n%%EOF\n"
    )

    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()

    authority_id = "FRA-VALID-TEST"

    authority_dir = (
        state_root
        / "customer_cases"
        / "release_authorities"
    )
    authority_dir.mkdir(parents=True)

    authority = {
        "schema": "dio.fulfilment_release_authority.v1",
        "authority_id": authority_id,
        "case_id": "CASE-TEST",
        "product_id": "Sophia Integrity",
        "job_id": "JOB-TEST",
        "artifact": {
            "kind": "document",
            "path": str(pdf.resolve()),
            "file_name": "review.pdf",
            "mime_type": "application/pdf",
            "sha256": sha,
            "bytes": pdf.stat().st_size,
        },
        "authority_created": True,
        "fulfilment_release_authorized": True,
        "external_send_authorized": True,
        "consumed": False,
    }

    (
        authority_dir
        / f"{authority_id}.json"
    ).write_text(
        json.dumps(authority, indent=2) + "\n",
        encoding="utf-8",
    )

    result = _result(pdf, sha)
    result["outbound_artifact"][
        "release_authority_id"
    ] = authority_id

    monkeypatch.setenv(
        "DIO_PRESENCE_CORE_TELEGRAM_REPLIES",
        "1",
    )
    monkeypatch.setenv(
        "DIO_TELEGRAM_PUBLIC_BOT_TOKEN",
        "test-token",
    )

    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "ok": True,
                "result": {
                    "message_id": 91,
                    "document": {
                        "file_id": "TG-FILE-91",
                    },
                },
            }

    def fake_post(
        url,
        *,
        data=None,
        files=None,
        json=None,
        timeout=None,
    ):
        calls.append(url)
        return Response()

    monkeypatch.setattr(
        "presence_core.telegram_transport.httpx.post",
        fake_post,
    )

    sent, error, receipt = send_telegram_reply(
        _envelope(),
        result,
        root=root,
        state_root=state_root,
    )

    assert sent is True
    assert error is None
    assert len(calls) == 1
    assert receipt["delivery_mode"] == "document"
    assert receipt["document"]["sha256"] == sha
    assert (
        receipt["document"]["telegram_message_id"]
        == 91
    )
