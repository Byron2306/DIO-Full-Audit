#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.serve_control_deck import ControlDeckHandler  # noqa: E402
from scripts.serve_market_command_ms10 import sensorium_state  # noqa: E402

CAPITAL_SUPPORT_PRIORITY = ROOT / "state" / "market_capital" / "rankings" / "CAPITAL_SUPPORT_PRIORITY.json"


def capital_support_priority_state() -> dict:
    if not CAPITAL_SUPPORT_PRIORITY.is_file():
        return {
            "schema": "dio.goldeneye.capital_support_priority.v1",
            "state": "EMPTY",
            "items": [],
            "opportunity_count": 0,
            "truth_class": "RANKED_PRIORITY_MODEL_OUTPUT",
            "message": "No capital or support opportunities ranked yet.",
            "authority_created": False,
            "external_effects": False,
        }
    try:
        payload = json.loads(CAPITAL_SUPPORT_PRIORITY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "schema": "dio.goldeneye.capital_support_priority.v1",
            "state": "UNAVAILABLE",
            "items": [],
            "opportunity_count": 0,
            "truth_class": "RANKED_PRIORITY_MODEL_OUTPUT",
            "message": f"Capital/support priority state unreadable: {exc}",
            "authority_created": False,
            "external_effects": False,
        }
    if not isinstance(payload, dict):
        payload = {"items": []}
    payload.setdefault("schema", "dio.goldeneye.capital_support_priority.v1")
    payload.setdefault("state", "PRESENT" if payload.get("items") else "EMPTY")
    payload.setdefault("items", [])
    payload.setdefault("opportunity_count", len(payload.get("items") or []))
    payload["truth_class"] = "RANKED_PRIORITY_MODEL_OUTPUT"
    payload["authority_created"] = False
    payload["external_effects"] = False
    return payload


class GoldenEyeMS10Handler(ControlDeckHandler):
    server_version = "DIOGoldenEyeMS10/1.2"

    def _serve_goldeneye_page(self) -> None:
        page = (ROOT / "dashboard" / "goldeneye-ms10.html").read_text(encoding="utf-8")
        injection = '<script src="/dashboard/goldeneye_capital_slice3.js"></script>'
        if injection not in page:
            page = page.replace("</body>", injection + "</body>", 1)
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        route = urlsplit(self.path).path
        if route == "/api/goldeneye/sensorium":
            self.send_json(sensorium_state())
            return
        if route == "/api/goldeneye/capital-support":
            self.send_json(capital_support_priority_state())
            return
        if route in {"/", "/dashboard/goldeneye-ms10.html"}:
            self._serve_goldeneye_page()
            return
        super().do_GET()


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve GoldenEye from the current DIO repo with the MS-10 Sensorium truth plane")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("GoldenEye must bind to localhost")
    server = ThreadingHTTPServer((args.host, args.port), GoldenEyeMS10Handler)
    print(f"DIO GoldenEye MS-10: http://{args.host}:{args.port}")
    print("Current-repo portfolio state + canonical Market Sensorium truth plane + read-only Capital & Support priority field")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
