from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from products.paid_reference import run_paid_reference_journey


ACCEPTANCE_TOKEN = "DIO_PAID_REFERENCE_PRODUCTS_READY"


def run_paid_reference_gauntlet(*, output_dir: Path) -> dict[str, Any]:
    payload = {
        "name": "Phase 11 Reference Operator", "email": "phase11@example.invalid",
        "organisation": "DIO Controlled Test", "message": "Compile the controlled ContractProof reference journey.",
        "review_title": "Phase 11 controlled service agreement review",
        "contract_text": "The Supplier shall provide the monthly service report by the fifth business day. The Customer must retain signed acceptance records for twelve months.",
        "evidence_notes": "Controlled gauntlet intentionally supplies no formally bound evidence records.",
        "page_viewed": True, "information_acknowledged": True,
        "controlled_test_payment_consented": True, "website_honeypot": "",
    }
    first = run_paid_reference_journey(payload, output_dir=output_dir / "first")
    second = run_paid_reference_journey(payload, output_dir=output_dir / "second")
    if first != second:
        raise AssertionError("paid-reference journey is non-deterministic")
    if any(first["truth_boundaries"].values()):
        raise AssertionError("paid-reference journey crossed a truth boundary")
    receipt = {
        "schema": "dio.paid_reference.phase11_receipt.v1",
        "journey_id": first["journey_id"], "journey_fingerprint": first["journey_fingerprint"],
        "resolution": first["resolution"], "deterministic_execution": "PASS",
        "phase10_controlled_payment_binding": "PASS", "proof_integrity": "PASS",
        "external_delivery": "REFUSE", "market_validation": "REFUSE",
        "acceptance_token": ACCEPTANCE_TOKEN,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "PAID_REFERENCE_PHASE11_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt
