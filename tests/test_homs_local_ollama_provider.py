import asyncio
import json
import os
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from scripts.run_homs_hymark_batch import (
    DEFAULT_HYMARK_BACKEND,
    assessment_response_is_complete,
    configure_provider,
    load_hymark_backend,
    run_batch,
)
from scripts.run_homs_live_batch import load_provider_env


def test_homs_uses_global_ollama_model_without_provider_secret(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "granite3.2:2b")
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:11434")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("HOMS_AI_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("HOMS_AI_MAX_RETRIES", raising=False)
    monkeypatch.delenv("HOMS_AI_MAX_TOKENS", raising=False)

    provider = configure_provider(Path("/missing/provider-secrets.env"), "ollama", "")

    assert provider["selected_provider"] == "ollama"
    assert provider["selected_model"] == "granite3.2:2b"
    assert provider["base_url"] == "http://127.0.0.1:11434/v1"
    assert provider["selected_key_name"] == ""
    assert os.environ["HOMS_AI_TIMEOUT_SECONDS"] == "360"
    assert os.environ["HOMS_AI_MAX_RETRIES"] == "0"
    assert os.environ["HOMS_AI_MAX_TOKENS"] == "512"
    assert run_batch.__defaults__[-2:] == ("ollama", "")


def test_homs_rejects_provider_error_fallback_as_incomplete():
    rubric = {
        "total_marks": 2,
        "criteria": [
            {"name": "Criterion A", "weight": 1},
            {"name": "Criterion B", "weight": 1},
        ],
    }
    fallback = {
        "error": "Request timed out.",
        "criteria_scores": {},
        "overall_feedback": "Assessment failed due to an error.",
    }
    valid = {
        "criteria_scores": {
            "Criterion A": {"score": 1, "feedback": "Correct use of evidence."},
            "Criterion B": {"score": 0, "feedback": "Explain the missing step."},
        },
        "overall_feedback": "Review the second criterion before finalising.",
    }

    assert not assessment_response_is_complete(fallback, rubric)
    assert assessment_response_is_complete(valid, rubric)


def test_hymark_prompt_is_subject_neutral_and_rubric_driven():
    hymark = load_hymark_backend(DEFAULT_HYMARK_BACKEND)
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=json.dumps(
                        {
                            "total_score": 1,
                            "criteria_scores": {
                                "Criterion A": {
                                    "score": 1,
                                    "feedback": "The method is supported by the work.",
                                }
                            },
                            "overall_feedback": "Review the result.",
                            "annotations": [],
                        }
                    )
                )
            )
        ]
    )

    with patch.object(
        hymark.openai_client.chat.completions,
        "create",
        return_value=response,
    ) as create:
        result = asyncio.run(
            hymark.assess_with_ai(
                "A short learner response.",
                {
                    "total_marks": 1,
                    "criteria": [{"name": "Criterion A", "weight": 1}],
                },
            )
        )

    prompts = "\n".join(message["content"] for message in create.call_args.kwargs["messages"])
    assert "HISTORY EDUCATION" not in prompts
    assert "Criterion A" in prompts
    assert result["total_score"] == 1


def test_homs_live_batch_uses_global_ollama_model_without_provider_secret(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "granite3.2:2b")
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:11434")
    monkeypatch.delenv("HOMS_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)

    provider = load_provider_env(Path("/missing/provider-secrets.env"), "ollama")

    assert provider["selected_provider"] == "ollama"
    assert provider["selected_model"] == "granite3.2:2b"
    assert provider["base_url"] == "http://127.0.0.1:11434/v1"
