#!/usr/bin/env python3
"""Deliver one approved Vesper return manifest to its authenticated web portal."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from presence_core.deliverable_release_v2 import deliver_manifest  # noqa: E402
from presence_core.web_package_transport import web_portal_transport  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("authority_id")
    parser.add_argument("--state-root", type=Path, default=Path(os.getenv("DIO_VESPER_PRESENCE_ROOT", ROOT / "state" / "presence")))
    args = parser.parse_args()
    try:
        result = deliver_manifest(
            args.state_root.expanduser().resolve(),
            args.authority_id,
            channel="web_portal",
            destination="authenticated_customer_session",
            transport=web_portal_transport(args.state_root),
        )
        receipt = result.get("delivery_receipt") or {}
        print(json.dumps({
            "schema": "dio.vesper_web_package_delivery_command.v1",
            "delivered": result.get("delivered") is True,
            "delivery_receipt_id": receipt.get("delivery_receipt_id"),
            "delivery_receipt_sha256": receipt.get("delivery_receipt_sha256"),
            "case_id": receipt.get("case_id"),
            "manifest_sha256": receipt.get("manifest_sha256"),
            "customer_download_available": result.get("delivered") is True,
            "external_effects": result.get("delivered") is True,
        }, indent=2, sort_keys=True))
        return 0 if result.get("delivered") is True else 2
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"schema": "dio.vesper_web_package_delivery_command.v1", "delivered": False,
                          "error": str(exc)[:300], "customer_download_available": False}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
