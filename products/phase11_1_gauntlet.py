from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from products.phase11_1 import run_attachment_delivery_journey


ACCEPTANCE_TOKEN = "DIO_PHASE11_1_1_EVIDENCE_RECONCILIATION_READY"


def _attachment(name: str, text: str, role: str) -> dict[str, Any]:
    return {"filename": name, "mime_type": "text/plain", "role": role, "content_base64": base64.b64encode(text.encode()).decode()}


def run_phase11_1_gauntlet(*, output_dir: Path, root: Path) -> dict[str, Any]:
    payload = {
        "channel": "outlook", "thread_ref": "outlook://controlled/thread-11-1", "name": "Phase 11.1 Operator",
        "email": "phase11-1@example.invalid", "organisation": "DIO", "review_title": "Attachment-bound service review",
        "message": "Map the supplied evidence to the contract obligations and prepare a draft response.",
        "attachments": [
            _attachment("agreement.txt", "The Supplier shall deliver the signed monthly service report by 2026-09-01. The Supplier must maintain valid insurance. The Customer must retain the signed acceptance record for twelve months.", "authoritative_contract"),
            _attachment("delivery-receipt.txt", "Target clause: 1. Monthly report received but unsigned; human verification remains required.", "evidence"),
            _attachment("insurance.txt", "Target clause: 2. Insurance certificate expired 2025-01-01.", "evidence"),
        ],
        "page_viewed": True, "information_acknowledged": True, "controlled_test_payment_consented": True, "website_honeypot": "",
    }
    first = run_attachment_delivery_journey(payload, output_dir=output_dir / "first", root=root)
    second = run_attachment_delivery_journey(payload, output_dir=output_dir / "second", root=root)
    if first != second:
        raise AssertionError("Phase 11.1 journey is not deterministic")
    if first["sent"] or first["external_delivery"] != "REFUSE" or first["human_release"] != "NEEDS_YOU":
        raise AssertionError("Phase 11.1 crossed the human release boundary")
    if first["evidence_fanout_guard"] != "PASS" or first["unresolved_attachment_count"]:
        raise AssertionError("Phase 11.1.1 evidence reconciliation did not resolve safely")
    receipt = {**first, "deterministic_execution": "PASS", "acceptance_token": ACCEPTANCE_TOKEN}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "PHASE11_1_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt
