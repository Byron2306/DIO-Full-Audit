#!/usr/bin/env python3
"""Run a synthetic source-scope comparison through the Evidex review product."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "acceptance_runs/68-product-sellability-20261027/EVIDEX_SCOPE_COMPARABILITY_DEMO_20261104_V6"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f"output directory must be new or empty: {OUT}")
    OUT.mkdir(parents=True, exist_ok=True, mode=0o700)
    claims = [
        ("claim-2025", "Claim C-2025 reports 10 workshops delivered.", "2025-01-01", "2025-12-31", "programme-A"),
        ("register-match", "Attendance register records 9 workshops delivered.", "2025-01-01", "2025-12-31", "programme-A"),
        ("register-mismatch", "Attendance register records 9 workshops delivered.", "2024-01-01", "2024-12-31", "programme-A"),
        ("register-unknown", "Attendance register records 9 workshops delivered.", None, None, None),
    ]
    packet = {
        "owner_authorized": True,
        "case_id": "SYNTHETIC-EVIDEX-SCOPE-COMPARABILITY",
        "title": "Synthetic Evidex period and population comparison",
        "organisation": "Synthetic QA fixture",
        "sources": [{"source_id": row[0], "title": row[0], "text": row[1]} for row in claims],
        "records": [{"record_id": row[0], "source_id": row[0], "quote": row[1], "period_start": row[2],
                     "period_end": row[3], "population_id": row[4]} for row in claims],
        "controlled_synthetic_demo": True,
    }
    from products.customer_product_router import run_customer_product

    execution = run_customer_product("Evidex EvidenceOps", packet, OUT, render_pdf=False)
    review_path = OUT / "CUSTOMER_EVIDENCE_REVIEW.json"
    review = json.loads(review_path.read_text(encoding="utf-8"))
    comparisons = review["quantity_comparisons"]
    match = next(row for row in comparisons if row["candidate_record_id"] == "register-match")
    mismatch = next(row for row in comparisons if row["candidate_record_id"] == "register-mismatch")
    unknown = next(row for row in comparisons if row["candidate_record_id"] == "register-unknown")
    mismatch_request = next(row for row in review["review_actions"] if row.get("record_id") == "register-mismatch" and row.get("reason") == "QUANTITY_RECONCILIATION")
    unknown_request = next(row for row in review["review_actions"] if row.get("record_id") == "register-unknown" and row.get("reason") == "QUANTITY_RECONCILIATION")
    if (match.get("declared_scope_match") is not True
            or match.get("state") != "DECLARED_SCOPE_MATCH_QUANTITY_DIFFERENCE_REQUIRES_REVIEW"
            or mismatch.get("declared_scope_match") is not False
            or mismatch.get("difference") is not None
            or mismatch.get("difference_basis") is not None
            or mismatch.get("state") != "DECLARED_SCOPE_INCOMPARABLE_REVIEW_REQUIRED"
            or mismatch.get("claim_scope", {}).get("period_start") == mismatch.get("candidate_record_scope", {}).get("period_start")
            or unknown.get("declared_scope_match") is not False
            or unknown.get("difference") is not None
            or unknown.get("difference_basis") is not None
            or unknown.get("state") != "DECLARED_SCOPE_INCOMPARABLE_REVIEW_REQUIRED"
            or not any("coverage start and end dates" in field for field in mismatch_request.get("requested_evidence", []))
            or not any("population/program identifier" in field for field in mismatch_request.get("requested_evidence", []))
            or not any("coverage start and end dates" in field for field in unknown_request.get("requested_evidence", []))
            or not any("population/program identifier" in field for field in unknown_request.get("requested_evidence", []))
            or review.get("support_adjudicated") is not False
            or review.get("release_authorized") is not False):
        raise ValueError("Evidex scope comparability review failed its match/mismatch or held boundary")
    evidence = {
        "schema": "dio.evidex.scope_comparability_execution.v1",
        "product": "Evidex EvidenceOps",
        "review_path": review_path.relative_to(ROOT).as_posix(),
        "review_sha256": sha(review_path),
        "evidence_requests_sha256": sha(OUT / "EVIDENCE_REQUESTS.csv"),
        "evidence_request_count": len(review["review_actions"]),
        "customer_package_sha256": sha(OUT / "CUSTOMER_PACKAGE_RECEIPT.json"),
        "customer_execution_sha256": sha(OUT / "CUSTOMER_EXECUTION_RECEIPT.json"),
        "source_count": len(review["source_records"]),
        "comparison_count": len(comparisons),
        "declared_scope_match_count": sum(row["declared_scope_match"] for row in comparisons),
        "noncomparable_record_count": sum(not row["declared_scope_match"] for row in comparisons),
        "difference_remains_unverified": match["state"] == "DECLARED_SCOPE_MATCH_QUANTITY_DIFFERENCE_REQUIRES_REVIEW",
        "support_adjudicated": False,
        "human_review_required": True,
        "release_authorized": False,
        "external_effects": execution.get("external_effects", False),
        "fixture_boundary": "Synthetic customer-declared dates, population labels and quantities exercise the comparability logic; they do not verify record authenticity or delivery.",
    }
    evidence_path = OUT / "EVIDEX_SCOPE_COMPARABILITY_EXECUTION_EVIDENCE.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
