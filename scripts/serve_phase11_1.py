#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from products.attachment_intake import AttachmentIntakeError
from products.paid_reference import PaidReferenceError
from products.phase11_1 import run_attachment_delivery_journey


class Handler(BaseHTTPRequestHandler):
    output_root = ROOT / "state" / "phase11_1_runs"

    def _reply(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        route = "/vesper-intake.html" if self.path == "/" else self.path
        files = {"/vesper-intake.html": ("text/html; charset=utf-8", "vesper-intake.html"), "/vesper-intake.js": ("text/javascript; charset=utf-8", "vesper-intake.js")}
        if route not in files:
            self._reply(404, {"error": "NOT_FOUND"})
            return
        content_type, filename = files[route]
        body = (ROOT / "dashboard" / filename).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/api/attachment-delivery-journey":
            self._reply(405, {"error": "METHOD_NOT_ALLOWED"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 32 * 1024 * 1024:
                raise AttachmentIntakeError("invalid request size")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise AttachmentIntakeError("JSON object required")
            self._reply(200, run_attachment_delivery_journey(payload, output_dir=self.output_root, root=ROOT))
        except (AttachmentIntakeError, PaidReferenceError, ValueError, json.JSONDecodeError) as exc:
            self._reply(400, {"error": "PHASE11_1_REFUSED", "reason": str(exc)})

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the localhost-only Vesper attachment intake.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8112)
    parser.add_argument("--output", default=str(ROOT / "state" / "phase11_1_runs"))
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("Phase 11.1 storefront is localhost-only")
    Handler.output_root = Path(args.output).resolve()
    print(f"DIO Phase 11.1 Vesper intake: http://{args.host}:{args.port}")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
