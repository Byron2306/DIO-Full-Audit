#!/usr/bin/env python3
from __future__ import annotations

import argparse
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.serve_control_deck import ControlDeckHandler  # noqa: E402


class MS10ControlDeckHandler(ControlDeckHandler):
    server_version = "DIOBusinessWorkbench/1.0"

    def do_GET(self) -> None:
        if urlsplit(self.path).path == "/":
            self.path = "/dashboard/business.html"
        super().do_GET()


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve DIO BUSINESS operator workbench")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("DIO BUSINESS must bind to localhost")
    server = ThreadingHTTPServer((args.host, args.port), MS10ControlDeckHandler)
    print(f"DIO BUSINESS: http://{args.host}:{args.port}")
    print("Human operator workbench: ACTIVE · existing action plane preserved")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
