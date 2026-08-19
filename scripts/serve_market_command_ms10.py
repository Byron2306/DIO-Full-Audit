#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.serve_market_command import Handler  # noqa: E402


class MS10MarketCommandHandler(Handler):
    server_version = "DIOMarketWorkbench/2.0"

    def _product_choices(self) -> dict:
        path = ROOT / "state" / "product_portfolio" / "DIO_META_PORTFOLIO_ATLAS_IMPORT.json"
        if not path.is_file():
            return {"state": "not_imported", "products": []}
        registry = json.loads(path.read_text(encoding="utf-8"))
        products = []
        for row in registry.get("incarnations") or []:
            name = str(row.get("Incarnation") or row.get("Product") or row.get("name") or "").strip()
            if not name:
                continue
            products.append({
                "id": name,
                "name": name,
                "family": row.get("Suite") or row.get("Product Family") or row.get("Family") or "",
                "maturity": row.get("Maturity") or row.get("Readiness") or "",
            })
        return {"state": "imported", "count": len(products), "products": products}

    def do_GET(self) -> None:
        route = urlsplit(self.path).path
        if route == "/api/market/products":
            self.send_json(self._product_choices())
            return
        if route == "/":
            self.path = "/dashboard/market.html"
        super().do_GET()


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve DIO MARKET operator workbench")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("DIO MARKET must bind to localhost")
    server = ThreadingHTTPServer((args.host, args.port), MS10MarketCommandHandler)
    print(f"DIO MARKET: http://{args.host}:{args.port}")
    print("Campaign journey + Sensorium intelligence: ACTIVE")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
