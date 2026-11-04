#!/usr/bin/env python3
"""Regenerate source-aligned customer review packages for the four obligation-family products."""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKETS = {
    "GrantProof": ("grantproof", "GRANTPROOF_SOURCE_ALIGNED_REVIEW_20261104_V5"),
    "PermitProof": ("permitproof", "PERMITPROOF_SOURCE_ALIGNED_REVIEW_20261104_V1"),
    "PolicyProof": ("policyproof", "POLICYPROOF_SOURCE_ALIGNED_REVIEW_20261104_V1"),
    "TenderProof": ("tenderproof", "TENDERPROOF_SOURCE_ALIGNED_REVIEW_20261104_V1"),
}
sys.path.insert(0, str(ROOT))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_and_render(product: str, example: str, output_name: str) -> dict:
    source = ROOT / f"config/customer_products/examples/{example}.json"
    out = ROOT / f"acceptance_runs/68-product-sellability-20261027/{output_name}"
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"output directory must be new or empty: {out}")
    packet = json.loads(source.read_text(encoding="utf-8"))
    from products.customer_product_router import run_customer_product
    result = run_customer_product(product, packet, out)
    evidence_pack_root = out / "evidence_pack"
    pack_path = evidence_pack_root / "EVIDENCE_PACK.json"
    package_path = out / "CUSTOMER_OBLIGATION_FAMILY_RECEIPT.json"
    execution_path = out / "CUSTOMER_EXECUTION_RECEIPT.json"
    pack, package, execution = map(lambda path: json.loads(path.read_text(encoding="utf-8")),
                                   (pack_path, package_path, execution_path))
    obligations = pack.get("requirement_or_obligation_ledger") or []
    evidence_maps = pack.get("evidence_map") or []
    locator_by_id = {row.get("obligation_id"): (row.get("source") or {}).get("locator") for row in obligations}
    actual_relations = Counter((locator_by_id.get(row.get("obligation_id")), row.get("relation")) for row in evidence_maps)
    expected_relations = Counter((target, row.get("relation"))
                                 for row in packet.get("evidence") or []
                                 for target in row.get("target_locators") or [])
    provenance = pack.get("provenance_manifest") or {}
    clause_sources = provenance.get("source_clause_sources") or []
    evidence_sources = provenance.get("evidence_input_sources") or []
    source_bytes = (out / "customer_sources/governing_instrument.txt").read_bytes()
    for row in clause_sources:
        start, end = row.get("source_byte_start"), row.get("source_byte_end_exclusive")
        if (start is None or end is None or row.get("source_match_state") != "UNIQUE_EXACT_MATCH"
                or source_bytes[start:end].decode("utf-8") != row.get("text")):
            raise ValueError(f"{product} source clause is not uniquely byte-bound: {row.get('clause_id')}")
    for row in evidence_sources:
        evidence_path = out / str(row.get("source_file_ref") or "")
        evidence_bytes = evidence_path.read_bytes()
        actual_hash = hashlib.sha256(evidence_bytes).hexdigest()
        if (row.get("source_byte_start") != 0 or row.get("source_byte_end_exclusive") != len(evidence_bytes)
                or row.get("source_file_sha256") != actual_hash or row.get("source_row_sha256") != actual_hash
                or row.get("source_statement_sha256") != actual_hash):
            raise ValueError(f"{product} applicant evidence file is not byte-bound: {row.get('record_id')}")
    artifact_rows = package.get("artifacts") or []
    if any(sha(out / row["path"]) != row.get("sha256") for row in artifact_rows):
        raise ValueError(f"{product} customer package contains a declared hash mismatch")
    if (package.get("product_name") != product or package.get("source_sha256") != sha(out / "customer_sources/governing_instrument.txt")
            or len(obligations) != len(packet.get("obligations") or [])
            or len(evidence_maps) != len(packet.get("evidence") or [])
            or actual_relations != expected_relations or len(clause_sources) != len(packet.get("obligations") or [])
            or len(evidence_sources) != len(packet.get("evidence") or [])
            or any((row.get("evaluation") or {}).get("status") != "NEEDS_REVIEW" for row in obligations)
            or package.get("external_release") != "REFUSE" or package.get("authority_created") is not False
            or execution.get("external_effects") is not False or result.get("release_authorized") is not False
            or not all((evidence_pack_root / f"EVIDENCE_PACK.{ext}").is_file() for ext in ("pdf", "docx", "html"))):
        raise ValueError(f"{product} source/evidence alignment or human-review boundary is incomplete")
    evidence = {
        "schema": "dio.obligation_family.source_aligned_review.v1",
        "product": product,
        "source_packet_sha256": sha(source),
        "customer_package_receipt_sha256": sha(package_path),
        "evidence_pack_sha256": sha(pack_path),
        "requirement_count": len(obligations),
        "evidence_mapping_count": len(evidence_maps),
        "source_clause_byte_spans_verified": len(clause_sources),
        "applicant_evidence_file_byte_spans_verified": len(evidence_sources),
        "evidence_relations_match_packet": actual_relations == expected_relations,
        "all_items_need_human_review": all((row.get("evaluation") or {}).get("status") == "NEEDS_REVIEW" for row in obligations),
        "professional_approval": "NOT_GRANTED",
        "external_release": "REFUSE",
        "external_effects": False,
        "artifact_count": len(artifact_rows),
        "synthetic_fixture": packet.get("synthetic_acceptance_not_customer_evidence") is True,
        "claim_boundary": package.get("claim_boundary"),
    }
    evidence_path = out / f"{example.upper()}_SOURCE_ALIGNMENT_EVIDENCE.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return evidence


def main() -> int:
    rows = [validate_and_render(product, *spec) for product, spec in PACKETS.items()]
    print(json.dumps({"product_count": len(rows), "products": rows}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
