from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from products.phase11_1 import run_attachment_delivery_journey


ACCEPTANCE_TOKEN = "DIO_PHASE11_1_VESPER_ATTACHMENT_DELIVERY_READY"


def _attachment(name: str, text: str, role: str) -> dict[str, Any]:
    return {"filename": name, "mime_type": "text/plain", "role": role, "content_base64": base64.b64encode(text.encode()).decode()}


def run_phase11_1_gauntlet(*, output_dir: Path, root: Path) -> dict[str, Any]:
    payload = {
        "channel": "outlook", "thread_ref": "outlook://controlled/thread-11-1", "name": "Phase 11.1 Operator",
        "email": "phase11-1@example.invalid", "organisation": "DIO", "review_title": "Attachment-bound service review",
        "message": "Map the supplied evidence to the contract obligations and prepare a draft response.",
        "attachments": [
            _attachment("agreement.txt", "The Supplier shall deliver the monthly service report by the fifth business day. The Customer must retain the signed acceptance record for twelve months.", "authoritative_contract"),
            _attachment("delivery-receipt.txt", "Monthly report received for controlled review; human verification remains required.", "evidence"),
        ],
        "page_viewed": True, "information_acknowledged": True, "controlled_test_payment_consented": True, "website_honeypot": "",
    }
    first = run_attachment_delivery_journey(payload, output_dir=output_dir / "first", root=root)
    second = run_attachment_delivery_journey(payload, output_dir=output_dir / "second", root=root)
    if first != second:
        raise AssertionError("Phase 11.1 journey is not deterministic")
    if first["sent"] or first["external_delivery"] != "REFUSE" or first["human_release"] != "NEEDS_YOU":
        raise AssertionError("Phase 11.1 crossed the human release boundary")
    receipt = {**first, "deterministic_execution": "PASS", "acceptance_token": ACCEPTANCE_TOKEN}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "PHASE11_1_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt
