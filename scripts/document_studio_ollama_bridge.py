#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    base_url = str(payload.get("base_url") or "http://127.0.0.1:11434").rstrip("/")
    model = str(payload.get("model") or "qwen2.5:0.5b")
    request_body = {
        "model": model,
        "prompt": str(payload.get("prompt") or ""),
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
