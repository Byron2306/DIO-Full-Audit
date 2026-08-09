#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import json
import sys


def main() -> int:
    request = json.load(sys.stdin)
    with contextlib.redirect_stdout(sys.stderr):
        from backend.services.presence_server import remote_chat_generate

    result = remote_chat_generate(
        str(request["prompt"]),
        system_prompt=str(request["system_prompt"]),
        provider="gemini",
        model=str(request.get("model") or "gemini-flash-lite-latest"),
        max_predict=int(request.get("max_predict") or 6000),
        temperature=float(request.get("temperature") or 0.1),
    )
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
