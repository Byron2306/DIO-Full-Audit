#!/usr/bin/env python3
"""Read-only canonical portfolio identity service."""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from products.commercial_pricing_registry import build_commercial_pricing_registry

SNAPSHOT = ROOT / "state/product_portfolio/DIO_META_PORTFOLIO_ATLAS_IMPORT.json"


def portfolio_state():
    registry = build_commercial_pricing_registry(ROOT)
    products = registry["products"]

    identities = [
        {
            "product_id": row["product_id"],
            "name": row["name"],
            "suite": row.get("suite"),
            "canon_source": row.get("canon_source"),
            "pricing_state": row.get("pricing_state"),
            "commercial_validation": row.get("commercial_validation"),
        }
        for row in products
    ]

    ids = [row["product_id"] for row in identities]

    if len(ids) != 68 or len(set(ids)) != 68:
        raise ValueError("Canonical portfolio identity contract failed")

    runtime = {
        "snapshot_available": False,
        "incarnation_count": 0,
        "extension_summary_state": "UNKNOWN",
    }

    if SNAPSHOT.is_file():
        try:
            snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
            rows = snapshot.get("incarnations", [])
            runtime = {
                "snapshot_available": True,
                "incarnation_count": len(rows),
                "extension_summary_state": snapshot.get(
                    "extension_summary_state", "UNKNOWN"
                ),
            }
        except (OSError, ValueError, TypeError):
            runtime["extension_summary_state"] = "INVALID"

    return {
        "schema": "dio.canonical_portfolio_operator_view.v1",
        "canonical_identity_count": 68,
        "historical_53_count": 53,
        "canon_extension_count": 15,
        "identity_registry_complete": True,
        "runtime": runtime,
        "product_grade_verified": (
            runtime["incarnation_count"] == 68
            and runtime["extension_summary_state"] == "VERIFIED"
        ),
        "external_release_authorized": False,
        "authority_created": False,
        "external_effects": False,
        "products": identities,
    }


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        route = urlsplit(self.path).path

        if route not in ("/api/canonical/portfolio", "/api/canonical/health"):
            return self.send_json(404, {"error": "not_found"})

        try:
            state = portfolio_state()
        except (OSError, ValueError, KeyError, TypeError):
            return self.send_json(
                503,
                {
                    "error": "canonical_registry_unavailable",
                    "authority_created": False,
                    "external_effects": False,
                },
            )

        if route == "/api/canonical/health":
            return self.send_json(
                200,
                {
                    "ok": True,
                    "canonical_identity_count": state["canonical_identity_count"],
                    "runtime": state["runtime"],
                    "product_grade_verified": state["product_grade_verified"],
                },
            )

        return self.send_json(200, state)

    def do_POST(self):
        self.send_json(
            405,
            {
                "error": "read_only_service",
                "authority_created": False,
                "external_effects": False,
            },
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8768)
    args = parser.parse_args()

    if args.host not in ("127.0.0.1", "localhost"):
        parser.error("Only loopback binding is permitted")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"DIO canonical portfolio listening on {args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
