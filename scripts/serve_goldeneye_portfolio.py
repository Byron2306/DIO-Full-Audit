#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]


class GoldenEyePortfolioHandler(SimpleHTTPRequestHandler):
    snapshot_path = ROOT / "state" / "control_deck" / "CONTROL_DECK_PORTFOLIO_SNAPSHOT.json"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _json(self, status: HTTPStatus, payload: dict) -> None:
        body = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path == "/":
            self.path = "/dashboard/goldeneye-portfolio.html"
            return super().do_GET()
        if path == "/api/control-deck/portfolio":
            if not self.snapshot_path.is_file():
                return self._json(HTTPStatus.SERVICE_UNAVAILABLE, {
                    "error": "portfolio_snapshot_missing",
                    "action": "run python scripts/run_control_deck_phase9.py --output state/control_deck",
                    "authority_created": False,
                })
            return self._json(HTTPStatus.OK, json.loads(self.snapshot_path.read_text(encoding="utf-8")))
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        self._json(HTTPStatus.METHOD_NOT_ALLOWED, {
            "error": "goldeneye_portfolio_is_projection_only",
            "authority_created": False,
            "external_effects": False,
        })


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the read-only Phase 9 GoldenEye portfolio surface.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--snapshot", default=str(GoldenEyePortfolioHandler.snapshot_path))
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("GoldenEye Portfolio OS may bind only to localhost.")
    GoldenEyePortfolioHandler.snapshot_path = Path(args.snapshot).expanduser().resolve()
    server = ThreadingHTTPServer((args.host, args.port), GoldenEyePortfolioHandler)
    print(f"DIO GoldenEye Portfolio OS: http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
