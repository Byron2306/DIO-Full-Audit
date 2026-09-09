#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dio_secrets import load_secret_env  # noqa: E402
from portfolio_runtime import load_portfolio  # noqa: E402
from scripts.serve_market_command import Handler  # noqa: E402


SENSORIUM_STATE_PATH = ROOT / "state" / "market_sensorium" / "COMMERCIAL_COCKPIT.json"
SENSORIUM_UNAVAILABLE = "SENSORIUM_UNAVAILABLE"


def sensorium_state() -> dict:
    if SENSORIUM_STATE_PATH.is_file():
        try:
            value = json.loads(SENSORIUM_STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            value = None
        if isinstance(value, dict):
            return value
    return {
        "schema": "dio.market_sensorium.cockpit_unavailable.v1",
        "state": SENSORIUM_UNAVAILABLE,
        "ranked_targets": [],
        "hypotheses": [],
        "message": "No current Market Sensorium commercial-cockpit projection is present on this host. Market Command remains available.",
        "authority_created": False,
    }


def patch_market_dashboard(page: str) -> str:
    """Keep Market Command usable when the optional Sensorium projection is absent."""
    page = page.replace(
        'href="/state/market_sensorium/COMMERCIAL_COCKPIT.html">Evidence cockpit</a>',
        'href="/sensorium-evidence">Evidence cockpit</a>',
        1,
    )
    old = (
        "async function refresh(){const b=$('refresh');b.disabled=true;b.textContent='Refreshing…';try{const [mr,cr,pr]=await Promise.all([fetch('/api/market/state',{cache:'no-store'}),fetch('/state/market_sensorium/COMMERCIAL_COCKPIT.json',{cache:'no-store'}),fetch('/api/market/products',{cache:'no-store'})]);if(!mr.ok||!cr.ok)throw new Error(`market ${mr.status}, sensorium ${cr.status}`);MARKET=await mr.json();COCKPIT=await cr.json();PRODUCTS=pr.ok?(await pr.json()).products||[]:[];populateProducts();render(MARKET,COCKPIT)}catch(e){toast(`Market state failed: ${e.message}`,true)}finally{b.disabled=false;b.textContent='Refresh'}}$('refresh').onclick=refresh;refresh();"
    )
    new = (
        "async function refresh(){const b=$('refresh');b.disabled=true;b.textContent='Refreshing…';try{const [ms,cs,ps]=await Promise.allSettled([fetch('/api/market/state',{cache:'no-store'}),fetch('/api/market/sensorium',{cache:'no-store'}),fetch('/api/market/products',{cache:'no-store'})]);if(ms.status!=='fulfilled'||!ms.value.ok)throw new Error(`market ${ms.status==='fulfilled'?ms.value.status:ms.reason}`);MARKET=await ms.value.json();COCKPIT=(cs.status==='fulfilled'&&cs.value.ok)?await cs.value.json():{state:'SENSORIUM_UNAVAILABLE',ranked_targets:[],hypotheses:[],authority_created:false};PRODUCTS=(ps.status==='fulfilled'&&ps.value.ok)?(await ps.value.json()).products||[]:[];populateProducts();render(MARKET,COCKPIT);if(COCKPIT.state==='SENSORIUM_UNAVAILABLE')toast('Market live · SENSORIUM_UNAVAILABLE · Sensorium evidence projection is not present on this host.',true)}catch(e){toast(`Market state failed: ${e.message}`,true)}finally{b.disabled=false;b.textContent='Refresh'}}$('refresh').onclick=refresh;refresh();"
    )
    return page.replace(old, new, 1)


class MS10MarketCommandHandler(Handler):
    server_version = "DIOMarketWorkbench/2.3"

    def _product_choices(self) -> dict:
        registry = load_portfolio(auto_import=True)
        products = []
        for row in registry.get("incarnations") or []:
            name = str(row.get("Incarnation") or row.get("Product") or row.get("name") or "").strip()
            if not name:
                continue
            products.append({
                "id": name,
                "name": name,
                "family": row.get("Suite") or row.get("Product Family") or row.get("Family") or "",
                "primary_family": row.get("primary_family") or row.get("Product Family") or "",
                "maturity": row.get("Maturity") or row.get("Readiness") or "",
                "execution_truth_class": row.get("execution_truth_class") or "",
                "portfolio_identity": "canonical_incarnation",
            })
        return {
            "state": "imported",
            "count": len(products),
            "candidate_incarnations_imported": registry.get("candidate_incarnations_imported", 0),
            "products": products,
        }

    def _serve_market_page(self) -> None:
        page = (ROOT / "dashboard" / "market.html").read_text(encoding="utf-8")
        page = page.replace(
            '<div class="links"><button id="refresh"',
            '<div class="links"><a class="btn green" href="http://127.0.0.1:8765/dashboard/production.html">Production Studio</a><a class="btn gold" href="http://127.0.0.1:8765/dashboard/connections.html">Connections & Secrets</a><button id="refresh"',
            1,
        )
        page = patch_market_dashboard(page)
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _serve_sensorium_evidence(self) -> None:
        state = sensorium_state()
        status = str(state.get("state") or "PRESENT")
        ranked = list(state.get("ranked_targets") or [])
        hypotheses = list(state.get("hypotheses") or state.get("hivenance_hypotheses") or [])
        message = str(state.get("message") or "Sensorium evidence projection loaded.")
        body = f"""<!doctype html><html><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>DIO Sensorium Evidence</title><style>body{{margin:0;background:#050809;color:#edf4f3;font:14px/1.5 system-ui}}main{{max-width:900px;margin:auto;padding:24px}}.panel{{background:#0b1317;border:1px solid #26363e;border-radius:10px;padding:18px;margin-top:14px}}.state{{font-size:26px;font-weight:800;color:#efc36b}}code,pre{{white-space:pre-wrap;word-break:break-word;color:#a9d7e8}}a{{color:#e4b85f}}</style></head><body><main><a href=\"/\">← Market Command</a><h1>Sensorium + HiveNance Evidence Cockpit</h1><div class=\"panel\"><div class=\"state\">{html.escape(status)}</div><p>{html.escape(message)}</p><p>Ranked targets: <b>{len(ranked)}</b> · hypotheses: <b>{len(hypotheses)}</b></p><p>This surface is read-only and creates no outreach, publication, spend, or other external authority.</p></div><div class=\"panel\"><h2>Evidence projection</h2><pre>{html.escape(json.dumps(state, indent=2, ensure_ascii=True))}</pre></div></main></body></html>""".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        route = urlsplit(self.path).path
        load_secret_env(overwrite=False)
        if route == "/api/market/products":
            self.send_json(self._product_choices())
            return
        if route == "/api/market/sensorium":
            self.send_json(sensorium_state())
            return
        if route == "/sensorium-evidence":
            self._serve_sensorium_evidence()
            return
        if route in {"/", "/dashboard/market.html"}:
            self._serve_market_page()
            return
        super().do_GET()

    def do_POST(self) -> None:
        load_secret_env(overwrite=False)
        super().do_POST()


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve DIO MARKET operator workbench")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("DIO MARKET must bind to localhost")
    load_secret_env(overwrite=False)
    portfolio = load_portfolio(auto_import=True)
    server = ThreadingHTTPServer((args.host, args.port), MS10MarketCommandHandler)
    print(f"DIO MARKET: http://{args.host}:{args.port}")
    print(f"Portfolio: {portfolio.get('canonical_incarnation_count', 0)} canonical incarnations · Campaign journey + Sensorium ACTIVE")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
