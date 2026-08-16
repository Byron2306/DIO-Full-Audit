from __future__ import annotations

import base64
import json
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from products.phase11_1 import run_attachment_delivery_journey


ACCEPTANCE_TOKEN = "DIO_PHASE11_1_1_EVIDENCE_RECONCILIATION_READY"


def _attachment(name: str, text: str, role: str) -> dict[str, Any]:
    return {"filename": name, "mime_type": "text/plain", "role": role, "content_base64": base64.b64encode(text.encode()).decode()}


def _archive_attachment(name: str, member: str, text: str) -> dict[str, Any]:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member, text)
    return {"filename": name, "mime_type": "application/zip", "role": "evidence", "content_base64": base64.b64encode(buffer.getvalue()).decode()}


def run_phase11_1_gauntlet(*, output_dir: Path, root: Path) -> dict[str, Any]:
    payload = {
        "channel": "outlook", "thread_ref": "outlook://controlled/thread-11-1", "name": "Phase 11.1 Operator",
        "email": "phase11-1@example.invalid", "organisation": "DIO", "review_title": "Attachment-bound service review",
        "message": "Map the supplied evidence to the contract obligations and prepare a draft response.",
        "attachments": [
            _attachment("01_agreement.txt", """The Supplier shall deliver the signed monthly service report no later than 2026-09-01.
The Supplier must maintain valid insurance through 2026-12-31.
The Customer shall provide final written acceptance before the milestone is accepted.
The Supplier must notify the Customer of a security incident within 24 hours after discovery.
The Supplier shall complete preventative maintenance every calendar month.
The Supplier must remedy a failed inspection within five business days.
The Supplier shall delete export data within 48 hours after a verified request.""", "authoritative_contract"),
            _attachment("02_delivery.json", '{"target_clause":1,"signed":false}', "evidence"),
            _attachment("03_insurance.txt", "Target clause: 2. Insurance certificate expired 2025-01-01.", "evidence"),
            _attachment("04_acceptance.json", '{"target_clause":3,"final_acceptance":false,"signed":false,"state":"PROVISIONAL ACCEPTANCE"}', "evidence"),
            _attachment("05_incident.txt", "Contract clause: 4. Assessment: LATE NOTICE. Elapsed time: 30 hours.", "evidence"),
            _attachment("06_maintenance.json", '{"target_clause":5,"performed_at":"2026-08-14","signed":true}', "evidence"),
            _attachment("07_inspection.json", '{"target_clause":6,"inspection_status":"FAILED","remediation_required":true,"signed":false}', "evidence"),
            _attachment("08_canteen.txt", "Tomato soup, cheese sandwich and coffee.", "evidence"),
            _attachment("09_ambiguous.txt", "Routine service work was discussed. A report may exist.", "evidence"),
            _archive_attachment("10_deletion.zip", "deletion_audit.txt", "Target clause: 7. Deletion completed in 47 hours 30 minutes. Signature state: UNSIGNED."),
        ],
        "page_viewed": True, "information_acknowledged": True, "controlled_test_payment_consented": True, "website_honeypot": "",
    }
    first = run_attachment_delivery_journey(payload, output_dir=output_dir / "first", root=root)
    second = run_attachment_delivery_journey(payload, output_dir=output_dir / "second", root=root)
    if first != second:
        raise AssertionError("Phase 11.1 journey is not deterministic")
    if first["sent"] or first["external_delivery"] != "REFUSE" or first["human_release"] != "NEEDS_YOU":
        raise AssertionError("Phase 11.1 crossed the human release boundary")
    if first["evidence_fanout_guard"] != "PASS" or first["unresolved_attachment_count"] != 2:
        raise AssertionError("Phase 11.1.1 evidence reconciliation did not preserve safe fan-out and the two intended unresolved records")
    receipt = {**first, "deterministic_execution": "PASS", "acceptance_token": ACCEPTANCE_TOKEN}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "PHASE11_1_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt
