#!/usr/bin/env python3
from __future__ import annotations

import argparse
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

from scripts.serve_control_deck import ControlDeckHandler


class GoldenEyeHandler(ControlDeckHandler):
    """Use the existing governed control API, but make GoldenEye the root cockpit."""

    server_version = "DIOGoldenEye/1.0"

    def do_GET(self) -> None:
        if urlsplit(self.path).path == "/":
            self.path = "/dashboard/goldeneye.html"
        super().do_GET()


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the localhost-only DIO GoldenEye operator cockpit.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("GoldenEye must bind to localhost.")
    server = ThreadingHTTPServer((args.host, args.port), GoldenEyeHandler)
    print(f"DIO GoldenEye: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
