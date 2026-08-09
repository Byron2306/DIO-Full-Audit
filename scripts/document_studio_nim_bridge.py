#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import httpx


DEFAULT_SECRET_FILE = Path("/home/byron/EdgeK-BEAST/.beast/provider_secrets.env")
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "deepseek-ai/deepseek-v4-flash-0731"


def load_secret(path: Path, key: str) -> str:
    if value := os.environ.get(key):
        return value
    if not path.is_file():
        raise RuntimeError(f"NVIDIA provider secret file is unavailable: {path}")
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        name, value = line.split("=", 1)
        if name.strip() == key:
            return value.strip().strip('"').strip("'")
    raise RuntimeError(f"{key} is unavailable in the configured provider secret file.")


def main() -> int:
    request = json.load(sys.stdin)
    secret_file = Path(str(request.get("secret_file") or DEFAULT_SECRET_FILE)).expanduser()
    api_key = load_secret(secret_file, "NVIDIA_API_KEY")
    base_url = str(request.get("base_url") or os.environ.get("NVIDIA_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    model = str(request.get("model") or DEFAULT_MODEL)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": str(request["system_prompt"])},
            {"role": "user", "content": str(request["prompt"])},
        ],
        "temperature": float(request.get("temperature") or 0.05),
        "max_tokens": int(request.get("max_predict") or 7000),
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=240.0) as client:
        response = client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
    if response.status_code >= 400:
        safe_error = re.sub(r"nvapi-[A-Za-z0-9_-]+", "[REDACTED]", response.text[:1200])
        print(json.dumps({"status": "error", "provider": "nvidia_nim", "model": model, "error": f"http_{response.status_code}:{safe_error}"}))
        return 0
    body = response.json()
    choice = (body.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = str(message.get("content") or choice.get("text") or "")
    print(json.dumps({
        "status": "ok" if content else "empty",
        "provider": "nvidia_nim",
        "model": model,
        "response": content,
        "usage": body.get("usage") or {},
        "response_id": body.get("id"),
        "secret_source": "NVIDIA_API_KEY",
        "secret_values_redacted": True,
    }, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
