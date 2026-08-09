#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
_ROOT_BOOT = Path(__file__).resolve().parents[1]
if str(_ROOT_BOOT) not in sys.path:
    sys.path.insert(0, str(_ROOT_BOOT))

import json
import os
from datetime import date, timedelta
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from typing import Any

from market_command.catalog import load_catalogs, load_json
from market_command.core import MarketStore
from market_command.intelligence import IntelligenceStore
from market_command.channel_sync import sync_channel
from market_command.export_pack import export_campaign_pack
from market_command.agency import bind_outlook_draft, list_agency_outreach, prepare_agency_rfq
from adapters.marketing.readiness import adapter_readiness
from scripts.sync_outlook_mail import GraphClient, create_outlook_draft, load_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "market_command.json"
DB = ROOT / "state" / "market_command" / "market_command.sqlite"
EVENTS = ROOT / "telemetry" / "dio_events.jsonl"
CONTROL_POLICY = ROOT / "state" / "control_policy.json"
GRAPH_CONFIG = ROOT / "config" / "microsoft_graph.local.json"


def market_store() -> MarketStore:
    return MarketStore(DB, EVENTS, load_json(CONFIG))


def intelligence_store() -> IntelligenceStore:
    return IntelligenceStore(DB, EVENTS)


def read_body(handler: SimpleHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length < 2 or length > 262144:
        raise ValueError("Request body must be 2..262144 bytes")
    content_type = handler.headers.get("Content-Type", "")
    if "application/json" not in content_type:
        raise ValueError("Content-Type application/json required")
    payload = json.loads(handler.rfile.read(length))
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")
    return payload


class Handler(SimpleHTTPRequestHandler):
    server_version = "DIOMarketCommand/2.0"

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        print(f"[market-command] {self.address_string()} {fmt % args}")

    def _local_guard(self) -> None:
        if self.client_address[0] not in {"127.0.0.1", "::1"}:
            raise ValueError("Localhost client required")
        host = (self.headers.get("Host") or "").split(":", 1)[0].lower()
        if host not in {"127.0.0.1", "localhost", "::1", "[::1]"}:
            raise ValueError("Localhost Host header required")
        origin = self.headers.get("Origin")
        if origin and not (origin.startswith("http://127.0.0.1") or origin.startswith("http://localhost") or origin.startswith("http://[::1]")):
            raise ValueError("Cross-origin control requests are blocked")
        required = os.environ.get("DIO_MARKET_CONTROL_TOKEN")
        if required and self.headers.get("X-DIO-Control-Token") != required:
            raise ValueError("Invalid DIO Market Control token")

    def send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        route = urlsplit(self.path).path
        if route == "/api/market/state":
            catalogs = load_catalogs(ROOT)
            base = market_store().state(catalogs)
            base["adapter_readiness"] = {c["id"]: adapter_readiness(c["id"]) for c in catalogs["channels"]["channels"]}
            base["intelligence"] = intelligence_store().state()
            base["agency_outreach"] = list_agency_outreach(ROOT)
            base["schema"] = "dio.market_command.state.v2"
            self.send_json(base)
            return
        if route == "/api/market/catalogs":
            self.send_json(load_catalogs(ROOT)); return
        if route == "/api/market/health":
            self.send_json({"ok": True, "service": "dio-market-command", "version": "2.0", "write_adapters_enabled": False}); return
        if route == "/":
            self.path = "/market_dashboard/index.html"
        super().do_GET()

    def do_POST(self):
        route = urlsplit(self.path).path
        try:
            self._local_guard()
            p = read_body(self)
            st = market_store()
            intel = intelligence_store()
            if route == "/api/market/campaigns":
                result = st.create_campaign(p)
            elif route.startswith("/api/market/campaigns/"):
                parts = route.strip("/").split("/")
                cid = parts[3]
                action = parts[4] if len(parts) > 4 else ""
                if action == "approve": result = st.approve_campaign(cid, p.get("confirmed") is True)
                elif action == "activate": result = st.activate_campaign(cid, p.get("confirmed") is True)
                elif action == "measure": result = st.record_measurement(cid, p)
                elif action == "settle": result = st.settle_campaign(cid, p.get("confirmed") is True)
                elif action == "content": result = st.add_content(cid, p)
                elif action == "export-pack":
                    campaign = st.get_campaign(cid)
                    catalogs = load_catalogs(ROOT)
                    channel = next((x for x in catalogs["channels"]["channels"] if x["id"] == campaign["channel_id"]), None)
                    result = export_campaign_pack(ROOT, campaign, channel)
                else: raise ValueError("Unknown campaign action")
            elif route.startswith("/api/market/content/"):
                parts = route.strip("/").split("/")
                content_id = parts[3]
                action = parts[4] if len(parts) > 4 else ""
                if action == "approve":
                    result = st.approve_content(content_id, p.get("confirmed") is True)
                else:
                    raise ValueError("Unknown content action")
            elif route == "/api/market/media-buys":
                result = st.create_media_buy(p)
            elif route.startswith("/api/market/media-buys/") and route.endswith("/quote"):
                bid = route.strip("/").split("/")[3]
                if p.get("confirmed") is not True:
                    raise ValueError("Recording an agency quote requires explicit operator confirmation")
                result = st.record_media_quote(
                    bid,
                    int(p.get("quote_minor") or 0),
                    str(p.get("quote_reference") or ""),
                    int(p.get("approved_cap_minor") or 0),
                    str(p.get("notes") or ""),
                )
            elif route.startswith("/api/market/media-buys/") and route.endswith("/result"):
                bid = route.strip("/").split("/")[3]
                if p.get("confirmed") is not True:
                    raise ValueError("Recording a provider result requires explicit operator confirmation")
                result = st.record_media_result(bid, str(p.get("result_reference") or ""), p.get("metrics") or {})
            elif route.startswith("/api/market/media-buys/") and route.endswith("/approve"):
                bid = route.strip("/").split("/")[3]
                result = st.approve_media_buy(bid, p.get("confirmed") is True)
            elif route == "/api/market/agencies/rfq":
                if p.get("confirmed") is not True:
                    raise ValueError("Agency RFQ preparation requires explicit operator confirmation")
                result = prepare_agency_rfq(
                    ROOT,
                    st,
                    str(p.get("campaign_id") or ""),
                    str(p.get("agency_id") or ""),
                    str(p.get("placement") or ""),
                    "DIO operator via Market Command",
                    p.get("route_confirmed") is True,
                )
                if result.get("mail_intent_id") and not result.get("provider_draft_id"):
                    policy = load_json(CONTROL_POLICY) if CONTROL_POLICY.exists() else {}
                    if policy.get("outbound_mail") != "on":
                        raise ValueError("RFQ package created, but Outlook draft creation is held by outbound_mail=off")
                    graph = GraphClient(load_config(GRAPH_CONFIG))
                    graph.acquire_token(interactive=False)
                    receipt = create_outlook_draft(graph, ROOT / "state" / "mail_intents", EVENTS, result["mail_intent_id"])
                    result = bind_outlook_draft(ROOT, result["campaign_id"], result["agency_id"], receipt)
            elif route == "/api/market/policy":
                result = st.set_policy(str(p.get("key") or ""), str(p.get("value") or ""))
            elif route == "/api/market/external-links":
                result = intel.bind_external_campaign(p)
            elif route == "/api/market/attribution":
                result = intel.record_attribution(p)
            elif route == "/api/market/roles":
                result = intel.bind_role(p)
            elif route == "/api/market/import-snapshot":
                result = intel.record_snapshot(p)
            elif route.startswith("/api/market/channels/") and route.endswith("/sync"):
                channel_id = route.strip("/").split("/")[3]
                end = str(p.get("end_date") or date.today().isoformat())
                start = str(p.get("start_date") or (date.today() - timedelta(days=7)).isoformat())
                result = sync_channel(intel, channel_id, start, end)
            else:
                self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND); return
            self.send_json(result)
        except (ValueError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
            self.send_json({"error": "market_action_blocked", "message": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self.send_json({"error": "market_internal_error", "message": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Serve localhost-only DIO Market Command Wave 2")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8770)
    args = ap.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Market Command must bind to localhost")
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"DIO Market Command Wave 2: http://{args.host}:{args.port}")
    print("Write-capable ad adapters: DISABLED BY DESIGN")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == "__main__":
    main()
