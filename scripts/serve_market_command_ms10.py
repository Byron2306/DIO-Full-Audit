#!/usr/bin/env python3
from __future__ import annotations

import argparse
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.serve_market_command import Handler  # noqa: E402


class MS10MarketCommandHandler(Handler):
    server_version = "DIOMarketWorkbench/1.0"

    def do_GET(self) -> None:
        if urlsplit(self.path).path == "/":
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
    print("Campaign action plane + Sensorium intelligence: ACTIVE")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
