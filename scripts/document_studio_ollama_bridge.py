#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from typing import Any


def _prompt_json(prompt: str, prefix: str) -> Any:
    for line in prompt.splitlines():
        if line.startswith(prefix):
            raw = line[len(prefix):].strip()
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return None
    return None


def _source_paragraphs(prompt: str) -> list[dict[str, str]]:
    marker = "SOURCE PARAGRAPHS:"
    if marker not in prompt:
        return []
    raw = prompt.split(marker, 1)[1].strip()
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(rows, list):
        return []
    result: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        paragraph_id = str(row.get("paragraph_id") or "").strip()
        text = str(row.get("text") or "")
        if paragraph_id and text:
            result.append({"paragraph_id": paragraph_id, "text": text})
    return result


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\b\d+(?:\.\d+)?\b", text))


def normalise_provider_result(prompt: str, result: dict[str, Any]) -> dict[str, Any]:
    """Conservatively repair weak local-model technical-edit output.

    The normaliser never invents replacement facts. Exact-ID edits are retained only
    when they preserve all source numbers and protected tokens. Missing, duplicated,
    misidentified, or fact-dropping edits are quarantined by replacing that paragraph
    with the exact source text and emitting a high-severity QA flag. The downstream
    Document Studio validator remains authoritative and unchanged.
    """

    service = ""
    for line in prompt.splitlines():
        if line.startswith("Service:"):
            service = line.split(":", 1)[1].strip()
            break
    if service != "technical_edit":
        return result

    paragraphs = _source_paragraphs(prompt)
    if not paragraphs:
        return result

    protected_raw = _prompt_json(prompt, "Protected tokens:")
    protected = [str(item) for item in protected_raw] if isinstance(protected_raw, list) else []

    rows = result.get("edits")
    rows = rows if isinstance(rows, list) else []
    by_id: dict[str, dict[str, Any]] = {}
    duplicate_ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        paragraph_id = str(row.get("paragraph_id") or "").strip()
        if not paragraph_id:
            continue
        if paragraph_id in by_id:
            duplicate_ids.add(paragraph_id)
            continue
        by_id[paragraph_id] = row

    qa_flags = list(result.get("qa_flags") or []) if isinstance(result.get("qa_flags"), list) else []
    repaired: list[dict[str, Any]] = []
    normalised: list[dict[str, Any]] = []

    for source in paragraphs:
        paragraph_id = source["paragraph_id"]
        source_text = source["text"]
        candidate = by_id.get(paragraph_id)
        reasons: list[str] = []

        if candidate is None:
            reasons.append("missing_or_misidentified_edit")
        elif paragraph_id in duplicate_ids:
            reasons.append("duplicate_edit_id")
        else:
            revised = str(candidate.get("revised") or "").strip()
            if not revised:
                reasons.append("empty_revised_text")
            missing_numbers = sorted(_numbers(source_text) - _numbers(revised))
            if missing_numbers:
                reasons.append("dropped_numbers:" + ",".join(missing_numbers))
            missing_tokens = [token for token in protected if token in source_text and token not in revised]
            if missing_tokens:
                reasons.append("dropped_protected_tokens:" + ",".join(missing_tokens))

        if reasons:
            repaired.append({
                "paragraph_id": paragraph_id,
                "revised": source_text,
                "category": "no_change",
                "rationale": "Local provider edit quarantined; exact source retained because deterministic safety checks failed.",
                "confidence": "low",
            })
            qa_flags.append({
                "paragraph_id": paragraph_id,
                "severity": "high",
                "issue": "Ollama edit quarantined: " + "; ".join(reasons),
            })
            normalised.append({"paragraph_id": paragraph_id, "action": "source_fallback", "reasons": reasons})
        else:
            kept = dict(candidate)
            kept["paragraph_id"] = paragraph_id
            kept["revised"] = str(kept["revised"]).strip()
            repaired.append(kept)
            normalised.append({"paragraph_id": paragraph_id, "action": "provider_edit_retained", "reasons": []})

    result = dict(result)
    result["edits"] = repaired
    result["qa_flags"] = qa_flags
    result["ollama_normalization"] = {
        "schema": "dio.document_studio.ollama_normalization.v1",
        "mode": "conservative_fact_preserving",
        "paragraphs": normalised,
        "authority_created": False,
        "release_authority": False,
        "external_send_authority": False,
    }
    return result


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    base_url = str(payload.get("base_url") or "http://127.0.0.1:11434").rstrip("/")
    model = str(payload.get("model") or "qwen2.5:0.5b")
    prompt = str(payload.get("prompt") or "")
    request_body = {
        "model": model,
        "prompt": prompt,
        "system": str(payload.get("system_prompt") or ""),
        "stream": False,
        "format": "json",
        "options": {
            "temperature": float(payload.get("temperature", 0.05)),
            "num_predict": int(payload.get("max_predict", 7000)),
        },
    }
    req = urllib.request.Request(
        base_url + "/api/generate",
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=240) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(json.dumps({
            "status": "error",
            "provider": "ollama",
            "model": model,
            "error": str(exc),
            "authority_created": False,
            "release_authority": False,
            "external_send_authority": False,
        }))
        return 1

    text = str(raw.get("response") or "").strip()
    if text:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                text = json.dumps(normalise_provider_result(prompt, parsed), ensure_ascii=False)
        except json.JSONDecodeError:
            # The canonical pipeline parser and validator remain the final authority.
            pass

    result = {
        "status": "ok" if text else "error",
        "provider": "ollama",
        "model": str(raw.get("model") or model),
        "response": text,
        "eval_count": raw.get("eval_count", 0),
        "authority_created": False,
        "release_authority": False,
        "external_send_authority": False,
    }
    if not text:
        result["error"] = "ollama_empty_response"
    print(json.dumps(result))
    return 0 if text else 1


if __name__ == "__main__":
    raise SystemExit(main())
