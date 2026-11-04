#!/usr/bin/env python3
"""Refresh Market Radar's manifest-bound customer case through pinned HTTPS."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE = ROOT / "acceptance_runs/68-product-sellability-20261027"
SOURCE_PACKET = BASE / "NATIVE_PACKET_CUSTOMER_EXECUTIONS_20261102_V1/market-radar/CUSTOMER_PACKET"
OUTPUT = BASE / "MARKET_RADAR_CUSTOMER_EXECUTION_20261104_V3"
EVIDENCE = BASE / "MARKET_RADAR_CUSTOMER_EXECUTION_20261104_V3.json"
EXPECTED = {"ZA-COMPLY-001", "ZA-FILESAFE-001", "ZA-CAPECOM-001"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if not SOURCE_PACKET.is_dir():
        raise ValueError(f"manifest-bound customer packet is missing: {SOURCE_PACKET}")
    from products.market_radar_research import _VisibleText, _market_facts
    route_receipt_path = OUTPUT / "NATIVE_CUSTOMER_PACKET_RECEIPT.json"
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        if not route_receipt_path.is_file():
            raise ValueError(f"existing Market Radar execution is incomplete: {OUTPUT}")
        result = json.loads(route_receipt_path.read_text(encoding="utf-8"))
    else:
        from products.native_customer_runner import run_native_customer_packet
        result = run_native_customer_packet("Market Radar", {
            "owner_authorized": True,
            "customer_packet_dir": str(SOURCE_PACKET),
            "as_of": "2026-11-04",
        }, OUTPUT)
    if (result.get("product_name") != "Market Radar"
            or result.get("terminal_artifact_kind") != "source_bound_market_brief"
            or result.get("native_receipt", {}).get("source_count") != 3
            or result.get("native_receipt", {}).get("source_failures")
            or result.get("native_receipt", {}).get("market_demand_claimed") is not False
            or result.get("native_receipt", {}).get("authority_created") is not False
            or result.get("native_receipt", {}).get("external_effects") is not False):
        raise ValueError("Market Radar customer route failed its source or release-boundary contract")

    execution = OUTPUT / "EXECUTION"
    brief_path = execution / "MARKET_RADAR_TARGET_BRIEF.json"
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    by_id = {row.get("source_id"): row for row in brief.get("sources") or []}
    if set(by_id) != EXPECTED or brief.get("source_count") != len(EXPECTED) or brief.get("source_failures"):
        raise ValueError("Market Radar did not capture all three customer-scoped sources")
    source_records = []
    for source_id, row in sorted(by_id.items()):
        raw = Path(row.get("raw_path") or "").resolve()
        if (not raw.is_file() or not raw.is_relative_to(execution.resolve())
                or row.get("http_status") != 200
                or row.get("transport") != "HTTPS public-IP-pinned GET; TLS hostname verified; redirects refused"
                or not row.get("resolved_ip")
                or sha(raw) != row.get("raw_sha256")
                or raw.stat().st_size != row.get("raw_bytes")):
            raise ValueError(f"Market Radar source capture is not verified: {source_id}")
        parser = _VisibleText()
        parser.feed(raw.read_text(encoding="utf-8", errors="replace"))
        visible_text = " ".join(" ".join(parser.parts).split())
        if _market_facts(row, visible_text) != row.get("facts"):
            raise ValueError(f"Stored public-signal facts do not reproduce from source bytes: {source_id}")
        source_records.append({
            "source_id": source_id,
            "url": row["url"],
            "source_class": row["source_class"],
            "captured_at": row["captured_at"],
            "resolved_ip": row["resolved_ip"],
            "transport": row["transport"],
            "raw_path": raw.relative_to(ROOT).as_posix(),
            "raw_sha256": sha(raw),
            "fact_count": len(row.get("facts") or []),
            "facts_reproduced_from_capture": True,
        })
    all_outputs = result.get("artifacts") or []
    for item in all_outputs:
        path = OUTPUT / item["path"]
        if not path.is_file() or path.stat().st_size != item["bytes"] or sha(path) != item["sha256"]:
            raise ValueError(f"Market Radar output failed manifest hash/size verification: {item['path']}")

    report = {
        "schema": "dio.market_radar.ip_pinned_customer_refresh_evidence.v1",
        "product": "Market Radar",
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "synthetic_acceptance_case": result.get("synthetic_acceptance_case"),
        "customer_context_authenticated": False,
        "source_packet": str(SOURCE_PACKET.relative_to(ROOT)),
        "execution": str(OUTPUT.relative_to(ROOT)),
        "execution_receipt_sha256": sha(route_receipt_path),
        "brief_sha256": sha(brief_path),
        "source_count": len(source_records),
        "source_records": source_records,
        "output_count": len(all_outputs),
        "all_output_hashes_and_sizes_verified": True,
        "all_extracted_facts_reproduced_from_source_bytes": True,
        "market_demand_claimed": False,
        "customer_outreach_performed": False,
        "spend_authorized": False,
        "authority_created": False,
        "external_effects": False,
        "product_qualification": "UNPROVED",
        "limitations": [
            "Vendor feature and list-price claims were observed on vendor pages; they are not independently verified product performance or a complete market census.",
            "The business-survey signals are contextual and do not establish demand, market size, willingness to pay, competitor rank or product-market fit.",
            "The supplied customer context was not independently authenticated; no interviews or outreach were performed.",
        ],
    }
    EVIDENCE.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"execution": report["execution"], "evidence": EVIDENCE.relative_to(ROOT).as_posix(), "source_count": len(source_records), "fact_reproduction": True, "all_outputs_hash_verified": True, "qualification": "UNPROVED"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
