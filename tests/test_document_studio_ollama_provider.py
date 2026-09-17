from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from adapters.document_studio.pipeline import invoke_provider


def test_document_studio_ollama_provider_uses_local_bridge_without_release_authority() -> None:
    request = {
        "provider": "ollama",
        "ollama_model": "qwen2.5:0.5b",
        "ollama_url": "http://127.0.0.1:11434",
    }
    provider_payload = {
        "status": "ok",
        "provider": "ollama",
        "model": "qwen2.5:0.5b",
        "response": json.dumps({
            "document_summary": "summary",
            "edits": [],
            "translations": [],
            "glossary": [],
            "qa_flags": [],
        }),
        "authority_created": False,
        "release_authority": False,
        "external_send_authority": False,
    }

    class Completed:
        returncode = 0
        stdout = json.dumps(provider_payload)
        stderr = ""

    with patch("adapters.document_studio.pipeline.subprocess.run", return_value=Completed()) as run:
        result, provider = invoke_provider(request, "system", "prompt", max_predict=512)

    command = run.call_args.args[0]
    payload = json.loads(run.call_args.kwargs["input"])
    assert Path(command[1]).name == "document_studio_ollama_bridge.py"
    assert payload["model"] == "qwen2.5:0.5b"
    assert payload["base_url"] == "http://127.0.0.1:11434"
    assert provider["provider"] == "ollama"
    assert provider["authority_created"] is False
    assert result["document_summary"] == "summary"
