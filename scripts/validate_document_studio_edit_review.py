#!/usr/bin/env python3
"""Validate a returned source-bound Document Studio technical edit review."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.document_studio_edit_review import validate_technical_edit_review


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path, help="Native Document Studio job directory")
    parser.add_argument("--csv", type=Path, help="Completed copy of TECHNICAL_EDIT_REVIEW_TEMPLATE.csv")
    parser.add_argument("--output", type=Path, help="Validation receipt; defaults beside the review CSV")
    args = parser.parse_args()
    run_dir = args.run_dir.expanduser().resolve()
    receipt_path = run_dir / "DOCUMENT_STUDIO_RECEIPT.json"
    ledger_path = run_dir / "CHANGE_LEDGER.csv"
    if not receipt_path.is_file() or not ledger_path.is_file():
        parser.error("run directory must contain DOCUMENT_STUDIO_RECEIPT.json and CHANGE_LEDGER.csv")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("service") not in {"technical_edit", "edit_and_translate"} or receipt.get("processing", {}).get("remote_inference_used") is not False:
        parser.error("source job is not a locally processed technical edit run")
    outputs = {str(row.get("path") or ""): str(row.get("sha256") or "") for row in receipt.get("outputs") or []}
    if outputs.get("CHANGE_LEDGER.csv") != __import__("hashlib").sha256(ledger_path.read_bytes()).hexdigest():
        parser.error("source change ledger is not bound by the native job receipt")
    csv_path = args.csv.expanduser().resolve() if args.csv else run_dir / "TECHNICAL_EDIT_REVIEW_TEMPLATE.csv"
    if not csv_path.is_file():
        parser.error("technical editor review CSV is missing")
    result = validate_technical_edit_review(csv_path, ledger_path)
    result.update({
        "source_run_dir": str(run_dir),
        "source_job_id": receipt.get("job_id"),
        "source_receipt_sha256": __import__("hashlib").sha256(receipt_path.read_bytes()).hexdigest(),
        "source_change_ledger_sha256": __import__("hashlib").sha256(ledger_path.read_bytes()).hexdigest(),
        "release_authorized": False,
    })
    output = args.output.expanduser().resolve() if args.output else csv_path.with_name("TECHNICAL_EDIT_REVIEW_VALIDATION.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"state": result["state"], "expected_paragraph_count": result.get("expected_paragraph_count"),
                      "matched_paragraph_count": result.get("matched_paragraph_count"), "issues": len(result.get("issues") or []),
                      "client_approval_required": result.get("client_approval_required", True),
                      "release_authorized": False, "receipt": str(output)}, indent=2))
    return 0 if not result.get("issues") else 2


if __name__ == "__main__":
    raise SystemExit(main())
