#!/usr/bin/env python3
"""Run fresh official-source snapshots through the catalog FundingFinder route."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PACKET_SOURCE = ROOT / "acceptance_runs/68-product-sellability-20261027/funding-finder/reviewed/official-refresh-20261104-v3/packets/south-africa-moya-live-snapshot.json"
PACKET_PATH = ROOT / "acceptance_runs/68-product-sellability-20261027/FUNDINGFINDER_LIVE_CUSTOMER_ROUTE_PACKET_20261104_V3.json"
OUTPUT = ROOT / "acceptance_runs/68-product-sellability-20261027/FUNDINGFINDER_LIVE_CUSTOMER_ROUTE_20261104_V3"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    packet = json.loads(PACKET_SOURCE.read_text(encoding="utf-8"))
    packet["owner_authorized"] = True
    packet["synthetic_acceptance_not_customer_evidence"] = True
    PACKET_PATH.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise ValueError(f"output directory must be new or empty: {OUTPUT}")
    from products.customer_product_router import run_customer_product

    result = run_customer_product("FundingFinder", packet, OUTPUT, render_pdf=True)
    receipt = result.get("receipt") or {}
    if (result.get("requested_product") != "FundingFinder" or result.get("human_review_required") is not True
            or result.get("release_authorized") is not False or result.get("external_effects") is not False
            or result.get("commercial_validation") != "UNPROVED"):
        raise ValueError("FundingFinder customer route crossed its review, external-effect or qualification boundary")
    if (receipt.get("as_of") != "2026-11-04" or receipt.get("processing", {}).get("public_fetch_enabled") is not False
            or receipt.get("release", {}).get("eligibility_certified") is not False
            or receipt.get("release", {}).get("award_guaranteed") is not False
            or receipt.get("release", {}).get("application_submitted") is not False
            or receipt.get("release", {}).get("externally_sent") is not False):
        raise ValueError("FundingFinder customer route is not bound to the offline source snapshots or safe-release contract")
    rows = receipt.get("shortlist") or []
    if len(rows) != 2 or any(row.get("fit_state") != "unknown_review_required" or row.get("timing_state") != "unknown" for row in rows):
        raise ValueError("Synthetic applicant route must preserve unknown NYDA/TIA eligibility and timing")
    inventory = result.get("artifacts") or []
    for row in inventory:
        path = OUTPUT / row["path"]
        if not path.is_file() or path.stat().st_size != row["bytes"] or sha(path) != row["sha256"]:
            raise ValueError(f"FundingFinder customer execution artifact failed its hash/size inventory: {row['path']}")
    print(json.dumps({
        "execution_receipt": (OUTPUT / "CUSTOMER_EXECUTION_RECEIPT.json").relative_to(ROOT).as_posix(),
        "execution_receipt_sha256": sha(OUTPUT / "CUSTOMER_EXECUTION_RECEIPT.json"),
        "customer_packet": PACKET_PATH.relative_to(ROOT).as_posix(),
        "customer_packet_sha256": sha(PACKET_PATH),
        "artifact_count": len(inventory),
        "opportunity_count": len(rows),
        "all_outputs_hash_verified": True,
        "eligibility_certified": False,
        "application_submitted": False,
        "product_qualification": "UNPROVED",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
