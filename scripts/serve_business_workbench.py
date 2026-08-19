#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dio_secrets import load_secret_env  # noqa: E402
from operator_production import create_marketing_pack, production_state, run_evidence_gate  # noqa: E402
from portfolio_runtime import import_portfolio  # noqa: E402
from scripts.serve_control_deck import EVENT_LOG, emit_event  # noqa: E402
from scripts.serve_control_deck_ms10 import MS10ControlDeckHandler, _read_json_body  # noqa: E402


class BusinessWorkbenchHandler(MS10ControlDeckHandler):
    server_version = "DIOBusinessWorkbench/3.0"

    def _serve_business_page(self) -> None:
        page = (ROOT / "dashboard" / "business.html").read_text(encoding="utf-8")
        page = page.replace(
            '<div class="topnav">',
            '<div class="topnav"><a class="btn green" href="/dashboard/production.html">Production Studio</a><a class="btn gold" href="/dashboard/connections.html">Connections & Secrets</a>',
            1,
        )
        page = page.replace(
            '<a class="btn" href="#presence">Sites & social</a>',
            '<a class="btn" href="#presence">Sites & social</a><a class="btn green" href="/dashboard/production.html">Production</a><a class="btn" href="/dashboard/connections.html">Secrets & connections</a>',
            1,
        )
        youtube = '<a class="card launch social" target="_blank" rel="noreferrer" href="https://www.youtube.com/@DIOworkflows"><small>Social</small><b>YouTube</b><span>@DIOworkflows</span></a>'
        tiktok = (
            '<a class="card launch social" target="_blank" rel="noreferrer" href="https://business.tiktok.com/"><small>Social</small><b>TikTok Business</b><span>Business account / center</span></a>'
            '<a class="card launch social" target="_blank" rel="noreferrer" href="https://ads.tiktok.com/"><small>Advertising</small><b>TikTok Ads</b><span>Ads Manager</span></a>'
        )
        page = page.replace(youtube, youtube + tiktok, 1)
        self._send_bytes(page.encode("utf-8"), "text/html; charset=utf-8")

    def do_GET(self) -> None:
        route = urlsplit(self.path).path
        if route == "/api/business/production/state":
            self.send_json(production_state())
            return
        if route == "/api/business/portfolio":
            self.send_json(import_portfolio(force=False))
            return
        if route == "/api/business/health":
            portfolio = import_portfolio(force=False)
            self.send_json(
                {
                    "ok": True,
                    "service": "dio-business",
                    "version": "3.0",
                    "portfolio_auto_import": True,
                    "canonical_incarnations": portfolio.get("canonical_incarnation_count", 0),
                    "production_studio": True,
                    "marketing_asset_factory": True,
                    "evidence_gate": True,
                    "candidate_incarnations_promoted": False,
                }
            )
            return
        super().do_GET()

    def do_POST(self) -> None:
        route = urlsplit(self.path).path
        if route not in {
            "/api/business/portfolio/import",
            "/api/business/production/marketing",
            "/api/business/production/evidence-gate",
        }:
            super().do_POST()
            return
        try:
            payload = _read_json_body(self, 65536)
            if payload.get("confirmed") is not True:
                raise ValueError("Production actions require explicit operator confirmation")
            if route == "/api/business/portfolio/import":
                result = import_portfolio(force=True)
                emit_event(EVENT_LOG, "portfolio.runtime_imported", "info", "portfolio", "DIO-META-PORTFOLIO", {"canonical_incarnations": result.get("canonical_incarnation_count"), "candidate_incarnations_imported": 0})
            elif route == "/api/business/production/marketing":
                result = create_marketing_pack(payload)
                emit_event(EVENT_LOG, "production.marketing_pack_created", "action", "marketing_pack", result["run_id"], {"incarnation": result["incarnation"], "render_reel_requested": result["render_reel_requested"], "publication_authorized": False})
            else:
                result = run_evidence_gate(payload)
                emit_event(EVENT_LOG, "production.evidence_gate_ran", "action", "evidence_gate", result["run_id"], {"incarnation": result["incarnation"], "state": result["state"], "authority_created": False})
            self.send_json({"status": "completed", "result": result})
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": "production_action_blocked", "message": str(exc)}, HTTPStatus.BAD_REQUEST)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve DIO BUSINESS with production studio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("DIO BUSINESS must bind to localhost")
    load_secret_env(overwrite=False)
    portfolio = import_portfolio(force=False)
    server = ThreadingHTTPServer((args.host, args.port), BusinessWorkbenchHandler)
    print(f"DIO BUSINESS: http://{args.host}:{args.port}")
    print(f"Portfolio: {portfolio.get('canonical_incarnation_count', 0)} canonical incarnations · Production Studio ACTIVE")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
