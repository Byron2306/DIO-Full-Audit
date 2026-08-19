#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import mimetypes
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import parse_qs, quote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from commerce.invoices import create_invoice, issue_invoice, list_invoices, load_invoice  # noqa: E402
from dio_secrets import load_secret_env, save_secret_values, secret_status  # noqa: E402
from scripts.manage_mail_intent import create_intent_from_payload  # noqa: E402
from scripts.serve_control_deck import (  # noqa: E402
    ControlDeckHandler,
    EVENT_LOG,
    emit_event,
    load_policy,
    read_json,
    utc_now,
    write_json,
)


ALLOWED_ARTIFACT_ROOTS = tuple(
    root.resolve()
    for root in (
        ROOT,
        Path("/home/byron/Downloads/KnowEdge_AutoRelease_Suite"),
        Path("/home/byron/Downloads/NicheFoundry_Phase11"),
        Path("/home/byron/KnowEdge_Microsoft_Mirror"),
    )
    if root.exists()
)


def _inside_allowed_root(path: Path) -> bool:
    return any(path == root or root in path.parents for root in ALLOWED_ARTIFACT_ROOTS)


def _resolve_artifact(raw: str) -> Path:
    if not raw.strip():
        raise ValueError("Artifact path is required")
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    resolved = candidate.resolve()
    if not _inside_allowed_root(resolved):
        raise ValueError("Artifact path is outside the approved DIO output roots")
    return resolved


def _business_artifact_url(path: Path) -> str:
    return "/api/business/artifact?path=" + quote(str(path), safe="")


def _directory_html(path: Path) -> bytes:
    rows = []
    parent = path.parent if _inside_allowed_root(path.parent) else None
    if parent is not None:
        rows.append(f'<a class="row" href="{html.escape(_business_artifact_url(parent))}">← parent</a>')
    for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold())):
        suffix = "/" if child.is_dir() else ""
        rows.append(
            f'<a class="row" href="{html.escape(_business_artifact_url(child))}">'
            f'<b>{html.escape(child.name)}{suffix}</b>'
            f'<span>{"folder" if child.is_dir() else html.escape(mimetypes.guess_type(child.name)[0] or "file")}</span>'
            "</a>"
        )
    body = "".join(rows) or '<div class="empty">This output folder is empty.</div>'
    return f"""<!doctype html><meta charset="utf-8"><title>DIO output · {html.escape(path.name)}</title>
<style>body{{margin:0;background:#071014;color:#eef4f3;font:14px/1.45 system-ui,sans-serif}}main{{max-width:1100px;margin:auto;padding:24px}}h1{{font:700 34px Georgia,serif;margin:0 0 5px}}p{{color:#91a0a4;word-break:break-all}}.list{{border:1px solid #28363d;border-radius:9px;overflow:hidden}}.row{{display:flex;justify-content:space-between;gap:20px;padding:11px 13px;border-bottom:1px solid #202c31;color:#eef4f3;text-decoration:none}}.row:hover{{background:#101b20}}.row span{{color:#8fa0a5}}.empty{{padding:18px;color:#8fa0a5}}</style>
<main><h1>DIO output</h1><p>{html.escape(str(path))}</p><div class="list">{body}</div></main>""".encode("utf-8")


def _read_json_body(handler: ControlDeckHandler, maximum: int = 32768) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length < 2 or length > maximum:
        raise ValueError(f"Business request must be between 2 and {maximum} bytes")
    payload = json.loads(handler.rfile.read(length))
    if not isinstance(payload, dict):
        raise ValueError("Business request must be a JSON object")
    return payload


class MS10ControlDeckHandler(ControlDeckHandler):
    server_version = "DIOBusinessWorkbench/2.4"

    def _send_bytes(self, body: bytes, content_type: str, filename: str | None = None) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if filename:
            self.send_header("Content-Disposition", f'inline; filename="{filename.replace(chr(34), "")}"')
        self.end_headers()
        self.wfile.write(body)

    def _serve_business_page(self) -> None:
        page = (ROOT / "dashboard" / "business.html").read_text(encoding="utf-8")
        page = page.replace(
            '<div class="topnav">',
            '<div class="topnav"><a class="btn gold" href="/dashboard/connections.html">Connections & Secrets</a>',
            1,
        )
        page = page.replace(
            '<a class="btn" href="#presence">Sites & social</a>',
            '<a class="btn" href="#presence">Sites & social</a><a class="btn" href="/dashboard/connections.html">Secrets & connections</a>',
            1,
        )
        youtube = '<a class="card launch social" target="_blank" rel="noreferrer" href="https://www.youtube.com/@DIOworkflows"><small>Social</small><b>YouTube</b><span>@DIOworkflows</span></a>'
        tiktok = (
            '<a class="card launch social" target="_blank" rel="noreferrer" href="https://business.tiktok.com/"><small>Social</small><b>TikTok Business</b><span>Business account / center</span></a>'
            '<a class="card launch social" target="_blank" rel="noreferrer" href="https://ads.tiktok.com/"><small>Advertising</small><b>TikTok Ads</b><span>Ads Manager</span></a>'
        )
        page = page.replace(youtube, youtube + tiktok, 1)
        self._send_bytes(page.encode("utf-8"), "text/html; charset=utf-8")

    def _redirect_repo_artifact(self, target: Path) -> bool:
        repo_root = ROOT.resolve()
        if not (target == repo_root or repo_root in target.parents):
            return False
        relative = target.relative_to(repo_root).as_posix()
        location = "/" + quote(relative, safe="/")
        if target.is_dir() and not location.endswith("/"):
            location += "/"
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        return True

    def _serve_artifact(self) -> None:
        params = parse_qs(urlsplit(self.path).query)
        raw = (params.get("path") or [""])[0]
        try:
            target = _resolve_artifact(raw)
        except ValueError as exc:
            self.send_json({"error": "artifact_path_blocked", "message": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if not target.exists():
            self.send_json(
                {"error": "artifact_missing", "message": "The recorded output path does not currently exist.", "path": str(target)},
                HTTPStatus.NOT_FOUND,
            )
            return
        if self._redirect_repo_artifact(target):
            return
        if target.is_dir():
            self._send_bytes(_directory_html(target), "text/html; charset=utf-8")
            return
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self._send_bytes(target.read_bytes(), content_type, target.name)

    def _update_lead(self) -> None:
        payload = _read_json_body(self, 16384)
        if payload.get("confirmed") is not True:
            raise ValueError("Lead update requires explicit operator confirmation")
        lead_id = str(payload.get("lead_id") or "").upper()
        if not lead_id or not lead_id.replace("-", "").isalnum():
            raise ValueError("Invalid lead id")
        path = ROOT / "state" / "leads" / f"{lead_id}.json"
        if not path.is_file():
            raise ValueError("Lead does not exist")
        lead = read_json(path)
        contact = dict(lead.get("contact") or {})
        for field in ("name", "email", "organisation"):
            if field in payload:
                contact[field] = str(payload.get(field) or "").strip()
        lead["contact"] = contact
        if "offer" in payload:
            lead["offer"] = str(payload.get("offer") or "").strip()
        if "notes" in payload:
            lead["operator_notes"] = str(payload.get("notes") or "").strip()
        lead["updated_at"] = utc_now()
        lead["updated_by"] = "DIO operator via BUSINESS"
        write_json(path, lead)
        emit_event(
            EVENT_LOG,
            "lead.updated",
            "action",
            "lead",
            lead_id,
            {"fields": [key for key in ("name", "email", "organisation", "offer", "notes") if key in payload]},
            lead_id,
        )
        self.send_json({"status": "completed", "action": "update", "result": lead})

    def _save_secrets(self) -> None:
        payload = _read_json_body(self, 65536)
        if payload.get("confirmed") is not True:
            raise ValueError("Saving credentials requires explicit operator confirmation")
        values = payload.get("values")
        if not isinstance(values, dict) or not values:
            raise ValueError("Credential values must be a non-empty object")
        result = save_secret_values(values)
        load_secret_env(overwrite=True)
        emit_event(
            EVENT_LOG,
            "business.secrets_updated",
            "action",
            "secret_vault",
            "DIO-LOCAL-SECRETS",
            {"changed_keys": result["changed"], "cleared_keys": result["cleared"], "values_logged": False},
            "DIO-LOCAL-SECRETS",
        )
        self.send_json({"status": "completed", "save": result, "secret_status": secret_status()})

    def _create_invoice(self) -> None:
        payload = _read_json_body(self)
        issue = payload.get("issue") is True
        if issue and load_policy().get("invoice_authority") != "issue":
            raise ValueError("Invoice issue is held by invoice_authority=draft_only; enable invoice issue in BUSINESS first")
        invoice = create_invoice(ROOT, payload, issue=issue, operator="DIO operator via BUSINESS")
        emit_event(
            EVENT_LOG,
            "invoice.issued" if issue else "invoice.drafted",
            "action" if issue else "info",
            "invoice",
            invoice["invoice_id"],
            {
                "state": invoice["state"],
                "total_minor": invoice["total_minor"],
                "currency": invoice["currency"],
                "lead_id": invoice["lineage"].get("lead_id"),
                "job_id": invoice["lineage"].get("job_id"),
            },
            invoice["lineage"].get("job_id") or invoice["lineage"].get("lead_id"),
        )
        self.send_json({"status": "completed", "invoice": invoice})

    def _issue_invoice(self) -> None:
        payload = _read_json_body(self)
        if payload.get("confirmed") is not True:
            raise ValueError("Invoice issue requires explicit operator confirmation")
        if load_policy().get("invoice_authority") != "issue":
            raise ValueError("Invoice issue is held by invoice_authority=draft_only; enable invoice issue in BUSINESS first")
        invoice_id = str(payload.get("invoice_id") or "")
        invoice = issue_invoice(ROOT, invoice_id, operator="DIO operator via BUSINESS")
        emit_event(EVENT_LOG, "invoice.issued", "action", "invoice", invoice_id, {"total_minor": invoice["total_minor"], "currency": invoice["currency"]}, invoice_id)
        self.send_json({"status": "completed", "invoice": invoice})

    def _prepare_invoice_mail(self) -> None:
        payload = _read_json_body(self)
        if payload.get("confirmed") is not True:
            raise ValueError("Invoice email preparation requires explicit operator confirmation")
        invoice = load_invoice(ROOT, str(payload.get("invoice_id") or ""))
        if invoice["state"] != "issued":
            raise ValueError("Only an issued invoice may be prepared for email")
        recipient = str(invoice["customer"].get("email") or "").strip()
        if not recipient:
            raise ValueError("Invoice customer email is missing")
        amount = f"{invoice['currency']} {invoice['total_minor'] / 100:,.2f}"
        intent = create_intent_from_payload(
            {
                "purpose": "invoice",
                "recipient": recipient,
                "subject": f"DIO Workflows invoice {invoice['invoice_id']}",
                "body": (
                    f"Hello {invoice['customer']['name']},\n\n"
                    f"Please find invoice {invoice['invoice_id']} attached for {amount}, due {invoice['due_date']}.\n\n"
                    "The invoice records the agreed DIO Workflows service and payment reference. "
                    "Please reply to this message if any billing detail needs correction before payment.\n\n"
                    "Regards,\nDIO Workflows"
                ),
                "attachments": [invoice["document_path"]],
                "risk": "routine",
                "lead_id": invoice["lineage"].get("lead_id"),
                "job_id": invoice["lineage"].get("job_id"),
                "order_id": invoice["lineage"].get("order_id"),
                "product": "dio_invoice",
            },
            ROOT / "state" / "mail_intents",
            EVENT_LOG,
        )
        emit_event(EVENT_LOG, "invoice.mail_prepared", "action", "invoice", invoice["invoice_id"], {"mail_intent_id": intent["mail_intent_id"]}, invoice["invoice_id"])
        self.send_json({"status": "completed", "invoice_id": invoice["invoice_id"], "mail_intent": intent})

    def do_GET(self) -> None:
        route = urlsplit(self.path).path
        if route in {"/", "/dashboard/business.html"}:
            self._serve_business_page()
            return
        if route == "/api/business/artifact":
            self._serve_artifact()
            return
        if route == "/api/business/invoices":
            self.send_json({"schema": "dio.business.invoice_list.v1", "invoices": list_invoices(ROOT)})
            return
        if route == "/api/business/secrets":
            self.send_json(secret_status())
            return
        if route == "/api/business/health":
            self.send_json({"ok": True, "service": "dio-business", "version": "2.4", "artifact_gateway": True, "lead_editing": True, "invoice_desk": True, "secret_vault": True, "connections_surface": True, "tiktok_quick_links": True})
            return
        super().do_GET()

    def do_POST(self) -> None:
        route = urlsplit(self.path).path
        business_routes = {
            "/api/business/lead/update": self._update_lead,
            "/api/business/secrets": self._save_secrets,
            "/api/business/invoice/create": self._create_invoice,
            "/api/business/invoice/issue": self._issue_invoice,
            "/api/business/invoice/mail": self._prepare_invoice_mail,
        }
        if route in business_routes:
            try:
                business_routes[route]()
            except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
                self.send_json({"error": "business_action_blocked", "message": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        super().do_POST()


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve DIO BUSINESS operator workbench")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("DIO BUSINESS must bind to localhost")
    load_secret_env(overwrite=False)
    server = ThreadingHTTPServer((args.host, args.port), MS10ControlDeckHandler)
    print(f"DIO BUSINESS: http://{args.host}:{args.port}")
    print("Human operator workbench: ACTIVE · artifact gateway ACTIVE · invoice desk ACTIVE · secret vault ACTIVE")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
