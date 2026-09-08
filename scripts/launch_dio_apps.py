#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
import webbrowser
from typing import Any
from urllib.request import Request, urlopen

LAUNCHER_URL = "http://127.0.0.1:8764/"
STATE_URL = "http://127.0.0.1:8764/api/launcher/state"


def fetch_launcher_state(timeout: float = 1.0) -> dict[str, Any]:
    request = Request(STATE_URL, headers={"Accept": "application/json", "Cache-Control": "no-cache"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Launcher state must be a JSON object")
    return payload


def _is_ready(state: dict[str, Any]) -> bool:
    surfaces = state.get("surfaces") or []
    return (
        state.get("ready") is True
        and len(surfaces) == 4
        and all(row.get("ready") is True for row in surfaces if isinstance(row, dict))
        and (state.get("portfolio") or {}).get("verified") is True
    )


def _print_failure(state: dict[str, Any], error: Exception | None = None) -> None:
    if error is not None:
        print(f"DIO launcher did not become reachable: {error}")
    surfaces = state.get("surfaces") or []
    unavailable = [
        str(row.get("name") or row.get("id") or "unknown")
        for row in surfaces
        if isinstance(row, dict) and row.get("ready") is not True
    ]
    if unavailable:
        print("Unavailable surfaces: " + ", ".join(unavailable))
    portfolio = state.get("portfolio") or {}
    if portfolio.get("verified") is not True:
        print("Portfolio truth not verified: " + str(portfolio.get("summary") or "unavailable"))


def launch_apps(timeout_seconds: float = 20.0, open_browser: bool = True) -> int:
    subprocess.run(["systemctl", "--user", "start", "dio-apps.target"], check=True)
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    last_state: dict[str, Any] = {}
    last_error: Exception | None = None

    while True:
        try:
            last_state = fetch_launcher_state()
            last_error = None
            if _is_ready(last_state):
                portfolio = last_state["portfolio"]
                print(f"DIO ready · {portfolio.get('summary', '53 + 15 = 68')} · evidence VERIFIED")
                if open_browser:
                    webbrowser.open(LAUNCHER_URL)
                return 0
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc

        now = time.monotonic()
        if now >= deadline:
            break
        time.sleep(min(0.5, max(0.0, deadline - now)))

    _print_failure(last_state, last_error)
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Start DIO local apps and open the verified launcher")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    return launch_apps(timeout_seconds=args.timeout, open_browser=not args.no_browser)


if __name__ == "__main__":
    raise SystemExit(main())
