from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from adapters.document_studio.pipeline import invoke_provider
from scripts.document_studio_ollama_bridge import normalise_provider_result


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


def test_ollama_normalizer_quarantines_missing_ids_and_dropped_protected_facts() -> None:
    prompt = """Service: technical_edit
Protected tokens: ["2", "8"]
SOURCE PARAGRAPHS:
[{"paragraph_id":"P1","text":"Field Sampling Procedure"},{"paragraph_id":"P2","text":"The bottle must remain between 2 and 8 degrees Celsius during transport."}]
"""
    result = {
        "document_summary": "summary",
        "edits": [
            {
                "paragraph_id": "P2",
                "revised": "The bottle must remain cool during transport.",
                "category": "clarity",
                "rationale": "shorter",
                "confidence": "high"
            }
        ],
        "translations": [],
        "glossary": [],
        "qa_flags": [],
    }
    normalized = normalise_provider_result(prompt, result)
    assert [row["paragraph_id"] for row in normalized["edits"]] == ["P1", "P2"]
    assert normalized["edits"][0]["revised"] == "Field Sampling Procedure"
    assert normalized["edits"][1]["revised"] == "The bottle must remain between 2 and 8 degrees Celsius during transport."
    assert all(row["category"] == "no_change" for row in normalized["edits"])
    assert len(normalized["qa_flags"]) == 2
    assert normalized["ollama_normalization"]["authority_created"] is False


def test_ollama_normalizer_retains_safe_exact_id_edit() -> None:
    prompt = """Service: technical_edit
Protected tokens: ["2", "8"]
SOURCE PARAGRAPHS:
[{"paragraph_id":"P1","text":"The technician record the sample code. The bottle stays between 2 and 8 degrees."}]
"""
    result = {
        "edits": [{
            "paragraph_id": "P1",
            "revised": "The technician records the sample code. The bottle stays between 2 and 8 degrees.",
            "category": "grammar",
            "rationale": "subject-verb agreement",
            "confidence": "high"
        }],
        "qa_flags": [],
    }
    normalized = normalise_provider_result(prompt, result)
    assert normalized["edits"][0]["revised"].startswith("The technician records")
    assert normalized["edits"][0]["category"] == "grammar"
    assert normalized["qa_flags"] == []
    assert normalized["ollama_normalization"]["paragraphs"][0]["action"] == "provider_edit_retained"
