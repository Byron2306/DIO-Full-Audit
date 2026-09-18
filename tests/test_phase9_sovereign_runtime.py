from __future__ import annotations

from pathlib import Path

import pytest

from adapters.document_studio import pipeline as document_studio
from adapters.sophia.review_pipeline import reviewer_commentary
from presence_core import llm
from presence_core.sovereign_runtime import (
    canonical_llm_provider,
    ollama_url_is_local,
    require_local_ollama_url,
    sovereign_runtime_status,
)
from scripts import sync_vesper_presence_edge as presence_edge


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "provider",
    [
        "huggingface",
        "hf",
        "gemini",
        "google",
        "nvidia_nim",
        "openai",
        "anthropic",
        "groq",
    ],
)
def test_phase9_refuses_remote_llm_providers(provider: str) -> None:
    with pytest.raises(ValueError, match="permits Ollama only"):
        canonical_llm_provider(provider)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:11434",
        "http://localhost:11434",
        "http://192.168.1.10:11434",
        "http://10.0.0.4:11434",
        "http://172.16.10.4:11434",
    ],
)
def test_phase9_accepts_local_ollama_endpoints(url: str) -> None:
    assert ollama_url_is_local(url)
    assert require_local_ollama_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "https://api.example.com/v1",
        "https://8.8.8.8:11434",
        "https://router.huggingface.co",
        "ftp://127.0.0.1:11434",
    ],
)
def test_phase9_refuses_public_or_non_http_ollama_endpoints(url: str) -> None:
    assert not ollama_url_is_local(url)
    with pytest.raises(ValueError, match="local network"):
        require_local_ollama_url(url)


def test_sovereign_runtime_status_has_no_cloud_fallback() -> None:
    status = sovereign_runtime_status(
        {
            "DIO_PRESENCE_LLM_PROVIDER": "ollama",
            "OLLAMA_URL": "http://127.0.0.1:11434",
        }
    )
    assert status["ready"] is True
    assert status["llm_provider"] == "ollama"
    assert status["cloud_llm_fallback_allowed"] is False
    assert status["huggingface_runtime_required"] is False
    assert status["cloudflare_runtime_required_for_s0"] is False
    assert status["canonical_asr_provider"] == "faster-whisper-local"


def test_presence_cloud_provider_selection_never_calls_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DIO_PRESENCE_LLM_PROVIDER", "huggingface")
    monkeypatch.setenv("DIO_PRESENCE_LLM_DRAFTS", "1")
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:0.5b")

    called = {"network": False}

    def forbidden_post(*args, **kwargs):
        called["network"] = True
        raise AssertionError("cloud provider selection must not call a network model")

    monkeypatch.setattr(llm.httpx, "post", forbidden_post)
    result = llm.draft_with_ollama(
        {"intent": "general_info"},
        "state=observed",
        "deterministic fallback",
    )
    assert result == "deterministic fallback"
    assert called["network"] is False


def test_document_studio_remote_provider_is_refused_before_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = {"subprocess": False}

    def forbidden_run(*args, **kwargs):
        called["subprocess"] = True
        raise AssertionError("remote provider refusal must happen before bridge execution")

    monkeypatch.setattr(document_studio.subprocess, "run", forbidden_run)
    with pytest.raises(ValueError, match="permits Ollama only"):
        document_studio.invoke_provider(
            {"provider": "nvidia_nim"},
            "system",
            "prompt",
        )
    assert called["subprocess"] is False


def test_sophia_remote_provider_is_refused_before_endpoint_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manuscript = tmp_path / "paper.txt"
    manuscript.write_text("A sufficiently long local manuscript paragraph. " * 20)

    called = {"endpoint": False}

    def forbidden_fetch(*args, **kwargs):
        called["endpoint"] = True
        raise AssertionError("remote provider refusal must happen before Sophia endpoint use")

    monkeypatch.setattr(
        "adapters.sophia.review_pipeline.fetch_json",
        forbidden_fetch,
    )
    result = reviewer_commentary(
        "http://127.0.0.1:7070",
        {
            "reasoned_review_approved": True,
            "reasoned_provider": "gemini",
        },
        "Test",
        manuscript,
        manuscript.read_text(),
        "plain_text",
        {
            "status": "clean_first_pass",
            "missing_from_reference_list": [],
            "reference_list_entries_not_cited": [],
            "actionable_issue_count": 0,
            "in_text_citations": [],
            "reference_entries": [],
        },
        [],
        [],
    )
    assert result["status"] == "provider_refused"
    assert result["source"] == "phase9_sovereign_runtime"
    assert result["remote_processing"] is False
    assert called["endpoint"] is False


def test_presence_voice_transcription_uses_local_asr_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local_result = {
        "schema": "dio.vesper.voice_transcription.v1",
        "text": "hello",
        "provider": "faster-whisper-local",
        "authority_created": False,
        "external_processing": False,
    }
    monkeypatch.setattr(
        presence_edge,
        "transcribe_voice_with_local_whisper",
        lambda attachment: dict(local_result),
    )

    def forbidden_hf(*args, **kwargs):
        raise AssertionError("HF ASR must not be called by canonical Phase 9 runtime")

    monkeypatch.setattr(
        presence_edge,
        "transcribe_voice_with_hf",
        forbidden_hf,
    )
    result = presence_edge.transcribe_voice({"content_b64": "AA=="})
    assert result["provider"] == "faster-whisper-local"
    assert result["external_processing"] is False
    assert result["phase9_sovereign_runtime"] is True
    assert result["cloud_fallback_allowed"] is False
