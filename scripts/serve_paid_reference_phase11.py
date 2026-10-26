#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from products.paid_reference import PaidReferenceError, run_paid_reference_journey


class Handler(BaseHTTPRequestHandler):
    output_root = ROOT / "state" / "paid_reference_runs"

    def _reply(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in {"/", "/paid-reference.html"}:
            body = (ROOT / "dashboard" / "paid-reference.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/paid-reference.js":
            body = (ROOT / "dashboard" / "paid-reference.js").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._reply(404, {"error": "NOT_FOUND"})

    def do_POST(self) -> None:
        if self.path != "/api/reference-journey":
            self._reply(405, {"error": "METHOD_NOT_ALLOWED"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 16_384:
                raise PaidReferenceError("invalid request size")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise PaidReferenceError("JSON object required")
            journey = run_paid_reference_journey(payload, output_dir=self.output_root)
            self._reply(200, journey)
        except (PaidReferenceError, ValueError, json.JSONDecodeError) as exc:
            self._reply(400, {"error": "REFERENCE_JOURNEY_REFUSED", "reason": str(exc)})

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the localhost-only Phase 11 reference storefront.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8111)
    parser.add_argument("--output", default=str(ROOT / "state" / "paid_reference_runs"))
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("Phase 11 reference storefront is localhost-only")
    Handler.output_root = Path(args.output).resolve()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"DIO Phase 11 reference storefront: http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
