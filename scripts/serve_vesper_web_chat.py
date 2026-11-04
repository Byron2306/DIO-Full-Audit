#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import mimetypes
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.vesper_web_chat import (  # noqa: E402
    DEFAULT_STATE_ROOT,
    VesperWebChatError,
    VesperWebChatValidationError,
    canonical_incarnations,
    create_session,
    load_session,
    post_message,
)
from products import vesper_web_chat as web
from products import vesper_public_web as public_web


PAGE = ROOT / "dashboard" / "vesper-intake.html"
SCRIPT = ROOT / "dashboard" / "vesper-intake.js"
MAX_REQUEST_BYTES = 64 * 1024 * 1024
LOCAL_CORS_ORIGINS = {
    "http://127.0.0.1:8765",
    "http://localhost:8765",
    "http://127.0.0.1:8766",
    "http://localhost:8766",
    "http://127.0.0.1:8770",
    "http://localhost:8770",
}


class VesperWebChatHandler(BaseHTTPRequestHandler):
    server_version = "DIOVesperWebChat/1.0"
    site_root: Path | None = None

    def _same_local_origin(self, origin: str) -> bool:
        host = str(self.headers.get('Host') or '')
        target = urlsplit('http://' + host)
        return target.hostname in {'127.0.0.1', 'localhost', '::1'} and origin == 'http://' + host

    def _website_origin(self) -> None:
        origin = str(self.headers.get('Origin') or '')
        if origin and origin not in LOCAL_CORS_ORIGINS and not self._same_local_origin(origin):
            raise public_web.PublicWebAccessError('website origin refused')

    def _cors(self) -> None:
        origin = str(self.headers.get("Origin") or "")
        if origin in LOCAL_CORS_ORIGINS or self._same_local_origin(origin):
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
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self' http://127.0.0.1:8770 http://localhost:8770; img-src 'self' data:; media-src 'self' blob:; base-uri 'none'; frame-ancestors 'self'")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send((json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8"), "application/json; charset=utf-8", status)

    def send_download(self, body: bytes, filename: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "same-origin")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length < 2 or length > MAX_REQUEST_BYTES:
            raise VesperWebChatError(f"web-chat request must be between 2 and {MAX_REQUEST_BYTES} bytes")
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise VesperWebChatError("web-chat request must be a JSON object")
        return value

    def do_OPTIONS(self) -> None:
        if urlsplit(self.path).path.startswith('/api/vesper/web/'):
            try:
                self._website_origin()
            except public_web.PublicWebAccessError as exc:
                self.send_json({'message': str(exc)}, HTTPStatus.FORBIDDEN)
                return
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Vesper-Session-Token")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_GET(self) -> None:
        split = urlsplit(self.path)
        route = split.path
        if route.startswith('/api/vesper/web/'):
            try:
                self._website_origin()
                query = parse_qs(split.query)
                cid = str((query.get('conversation_id') or [''])[0])
                token = self.headers.get('X-Vesper-Session-Token')
                if route == '/api/vesper/web/session':
                    session = public_web.owning_session(cid, token)
                    from products.vesper_web_chat import _public_session
                    self.send_json({'session': _public_session(session),
                                    'replies': public_web.read_replies(cid, token, after=0)['replies']})
                elif route == '/api/vesper/web/replies':
                    self.send_json(public_web.read_replies(cid, token, after=(query.get('after') or [0])[0]))
                elif route == '/api/vesper/web/journey':
                    public_web.owning_session(cid, token)
                    self.send_json({'journey': web.customer_journey(cid), 'authority_created': False})
                elif route == '/api/vesper/web/invoice':
                    session = public_web.owning_session(cid, token)
                    case_id = str(session.get('canonical_case_id') or '')
                    if not case_id:
                        raise VesperWebChatError('issued customer invoice is unavailable')
                    from presence_core.customer_cases import load_case
                    from commerce.invoices import load_invoice
                    case = load_case(web._presence_root(DEFAULT_STATE_ROOT), case_id)
                    invoice_id = str(((case or {}).get('commercial') or {}).get('invoice_id') or '')
                    if not case or not invoice_id or (case.get('commercial') or {}).get('invoice_state') != 'issued':
                        raise VesperWebChatError('issued customer invoice is unavailable')
                    invoice = load_invoice(ROOT, invoice_id)
                    if invoice.get('state') != 'issued':
                        raise VesperWebChatError('issued customer invoice is unavailable')
                    case_email = str(case.get('contact_email') or '').strip().lower()
                    invoice_email = str((invoice.get('customer') or {}).get('email') or '').strip().lower()
                    if case_email and invoice_email != case_email:
                        raise VesperWebChatError('invoice customer binding needs reconciliation')
                    document = Path(str(invoice.get('document_path') or '')).resolve()
                    invoice_root = (ROOT / 'state' / 'invoices').resolve()
                    if invoice_root not in document.parents or not document.is_file():
                        raise VesperWebChatError('issued customer invoice is unavailable')
                    self._send(document.read_bytes(), 'text/html; charset=utf-8')
                elif route == '/api/vesper/web/package':
                    session = public_web.owning_session(cid, token)
                    case_id = str(session.get('canonical_case_id') or '')
                    from presence_core.customer_cases import load_case
                    from presence_core.web_package_transport import load_authorized_web_package
                    case = load_case(web._presence_root(DEFAULT_STATE_ROOT), case_id) if case_id else None
                    if not case:
                        raise VesperWebChatError('released customer package is unavailable')
                    package, filename = load_authorized_web_package(web._presence_root(DEFAULT_STATE_ROOT), case)
                    self.send_download(package.read_bytes(), filename)
                else:
                    self.send_json({'error': 'not_found'}, HTTPStatus.NOT_FOUND)
            except public_web.PublicWebAccessError as exc:
                self.send_json({'message': str(exc)}, HTTPStatus.FORBIDDEN)
            except public_web.PublicWebInputError as exc:
                self.send_json({'message': str(exc)}, HTTPStatus.BAD_REQUEST)
            except (VesperWebChatError, OSError, ValueError):
                self.send_json({'message': 'Conversation history needs reconciliation.'}, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        if self.site_root is not None and not route.startswith('/api/'):
            relative = 'vesper-intake.html' if route in {'/', '/chat', '/dashboard/vesper-intake.html'} else route.lstrip('/')
            path = (self.site_root / relative).resolve()
            if path.is_dir():
                path = (path / 'index.html').resolve()
            allowed = {'.html', '.js', '.css', '.json', '.svg', '.png', '.webp', '.jpg', '.jpeg', '.ico', '.woff', '.woff2', '.ttf', '.mp4', '.webm'}
            if (self.site_root not in path.parents or any(part.startswith('.') for part in Path(relative).parts)
                    or path.suffix.lower() not in allowed or not path.is_file()):
                self.send_json({'error': 'not_found'}, HTTPStatus.NOT_FOUND)
                return
            body = path.read_bytes()
            if relative == 'assets/dio-config.js':
                # The original public site's API default remains intact in Git.
                # The local restoration points this same frontend to its local API.
                body += b"\nif (['localhost','127.0.0.1','::1'].includes(location.hostname)) window.DIO_SITE_CONFIG.vesperPresenceApiOrigin = location.origin;\n"
            self._send(body, mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
            return
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
                if session.get('public_web_token_sha256'):
                    public_web.owning_session(conversation_id, self.headers.get('X-Vesper-Session-Token'))
                self.send_json(
                    {
                        "schema": session["schema"],
                        "conversation_id": session["conversation_id"],
                        "canonical_conversation_id": session.get("canonical_conversation_id"),
                        "canonical_case_id": session.get("canonical_case_id"),
                        "canonical_case_stage": session.get("canonical_case_stage"),
                        "identity": session["identity"],
                        "channel": session["channel"],
                        "surface": session["surface"],
                        "incarnation_hint": session.get("incarnation_hint"),
                        "contact": dict(session.get("contact") or {}),
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
            except public_web.PublicWebAccessError as exc:
                self.send_json({'message': str(exc)}, HTTPStatus.FORBIDDEN)
            except VesperWebChatError as exc:
                self.send_json({"error": "vesper_session_not_found", "message": str(exc)}, HTTPStatus.NOT_FOUND)
            return
        if route == "/api/vesper/chat/journey":
            conversation_id = str((parse_qs(split.query).get("conversation_id") or [""])[0]).strip()
            try:
                session = load_session(conversation_id)
                if session.get('public_web_token_sha256'):
                    public_web.owning_session(conversation_id, self.headers.get('X-Vesper-Session-Token'))
                self.send_json({"journey": web.customer_journey(conversation_id), "authority_created": False})
            except public_web.PublicWebAccessError as exc:
                self.send_json({'message': str(exc)}, HTTPStatus.FORBIDDEN)
            except (VesperWebChatError, ValueError, OSError) as exc:
                self.send_json({"error": "vesper_journey_unavailable", "message": str(exc)}, HTTPStatus.NOT_FOUND)
            return
        if route == "/api/vesper/health":
            self.send_json(
                {
                    "ok": True,
                    "service": "vesper-web-chat",
                    "version": "1.2",
                    "canonical_presence_engine": True,
                    "website_frontend": 'DIO-Workflows/vesper-intake.html' if self.site_root else 'legacy_local_intake',
                    "website_session_protocol": 'session_token_v1',
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
            if route.startswith('/api/vesper/web/'):
                self._website_origin()
                token = self.headers.get('X-Vesper-Session-Token')
                if route == '/api/vesper/web/session':
                    self.send_json(public_web.open_session(payload), HTTPStatus.CREATED)
                elif route == '/api/vesper/web/message':
                    self.send_json(public_web.accept_message(payload, token))
                elif route == '/api/vesper/web/voice':
                    self.send_json(public_web.accept_voice(payload, token))
                elif route == '/api/vesper/web/journey':
                    if set(payload) != {"conversation_id", "action", "action_ref", "payload"} or not isinstance(payload.get("payload"), dict):
                        raise VesperWebChatValidationError("journey request does not match its schema")
                    cid = str(payload.get('conversation_id') or '')
                    public_web.owning_session(cid, token)
                    result = web.perform_customer_journey_action(
                        cid, action=payload.get('action'), action_ref=payload.get('action_ref'),
                        payload=payload.get('payload') if isinstance(payload.get('payload'), dict) else {},
                    )
                    self.send_json(result)
                else:
                    self.send_json({'error': 'not_found'}, HTTPStatus.NOT_FOUND)
                return
            if route == "/api/vesper/chat/session":
                result = create_session(payload)
                self.send_json({"status": "created", "session": result}, HTTPStatus.CREATED)
                return
            if route == "/api/vesper/chat/message":
                conversation_id = str(payload.pop("conversation_id", "")).strip()
                session = load_session(conversation_id)
                if session.get('public_web_token_sha256'):
                    public_web.owning_session(conversation_id, self.headers.get('X-Vesper-Session-Token'))
                result = post_message(conversation_id, payload)
                self.send_json({"status": "completed", **result})
                return
            if route == "/api/vesper/chat/journey":
                if set(payload) != {"conversation_id", "action", "action_ref", "payload"} or not isinstance(payload.get("payload"), dict):
                    raise VesperWebChatValidationError("journey request does not match its schema")
                conversation_id = str(payload.get("conversation_id") or "").strip()
                session = load_session(conversation_id)
                if session.get('public_web_token_sha256'):
                    public_web.owning_session(conversation_id, self.headers.get('X-Vesper-Session-Token'))
                result = web.perform_customer_journey_action(
                    conversation_id, action=payload.get("action"),
                    action_ref=payload.get("action_ref"),
                    payload=payload.get("payload") if isinstance(payload.get("payload"), dict) else {},
                )
                self.send_json(result)
                return
            self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
        except public_web.PublicWebAccessError as exc:
            self.send_json({'message': str(exc)}, HTTPStatus.FORBIDDEN)
        except public_web.PublicWebVoiceUnavailable as exc:
            self.send_json({'message': str(exc), 'processing_state': 'REJECTED_NO_CANONICAL_EFFECT'}, HTTPStatus.SERVICE_UNAVAILABLE)
        except VesperWebChatValidationError as exc:
            self.send_json({"error": "vesper_web_chat_input_refused", "message": str(exc),
                            "processing_state": "REJECTED_NO_CANONICAL_EFFECT"}, HTTPStatus.BAD_REQUEST)
        except (VesperWebChatError, ValueError, OSError, json.JSONDecodeError) as exc:
            self.send_json({"error": "vesper_web_chat_blocked", "message": str(exc)}, HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write("VESPER WEB CHAT " + (format % args) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve Vesper, DIO Presence Core, as a governed web chat")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument('--site-root', type=Path, help='Verified DIO-Workflows website checkout to serve')
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Vesper Web Chat proof service must bind to localhost; use a reviewed reverse proxy for public deployment")
    if args.site_root:
        site = args.site_root.expanduser().resolve()
        if not (site / 'vesper-intake.html').is_file() or not (site / 'vesper-intake.js').is_file():
            raise ValueError('DIO-Workflows Vesper frontend is missing')
        VesperWebChatHandler.site_root = site
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
