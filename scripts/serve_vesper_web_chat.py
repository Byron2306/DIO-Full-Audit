#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.vesper_web_chat import (  # noqa: E402
    DEFAULT_STATE_ROOT,
    VesperWebChatError,
    canonical_incarnations,
    create_session,
    load_session,
    post_message,
)


PAGE = ROOT / "dashboard" / "vesper-intake.html"
SCRIPT = ROOT / "dashboard" / "vesper-intake.js"
MAX_REQUEST_BYTES = 64 * 1024 * 1024
LOCAL_CORS_ORIGINS = {
    "http://127.0.0.1:8765",
    "http://localhost:8765",
    "http://127.0.0.1:8770",
    "http://localhost:8770",
}


class VesperWebChatHandler(BaseHTTPRequestHandler):
    server_version = "DIOVesperWebChat/1.0"

    def _cors(self) -> None:
        origin = str(self.headers.get("Origin") or "")
        if origin in LOCAL_CORS_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _send(self, body: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self' http://127.0.0.1:8770 http://localhost:8770; img-src 'self' data:; base-uri 'none'; frame-ancestors 'self'")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send((json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8"), "application/json; charset=utf-8", status)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length < 2 or length > MAX_REQUEST_BYTES:
            raise VesperWebChatError(f"web-chat request must be between 2 and {MAX_REQUEST_BYTES} bytes")
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise VesperWebChatError("web-chat request must be a JSON object")
        return value

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_GET(self) -> None:
        split = urlsplit(self.path)
        route = split.path
        if route in {"/", "/chat", "/dashboard/vesper-intake.html"}:
            self._send(PAGE.read_bytes(), "text/html; charset=utf-8")
            return
        if route in {"/vesper-intake.js", "/dashboard/vesper-intake.js"}:
            self._send(SCRIPT.read_bytes(), "application/javascript; charset=utf-8")
            return
        if route == "/api/vesper/chat/products":
            self.send_json(
                {
                    "schema": "dio.vesper.web_chat.products.v1",
                    "incarnations": canonical_incarnations(),
                    "candidate_products_exposed": False,
                    "authority_created": False,
                }
            )
            return
        if route == "/api/vesper/chat/session":
            conversation_id = str((parse_qs(split.query).get("conversation_id") or [""])[0]).strip()
            try:
                session = load_session(conversation_id)
                self.send_json(
                    {
                        "schema": session["schema"],
                        "conversation_id": session["conversation_id"],
                        "identity": session["identity"],
                        "channel": session["channel"],
                        "surface": session["surface"],
                        "incarnation_hint": session.get("incarnation_hint"),
                        "route": session.get("route") or {},
                        "state": session["state"],
                        "messages": session["messages"],
                        "attachment_count": len(session.get("attachments") or []),
                        "handoff": session.get("handoff") or {},
                        "human_gate": session["human_gate"],
                        "external_send": session["external_send"],
                        "external_release": session["external_release"],
                        "authority_created": False,
                        "external_effects": False,
                    }
                )
            except VesperWebChatError as exc:
                self.send_json({"error": "vesper_session_not_found", "message": str(exc)}, HTTPStatus.NOT_FOUND)
            return
        if route == "/api/vesper/health":
            self.send_json(
                {
                    "ok": True,
                    "service": "vesper-web-chat",
                    "version": "1.0",
                    "identity": "Vesper, DIO Presence Core",
                    "channel": "web_chat",
                    "state_root": str(DEFAULT_STATE_ROOT),
                    "whatsapp_required": False,
                    "telegram_required": False,
                    "external_send": "REFUSE",
                    "external_release": "REFUSE",
                    "authority_created": False,
                }
            )
            return
        self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        route = urlsplit(self.path).path
        try:
            payload = self._read_json()
            if route == "/api/vesper/chat/session":
                result = create_session(payload)
                self.send_json({"status": "created", "session": result}, HTTPStatus.CREATED)
                return
            if route == "/api/vesper/chat/message":
                conversation_id = str(payload.pop("conversation_id", "")).strip()
                result = post_message(conversation_id, payload)
                self.send_json({"status": "completed", **result})
                return
            self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
        except (VesperWebChatError, ValueError, OSError, json.JSONDecodeError) as exc:
            self.send_json({"error": "vesper_web_chat_blocked", "message": str(exc)}, HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write("VESPER WEB CHAT " + (format % args) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve Vesper, DIO Presence Core, as a governed web chat")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Vesper Web Chat proof service must bind to localhost; use a reviewed reverse proxy for public deployment")
    server = ThreadingHTTPServer((args.host, args.port), VesperWebChatHandler)
    print(f"Vesper Web Chat: http://{args.host}:{args.port}")
    print("Identity: Vesper, DIO Presence Core · channel=web_chat · WhatsApp/Telegram not required")
    print("External send/publication/release: REFUSE · human gate: NEEDS_YOU")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
