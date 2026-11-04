#!/usr/bin/env python3
"""Run four held obligation-family customer examples with byte-linked source quotes."""
from __future__ import annotations

import hashlib
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "acceptance_runs/68-product-sellability-20261027/OBLIGATION_FAMILY_CUSTOMER_EXECUTIONS_20261102_V2"
PRODUCTS = ("GrantProof", "PermitProof", "PolicyProof", "TenderProof")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f"output directory must be new or empty: {OUT}")
    from products.customer_product_router import run_customer_product

    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for product in PRODUCTS:
        slug = product.casefold()
        packet_path = ROOT / f"config/customer_products/examples/{slug}.json"
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        output_dir = OUT / slug
        run_customer_product(product, packet, output_dir, render_pdf=True)
        wrapper = json.loads((output_dir / "CUSTOMER_EXECUTION_RECEIPT.json").read_text(encoding="utf-8"))
        package_path = output_dir / "CUSTOMER_OBLIGATION_FAMILY_RECEIPT.json"
        package = json.loads(package_path.read_text(encoding="utf-8"))
        pack_path = output_dir / "evidence_pack/EVIDENCE_PACK.json"
        html_path = output_dir / "evidence_pack/EVIDENCE_PACK.html"
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
        instrument_path = output_dir / "customer_sources/governing_instrument.txt"
        instrument = instrument_path.read_bytes()
        instrument_text = instrument.decode("utf-8")
        clause_rows = pack.get("provenance_manifest", {}).get("source_clause_sources") or []
        if len(clause_rows) != package.get("obligation_candidate_count"):
            raise ValueError(f"{product}: not every obligation candidate has a source provenance row")
        validated_matches = 0
        for row in clause_rows:
            quote = str(row.get("text") or "")
            if (row.get("source_file_ref") != "customer_sources/governing_instrument.txt"
                    or row.get("source_file_sha256") != sha(instrument)
                    or row.get("source_statement_sha256") != sha(quote.encode("utf-8"))
                    or row.get("source_match_count") != len(row.get("source_matches") or [])):
                raise ValueError(f"{product} {row.get('clause_id')}: quote source binding is incomplete")
            for match in row.get("source_matches") or []:
                start, end = int(match["byte_start"]), int(match["byte_end_exclusive"])
                if (instrument[start:end].decode("utf-8") != quote
                        or instrument_text[int(match["character_start"]):int(match["character_end_exclusive"])] != quote
                        or sha(instrument[start:end]) != row.get("source_statement_sha256")):
                    raise ValueError(f"{product} {row.get('clause_id')}: byte or character span does not reproduce the quote")
                validated_matches += 1
        page = html.unescape(html_path.read_text(encoding="utf-8"))
        if ("Exact source byte provenance" not in page
                or any(str(row.get("text") or "") not in page for row in clause_rows)):
            raise ValueError(f"{product}: customer HTML report does not display the bound exact source quotes")
        if (wrapper.get("requested_product") != product
                or package.get("human_review_required") is not True
                or package.get("evidence_sufficiency_state") != "GAPS_PRESENT"
                or package.get("external_release") != "REFUSE"
                or package.get("legal_opinion_created") is not False
                or package.get("award_or_permit_decision_created") is not False):
            raise ValueError(f"{product}: route crossed the human/release boundary")
        artifacts = {
            path.relative_to(output_dir).as_posix(): sha(path.read_bytes())
            for path in sorted(output_dir.rglob("*")) if path.is_file()
        }
        results.append({
            "product_name": product,
            "status": "EXECUTED",
            "source_packet": packet_path.relative_to(ROOT).as_posix(),
            "customer_output_dir": output_dir.relative_to(ROOT).as_posix(),
            "source_sha256": package.get("source_sha256"),
            "candidate_count": package.get("obligation_candidate_count"),
            "source_quote_match_count": validated_matches,
            "evidence_sufficiency_state": package.get("evidence_sufficiency_state"),
            "human_review_required": package.get("human_review_required"),
            "external_release": package.get("external_release"),
            "artifacts": artifacts,
        })
    receipt = {
        "schema": "dio.obligation_family.source_location_batch.v1",
        "created_at": "2026-11-02",
        "synthetic_acceptance_inputs_only": True,
        "source_provenance_scope": "Every exact candidate quote is bound to the saved governing instrument by source hash, UTF-8 byte span, character span, line coordinates, and quote hash; repeated occurrences are all enumerated and flagged for review.",
        "human_review_required": True,
        "results": results,
        "summary": {"executed": len(results), "failed": 0,
                    "candidates": sum(row["candidate_count"] for row in results),
                    "verified_source_quote_matches": sum(row["source_quote_match_count"] for row in results)},
    }
    receipt_path = OUT / "SOURCE_LOCATION_BATCH_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(receipt["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
