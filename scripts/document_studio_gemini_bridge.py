#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import json
import re
import sys
import time
from typing import Any, Callable


def _parse_json_object(value: str) -> dict[str, Any]:
    """Validate structured provider output without repairing or rewriting it."""
    cleaned = value.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("provider response does not contain a JSON object")
    parsed = json.loads(cleaned[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("provider structured response must be a JSON object")
    return parsed


def _invoke_with_retry(
    request: dict[str, Any],
    remote_chat_generate: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    attempts = max(1, min(4, int(request.get("provider_attempts") or 3)))
    last: dict[str, Any] = {"status": "error", "provider": "gemini", "error": "provider_not_invoked"}
    errors: list[str] = []

    for attempt in range(1, attempts + 1):
        try:
            result = remote_chat_generate(
                str(request["prompt"]),
                system_prompt=str(request["system_prompt"]),
                provider="gemini",
                model=str(request.get("model") or "gemini-flash-lite-latest"),
                max_predict=int(request.get("max_predict") or 6000),
                temperature=float(request.get("temperature") or 0.1),
            )
            last = dict(result or {})
            if last.get("status") == "ok" and last.get("response"):
                try:
                    _parse_json_object(str(last["response"]))
                except (ValueError, json.JSONDecodeError) as exc:
                    errors.append(f"malformed_structured_output:{type(exc).__name__}:{exc}")
                    last = {
                        **last,
                        "status": "error",
                        "error": "malformed_structured_output",
                    }
                else:
                    last["bridge_attempt_count"] = attempt
                    last["bridge_retry_used"] = attempt > 1
                    last["bridge_retry_errors"] = errors
                    last["structured_output_validated"] = True
                    return last
            else:
                errors.append(str(last.get("error") or last.get("status") or "provider_unavailable"))
        except Exception as exc:  # noqa: BLE001 - bridge must preserve transient provider failure as data.
            errors.append(f"{type(exc).__name__}: {exc}")
            last = {"status": "error", "provider": "gemini", "error": errors[-1]}

        if attempt < attempts:
            time.sleep(float(attempt))

    last["bridge_attempt_count"] = attempts
    last["bridge_retry_used"] = attempts > 1
    last["bridge_retry_errors"] = errors
    last["structured_output_validated"] = False
    return last


def main() -> int:
    request = json.load(sys.stdin)
    with contextlib.redirect_stdout(sys.stderr):
        from backend.services.presence_server import remote_chat_generate

    result = _invoke_with_retry(request, remote_chat_generate)
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
