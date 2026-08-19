#!/usr/bin/env python3
from __future__ import annotations

import argparse
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dio_secrets import load_secret_env  # noqa: E402
from portfolio_runtime import load_portfolio  # noqa: E402
from scripts.serve_market_command import Handler  # noqa: E402


class MS10MarketCommandHandler(Handler):
    server_version = "DIOMarketWorkbench/2.2"

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
        body = page.encode("utf-8")
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
