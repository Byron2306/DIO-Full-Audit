#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import json
import sys
import time
from typing import Any, Callable


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
                last["bridge_attempt_count"] = attempt
                last["bridge_retry_used"] = attempt > 1
                last["bridge_retry_errors"] = errors
                return last
            errors.append(str(last.get("error") or last.get("status") or "provider_unavailable"))
        except Exception as exc:  # noqa: BLE001 - bridge must preserve transient provider failure as data.
            errors.append(f"{type(exc).__name__}: {exc}")
            last = {"status": "error", "provider": "gemini", "error": errors[-1]}

        if attempt < attempts:
            time.sleep(float(attempt))

    last["bridge_attempt_count"] = attempts
    last["bridge_retry_used"] = attempts > 1
    last["bridge_retry_errors"] = errors
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
