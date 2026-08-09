#!/usr/bin/env python3
from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "campaigns" / "phase3" / "evidex" / "human_dummy_test"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.strip() + "\n", encoding="utf-8")


def load_google_form_url() -> str:
    links_js = ROOT / "sites" / "evidex" / "assets" / "commercial-links.js"
    if not links_js.exists():
        return ""
    text = links_js.read_text(encoding="utf-8", errors="replace").strip()
    prefix = "window.EVIDEX_COMMERCIAL_LINKS = "
    if not text.startswith(prefix):
        return ""
    try:
        payload = json.loads(text[len(prefix):].rstrip(";"))
    except json.JSONDecodeError:
        return ""
    return str(payload.get("google_form_url") or "")


def build_pack() -> dict[str, str]:
    pack_dir = OUT_DIR / "dummy_upload_pack"
    pack_dir.mkdir(parents=True, exist_ok=True)

    write(
        pack_dir / "README_UPLOAD_ME.txt",
        """
EVIDEX HUMAN DUMMY TEST PACK
============================

This is a controlled, non-sensitive dummy evidence pack.

Use it to test the Google Form -> Drive -> local watcher -> delivery loop.

Suggested form values:
- Your name: Byron Bunt
- Organization: BrightStart Community Trust
- Role: M&E
- Email for delivery: byron.bunt@nwu.ac.za
- Time zone: Africa/Johannesburg
- Deadline: any date in the next 48 hours
- Confidentiality confirmation: Yes
- Pack purpose: Donor evidence pack for community reading and food support pilot
- Donor/funder: Ubuntu Community Fund
- Grant/project: Community Reading and Food Support Pilot
- Grant ID: EVIDEX-HUMAN-DUMMY-001
- Reporting period start: 2026-04-01
- Reporting period end: 2026-06-30
- KPI mode: pasted KPI text
- Tone: clear, conservative, donor-ready
- Required headings: Evidence table, mapped claims, provenance, QA notes, narrative
- Risk sensitivities: Do not claim audited financial assurance. Do not use learner images publicly.
- Red flags: Two photo consent forms pending; finance officer should confirm totals before final donor submission.
- Upload folder link: paste a Drive folder link containing these files if the form does not offer direct file upload.

KPI text to paste:
Youth reading workshops delivered | target 8 | actual 9 | Workshop sessions delivered
Learners reached | target 120 | actual 137 | Unique learners attending
Food parcels distributed | target 200 | actual 214 | Parcels issued to households
Receipts reconciled | target 95% | actual 98% | Eligible spend linked to receipt records
""",
    )
    write(
        pack_dir / "kpi_progress.csv",
        """
KPI,Target,Actual,Measurement,Notes
Youth reading workshops delivered,8,9,Workshop sessions delivered,Nine Saturday reading workshops were delivered across April to June.
Learners reached,120,137,Unique learners attending,Attendance register shows 137 unique learner names across the quarter.
Food parcels distributed,200,214,Parcels issued to households,Distribution summary records 214 parcels issued with signed register references.
Receipts reconciled,95%,98%,Eligible spend linked to receipt records,Receipt summary links 98 percent of pilot spend to receipt IDs and supplier notes.
""",
    )
    write(
        pack_dir / "attendance_register.csv",
        """
Session Date,Workshop,Unique Learners,Register Reference
2026-04-11,Youth reading workshops delivered,18,REG-APR-01
2026-04-18,Youth reading workshops delivered,16,REG-APR-02
2026-05-02,Youth reading workshops delivered,14,REG-MAY-01
2026-05-09,Youth reading workshops delivered,17,REG-MAY-02
2026-05-23,Youth reading workshops delivered,15,REG-MAY-03
2026-06-06,Youth reading workshops delivered,19,REG-JUN-01
2026-06-13,Youth reading workshops delivered,13,REG-JUN-02
2026-06-20,Youth reading workshops delivered,12,REG-JUN-03
2026-06-27,Youth reading workshops delivered,13,REG-JUN-04
""",
    )
    write(
        pack_dir / "receipts_summary.csv",
        """
Receipt ID,Category,Amount ZAR,KPI Link,Status
RCT-0411-01,Reading materials,1850,Youth reading workshops delivered,Verified
RCT-0502-02,Food parcels,6900,Food parcels distributed,Verified
RCT-0523-03,Transport support,1240,Learners reached,Verified
RCT-0613-04,Food parcels,7200,Food parcels distributed,Verified
RCT-0627-05,Printing and stationery,860,Receipts reconciled,Verified
""",
    )
    write(
        pack_dir / "field_visit_notes.txt",
        """
BrightStart Community Trust field visit notes.

Project: Community Reading and Food Support Pilot.
Reporting period: 2026-04-01 to 2026-06-30.

Observed claims:
- Youth reading workshops delivered: Programme file lists nine sessions delivered in the quarter.
- Learners reached: Coordinator register indicates 137 unique learners participated.
- Food parcels distributed: Distribution notes record 214 food parcels issued to households.
- Receipts reconciled: Finance summary links 98 percent of claimed spend to source receipts.

Known caveat: Two photo consent forms are pending, so public use of learner images is excluded from this pilot pack.
""",
    )
    write(
        pack_dir / "photo_log.txt",
        """
Photo log for non-sensitive pilot.

IMG-001: Workshop room setup, no learner faces visible. Supports Youth reading workshops delivered.
IMG-002: Reading material table, no private data visible. Supports Youth reading workshops delivered.
IMG-003: Food parcel packing table, no private data visible. Supports Food parcels distributed.
IMG-004: Delivery staging area, no household identifiers visible. Supports Food parcels distributed.
""",
    )

    form_url = load_google_form_url()
    email_body = OUT_DIR / "email_body.md"
    write(
        email_body,
        f"""
Hi Byron,

Here is the controlled Evidex human-dummy test.

Ad / offer:

Your donor report probably is not missing effort. It is missing an evidence pipeline.

Evidex turns scattered KPI notes, attendance registers, receipts, field notes, and photo logs into a review-ready evidence pack:

- evidence table
- mapped claims
- provenance/source index
- narrative draft
- QA receipt
- delivery ZIP

This is review-ready support, not automatic donor/auditor sign-off.

Form link:
{form_url or '[Google form link not found in local commercial-links.js]'}

Attached:
- evidex_human_dummy_upload_pack.zip

Use the README inside the ZIP for field values. If the form allows direct upload, upload the files from the unzipped pack. If the form asks for an upload folder link, create a Google Drive folder, upload these files there, share it with the Evidex ops account if needed, and paste that folder link.

Test marker:
EVIDEX-HUMAN-DUMMY-001

Once submitted, we are looking for:

```text
Google Form response
-> Drive EvidenceEngine/incoming/<job>
-> intake.yaml
-> uploads/
-> invoice/payment metadata
-> local mirror / watcher visibility
```

Boundary: this is controlled dummy data. No private learner/person data is included.
""",
    )

    zip_path = OUT_DIR / "evidex_human_dummy_upload_pack.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(pack_dir.rglob("*")):
            if path.is_file():
                zf.write(path, arcname=str(path.relative_to(pack_dir)))

    eml_path = OUT_DIR / "evidex_human_dummy_test_email.eml"
    msg = EmailMessage()
    msg["To"] = "byron.bunt@nwu.ac.za"
    msg["Subject"] = "EVIDEX human-dummy test: ad, form link, and upload pack"
    msg.set_content(email_body.read_text(encoding="utf-8"))
    msg.add_attachment(
        zip_path.read_bytes(),
        maintype="application",
        subtype="zip",
        filename=zip_path.name,
    )
    eml_path.write_bytes(bytes(msg))

    receipt = {
        "schema": "knowedge.evidex_human_dummy_pack.v1",
        "created_at": utc_now(),
        "status": "ready",
        "google_form_url_configured": bool(form_url),
        "form_url": form_url,
        "pack_dir": str(pack_dir),
        "zip": str(zip_path),
        "email_body": str(email_body),
        "eml": str(eml_path),
        "marker": "EVIDEX-HUMAN-DUMMY-001",
    }
    receipt_path = OUT_DIR / "HUMAN_DUMMY_PACK_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return {key: str(value) for key, value in receipt.items()}


def main() -> int:
    receipt = build_pack()
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
