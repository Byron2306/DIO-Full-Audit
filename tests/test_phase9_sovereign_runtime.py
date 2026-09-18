from __future__ import annotations

import base64
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from adapters.document_studio.pipeline import invoke_provider
from adapters.sophia.review_pipeline import reviewer_commentary
from commerce.paypal_local import (
    LocalCommerceStore,
    reconcile_local_paypal_order,
)
from presence_core.local_ingress import LocalIngressLedger
from scripts import poll_vesper_telegram as telegram_poll
from scripts.poll_vesper_telegram import TelegramPollError, update_to_envelope
from sovereign_runtime import (
    SovereignRuntimeError,
    llm_policy,
    require_ollama_provider,
)


def test_sovereign_policy_allows_only_ollama() -> None:
    assert require_ollama_provider("ollama", component="test") == "ollama"
    assert require_ollama_provider("local_ollama", component="test") == "ollama"
    assert require_ollama_provider("local", component="test") == "ollama"
    for provider in ("hf", "huggingface", "auto", "gemini", "nvidia_nim", "openai", "anthropic"):
        with pytest.raises(SovereignRuntimeError):
            require_ollama_provider(provider, component="test")

    policy = llm_policy(model="qwen2.5:0.5b", base_url="http://127.0.0.1:11434")
    assert policy.provider == "ollama"
    assert policy.cloud_fallback_allowed is False
    assert policy.hf_runtime_allowed is False


def test_document_studio_defaults_to_ollama_and_refuses_cloud_provider() -> None:
    provider_payload = {
        "status": "ok",
        "provider": "ollama",
        "model": "qwen2.5:0.5b",
        "response": json.dumps(
            {
                "document_summary": "summary",
                "edits": [],
                "translations": [],
                "glossary": [],
                "qa_flags": [],
            }
        ),
        "authority_created": False,
        "release_authority": False,
        "external_send_authority": False,
    }

    class Completed:
        returncode = 0
        stdout = json.dumps(provider_payload)
        stderr = ""

    with patch(
        "adapters.document_studio.pipeline.subprocess.run",
        return_value=Completed(),
    ) as run:
        _, provider = invoke_provider({}, "system", "prompt", max_predict=32)

    payload = json.loads(run.call_args.kwargs["input"])
    assert payload["base_url"] == "http://127.0.0.1:11434"
    assert provider["provider"] == "ollama"

    for forbidden in ("gemini", "nvidia_nim", "hf", "openai"):
        with pytest.raises(SovereignRuntimeError):
            invoke_provider(
                {"provider": forbidden},
                "system",
                "prompt",
                max_predict=32,
            )


def test_local_ingress_ledger_replays_same_event_without_reprocessing(tmp_path: Path) -> None:
    ledger = LocalIngressLedger(tmp_path / "ingress.sqlite")
    body = b'{"channel":"telegram","text":"hello"}'
    assert ledger.cached_response("telegram:operator:10", body) is None
    ledger.begin("telegram:operator:10", body)
    assert ledger.cached_response("telegram:operator:10", body) is None
    response = {"schema": "dio.presence_response.v2", "reply": {"text": "hi"}}
    ledger.complete("telegram:operator:10", body, response)
    assert ledger.cached_response("telegram:operator:10", body) == response

    with pytest.raises(ValueError):
        ledger.cached_response("telegram:operator:10", body + b"x")


def test_telegram_long_poll_update_becomes_signed_core_envelope_without_cloudflare() -> None:
    update = {
        "update_id": 12345,
        "message": {
            "message_id": 77,
            "from": {"id": 2306, "first_name": "Byron"},
            "chat": {"id": 2306},
            "text": "/start MKT-HOMS-42",
        },
    }
    envelope = update_to_envelope(
        update,
        token="unused-for-text",
        surface="operator",
        poll_sha256="a" * 64,
    )
    assert envelope is not None
    assert envelope["channel"] == "telegram"
    assert envelope["external_user_id"] == "2306"
    assert envelope["metadata"]["telegram_chat_id"] == "2306"
    assert envelope["metadata"]["telegram_bot_surface"] == "operator"
    assert envelope["metadata"]["telegram_start_payload"] == "MKT-HOMS-42"
    assert envelope["metadata"]["provider_event_key"] == "telegram:operator:12345"
    assert envelope["metadata"]["sovereign_local_ingress"] is True


def test_telegram_long_poll_document_preserves_exact_downloaded_bytes() -> None:
    payload = b"%PDF-1.7\nphase9\n"
    update = {
        "update_id": 900,
        "message": {
            "message_id": 12,
            "from": {"id": 99, "first_name": "A"},
            "chat": {"id": 99},
            "caption": "Please review this",
            "document": {
                "file_id": "FILE-1",
                "file_name": "paper.pdf",
                "mime_type": "application/pdf",
            },
        },
    }
    with patch("scripts.poll_vesper_telegram._download_file", return_value=payload):
        envelope = update_to_envelope(
            update,
            token="token",
            surface="public",
            poll_sha256="b" * 64,
        )
    assert envelope is not None
    attachment = envelope["attachment"]
    assert attachment["file_name"] == "paper.pdf"
    assert base64.b64decode(attachment["content_b64"]) == payload
    assert attachment["file_size"] == len(payload)
    assert envelope["metadata"]["telegram_bot_surface"] == "public"


def test_sophia_refuses_remote_reasoned_provider_before_network(tmp_path: Path) -> None:
    manuscript = tmp_path / "paper.md"
    manuscript.write_text("Controlled manuscript.", encoding="utf-8")
    result = reviewer_commentary(
        "http://127.0.0.1:7070",
        {
            "reasoned_review_approved": True,
            "reasoned_provider": "gemini",
        },
        "Controlled paper",
        manuscript,
        "Controlled manuscript.",
        "plain_text",
        {
            "status": "clean_first_pass",
            "missing_from_reference_list": [],
            "reference_list_entries_not_cited": [],
            "actionable_issue_count": 0,
            "reference_entries": [],
            "in_text_citations": [],
        },
        [],
        [],
    )
    assert result["status"] == "rejected"
    assert result["source"] == "sovereign_runtime"
    assert result["remote_processing"] is False
    assert "only Ollama" in result["commentary"]


def test_telegram_poller_refuses_hidden_webhook_without_explicit_cutover(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DIO_TELEGRAM_OPERATOR_BOT_TOKEN", "token")
    monkeypatch.setenv("DIO_PRESENCE_OPERATOR_SHARED_SECRET", "s" * 40)
    poller = telegram_poll.TelegramLongPoller(
        surface="operator",
        state_root=tmp_path,
        core_url="http://127.0.0.1:8787",
    )
    with patch(
        "scripts.poll_vesper_telegram._api_raw",
        return_value=(
            {"ok": True, "result": {"url": "https://legacy.example/webhook"}},
            b"{}",
        ),
    ):
        with pytest.raises(TelegramPollError, match="--drop-webhook"):
            poller.ensure_polling_mode(remove_webhook=False)


def test_telegram_poller_explicit_cutover_preserves_pending_updates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DIO_TELEGRAM_OPERATOR_BOT_TOKEN", "token")
    monkeypatch.setenv("DIO_PRESENCE_OPERATOR_SHARED_SECRET", "s" * 40)
    poller = telegram_poll.TelegramLongPoller(
        surface="operator",
        state_root=tmp_path,
        core_url="http://127.0.0.1:8787",
    )
    calls = []

    def fake_api(token, method, params=None, timeout=45.0):
        calls.append((method, dict(params or {})))
        if method == "getWebhookInfo":
            return {"ok": True, "result": {"url": "https://legacy.example/webhook"}}, b"{}"
        if method == "deleteWebhook":
            return {"ok": True, "result": True}, b"{}"
        raise AssertionError(method)

    with patch("scripts.poll_vesper_telegram._api_raw", side_effect=fake_api):
        result = poller.ensure_polling_mode(remove_webhook=True)

    assert result["webhook_removed"] is True
    assert result["pending_updates_preserved"] is True
    assert result["cloudflare_required"] is False
    assert ("deleteWebhook", {"drop_pending_updates": "false"}) in calls


class _FakePayPalClient:
    def __init__(self, provider_order: dict, capture: dict | None = None):
        self.provider_order = provider_order
        self.capture = capture
        self.capture_calls = 0

    def get_order(self, provider_order_id: str) -> dict:
        assert provider_order_id == self.provider_order["id"]
        return self.provider_order

    def capture_order(self, provider_order_id: str) -> dict:
        self.capture_calls += 1
        return self.provider_order

    def get_capture(self, capture_id: str) -> dict:
        assert self.capture is not None
        assert capture_id == self.capture["id"]
        return self.capture


def _paypal_order(
    *,
    status: str,
    capture: dict | None = None,
) -> dict:
    unit = {
        "invoice_id": "ORDER-PHASE9-001",
        "custom_id": "ORDER-PHASE9-001",
        "amount": {
            "currency_code": "USD",
            "value": "10.00",
        },
    }
    if capture is not None:
        unit["payments"] = {"captures": [capture]}
    return {
        "id": "PAYPAL-ORDER-1",
        "status": status,
        "purchase_units": [unit],
    }


def test_paypal_approved_order_is_not_captured_without_explicit_authority(
    tmp_path: Path,
) -> None:
    store = LocalCommerceStore(
        tmp_path / "orders",
        tmp_path / "receipts",
    )
    order = store.register(
        order_id="ORDER-PHASE9-001",
        product_code="EVIDEX",
        amount_minor=1000,
        currency="USD",
    )
    order["provider_order_id"] = "PAYPAL-ORDER-1"
    order["payment_state"] = "awaiting_payment"
    store.save(order)

    client = _FakePayPalClient(
        _paypal_order(status="APPROVED")
    )
    result = reconcile_local_paypal_order(
        store,
        client,
        "ORDER-PHASE9-001",
        capture_approved=False,
    )

    assert client.capture_calls == 0
    assert result["payment_state"] == "approved_awaiting_capture"
    assert result["external_funds_moved"] is False
    assert result["browser_return_authority"] is False
    assert result["cloudflare_used"] is False
    assert result["webhook_required"] is False


def test_paypal_completed_capture_becomes_verified_local_payment_truth(
    tmp_path: Path,
) -> None:
    store = LocalCommerceStore(
        tmp_path / "orders",
        tmp_path / "receipts",
    )
    order = store.register(
        order_id="ORDER-PHASE9-001",
        product_code="EVIDEX",
        amount_minor=1000,
        currency="USD",
    )
    order["provider_order_id"] = "PAYPAL-ORDER-1"
    order["payment_state"] = "awaiting_payment"
    store.save(order)

    capture_summary = {
        "id": "CAPTURE-1",
        "status": "COMPLETED",
    }
    capture_detail = {
        "id": "CAPTURE-1",
        "status": "COMPLETED",
        "amount": {
            "currency_code": "USD",
            "value": "10.00",
        },
    }
    client = _FakePayPalClient(
        _paypal_order(
            status="COMPLETED",
            capture=capture_summary,
        ),
        capture_detail,
    )

    result = reconcile_local_paypal_order(
        store,
        client,
        "ORDER-PHASE9-001",
        capture_approved=False,
    )

    assert result["payment_state"] == "paid"
    assert result["external_funds_moved"] is True
    assert result["fulfilment_released"] is False
    assert len(result["payment_receipt_sha256"]) == 64
    assert (
        tmp_path
        / "receipts"
        / f"{result['payment_receipt_sha256']}.json"
    ).is_file()
