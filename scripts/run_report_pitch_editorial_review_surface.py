#!/usr/bin/env python3
"""Run Report & Pitch Studio and capture its guided, held editorial handoff."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "acceptance_runs/68-product-sellability-20261027/REPORT_PITCH_SOURCE_BYTE_LINEAGE_20261102_V2"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    from products.professional_evidence_execution import execute_customer_case

    result = execute_customer_case("Report & Pitch Studio", OUT, operator_id="report-pitch-editorial-review-surface")
    case_root = OUT / "report-pitch-studio" / "report-pitch-studio"
    receipt_path = case_root / "PROFESSIONAL_EVIDENCE_RECEIPT.json"
    package_root = case_root / "EXECUTION" / "report_pitch_studio"
    page = package_root / "EDITORIAL_REVIEW.html"
    validation_path = package_root / "EDITORIAL_REVIEW_VALIDATION.json"
    worksheet = package_root / "EDITORIAL_REVIEW_WORKSHEET.csv"
    bindings = package_root / "REPORT_PITCH_SOURCE_BYTE_BINDINGS.json"
    manifest_path = package_root / "package_manifest.json"
    archive_path = package_root / "controlled_review_package.zip"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    with worksheet.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    artifacts = {row.get("path"): row.get("sha256") for row in manifest.get("artifacts") or []}
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
    required = {"EDITORIAL_REVIEW.html", "EDITORIAL_REVIEW_VALIDATION.json", "EDITORIAL_REVIEW_WORKSHEET.csv"}
    binding_doc = json.loads(bindings.read_text(encoding="utf-8"))
    checks = {
        "route_passed": receipt.get("status") == "PASS_FULL_PIPELINE",
        "source_claims_bound": json.loads((package_root / "REPORT_PITCH_SOURCE_BYTE_BINDINGS_RECEIPT.json").read_text()).get("all_claims_bind_to_exact_customer_register_rows") is True,
        "review_items_present": len(rows) > 0,
        "all_claim_rows_bound": all(any(b.get("claim_id") == row.get("item_id") for b in binding_doc.get("bindings") or [])
                                    for row in rows if row.get("item_type") == "claim"),
        "blank_review_held": validation.get("state") == "REVIEW_INCOMPLETE_OR_HOLD_REQUIRED",
        "publication_refused": receipt.get("external_publication") == "REFUSE" and validation.get("publication_authorized") is False,
        "manifest_binds_surface": artifacts.get("EDITORIAL_REVIEW.html") == sha(page) and artifacts.get("EDITORIAL_REVIEW_VALIDATION.json") == sha(validation_path),
        "controlled_zip_contains_surface": required.issubset(names),
    }
    if not all(checks.values()):
        raise RuntimeError(f"Report & Pitch editorial review surface checks failed: {checks}")
    evidence = {
        "schema": "dio.report_pitch.editorial_review_surface_evidence.v1",
        "run": OUT.relative_to(ROOT).as_posix(),
        "customer_route_receipt_sha256": sha(receipt_path),
        "review_page_sha256": sha(page), "worksheet_sha256": sha(worksheet),
        "source_bindings_sha256": sha(bindings), "validation_sha256": sha(validation_path),
        "manifest_sha256": sha(manifest_path), "controlled_review_zip_sha256": sha(archive_path),
        "review_item_count": len(rows), "source_claim_binding_count": len(binding_doc.get("bindings") or []),
        "blank_validation_state": validation.get("state"), "publication_gate": receipt.get("external_publication"),
        "checks": checks, "synthetic_acceptance_input": True,
    }
    evidence_path = OUT / "REPORT_PITCH_EDITORIAL_REVIEW_SURFACE_EVIDENCE.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
