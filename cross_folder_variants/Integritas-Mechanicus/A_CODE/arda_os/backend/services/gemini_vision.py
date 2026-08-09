"""Optional Gemini vision bridge for Sophia document evidence.

The key stays in environment variables and is never returned by these helpers.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict


GEMINI_VISION_DEFAULT_MODEL = (
    os.environ.get("SOPHIA_NATIVE_VISION_MODEL")
    or os.environ.get("SOPHIA_REASONED_MODEL")
    or "gemini-3.1-flash-lite"
)


def gemini_vision_status() -> Dict[str, Any]:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    enabled = os.environ.get("SOPHIA_ENABLE_NATIVE_VISION") == "1"
    provider = os.environ.get("SOPHIA_NATIVE_VISION_PROVIDER") or "gemini"
    model = os.environ.get("SOPHIA_NATIVE_VISION_MODEL") or GEMINI_VISION_DEFAULT_MODEL
    return {
        "provider": provider,
        "model": model,
        "enabled": enabled,
        "configured": bool(api_key),
        "status": "ready" if enabled and api_key and provider == "gemini" else (
            "configured_disabled" if api_key and provider == "gemini" else "missing_key_or_provider"
        ),
    }


def analyze_image_with_gemini(
    image_path: str | Path,
    *,
    prompt: str = "",
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Run Gemini vision on an image only when explicitly enabled."""
    status = gemini_vision_status()
    if status["status"] != "ready":
        return {
            "status": "not_invoked",
            "vision_status": status,
            "text": "",
            "warnings": ["native vision is not enabled/configured; use OCR/text evidence only"],
        }
    path = Path(image_path)
    if not path.exists() or not path.is_file():
        return {
            "status": "missing_image",
            "vision_status": status,
            "text": "",
            "warnings": ["image file is not available for native vision inspection"],
        }
    mime_type = mimetypes.guess_type(str(path))[0] or "image/png"
    if not mime_type.startswith("image/"):
        return {
            "status": "unsupported_mime",
            "vision_status": status,
            "text": "",
            "warnings": [f"native vision expects image MIME type, got {mime_type}"],
        }
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
    image_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    instruction = prompt or (
        "Inspect this image for academic evidence. Return only visible text, chart/figure observations, "
        "uncertainties, and what cannot be concluded. Do not invent citation metadata."
    )
    payload = {
        "contents": [{
            "parts": [
                {"text": instruction},
                {"inline_data": {"mime_type": mime_type, "data": image_b64}},
            ],
        }],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 900},
    }
    model_candidates = []
    for candidate in (
        str(status["model"] or ""),
        "gemini-flash-lite-latest",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
    ):
        if candidate and candidate not in model_candidates:
            model_candidates.append(candidate)
    data: Dict[str, Any] = {}
    used_model = ""
    errors = []
    for model in model_candidates:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
                used_model = model
                break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            errors.append(f"{model}:http_{exc.code}:{detail}")
            if exc.code not in {400, 404}:
                break
        except Exception as exc:
            errors.append(f"{model}:{type(exc).__name__}")
            break
    if not data:
        return {"status": "error", "vision_status": status, "text": "", "warnings": errors[:4] or ["gemini call failed"]}
    text_parts = []
    for candidate in data.get("candidates") or []:
        for part in ((candidate.get("content") or {}).get("parts") or []):
            if part.get("text"):
                text_parts.append(str(part.get("text")))
    text = "\n".join(text_parts).strip()
    return {
        "status": "checked" if text else "empty_response",
        "vision_status": {**status, "model_used": used_model or status.get("model")},
        "text": text,
        "warnings": [] if text else ["Gemini returned no visible analysis text"],
        "integrity_rule": "Native vision output is evidence about visible image content, not citation proof or source support by itself.",
    }
