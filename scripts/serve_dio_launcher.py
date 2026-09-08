#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dio_launcher import launcher_state  # noqa: E402

ALLOWED_BINDS = {"127.0.0.1", "localhost", "::1"}
ALLOWED_CLIENTS = {"127.0.0.1", "::1"}
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}
PAGE = ROOT / "dashboard" / "dio-launcher.html"


class LauncherHandler(BaseHTTPRequestHandler):
    server_version = "DIOLocalLauncher/1.0"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[dio-launcher] {self.address_string()} {fmt % args}")

    def _host_name(self) -> str:
        host = (self.headers.get("Host") or "").strip().lower()
        if host.startswith("["):
            return host.split("]", 1)[0] + "]"
        return host.split(":", 1)[0]

    def _local_guard(self) -> bool:
        client = self.client_address[0]
        return client in ALLOWED_CLIENTS and self._host_name() in ALLOWED_HOSTS

    def _send_bytes(self, body: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send_bytes(
            json.dumps(payload, ensure_ascii=True).encode("utf-8"),
            "application/json; charset=utf-8",
            status,
        )

    def do_GET(self) -> None:
        if not self._local_guard():
            self._send_json({"error": "localhost_required"}, HTTPStatus.FORBIDDEN)
            return
        route = urlsplit(self.path).path
        if route == "/api/launcher/state":
            self._send_json(launcher_state())
            return
        if route in {"/", "/dashboard/dio-launcher.html"}:
            self._send_bytes(PAGE.read_bytes(), "text/html; charset=utf-8")
            return
        if route == "/heartbeat":
            self._send_json({"ok": True, "service": "dio-local-launcher", "read_only": True})
            return
        self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        self.send_error(405, "Method Not Allowed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the read-only DIO local app launcher")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8764)
    args = parser.parse_args()
    if args.host not in ALLOWED_BINDS:
        raise ValueError("DIO launcher must bind to localhost")
    server = ThreadingHTTPServer((args.host, args.port), LauncherHandler)
    print(f"DIO launcher: http://{args.host}:{args.port}")
    print("Read-only app surface · authority created: NO")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
