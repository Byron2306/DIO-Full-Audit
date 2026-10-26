# DIO Phase 11.1 — Vesper Attachment and Draft Delivery Bridge

Phase 11.1 closes the gap between a paid-reference request and an attachment-bearing governed case. Vesper, DIO's Presence Core, accepts web or Outlook-shaped intake, quarantines original bytes, verifies signatures, hashes every file, emits extraction receipts and binds evidence into ContractProof.

The resulting human-readable proof pack is assembled into an Outlook Smart Bot delivery draft. The chain stops there. No message is sent, no attachment is externally released and no machine result creates human authority.

## Acceptance boundary

- one extractable attachment is explicitly designated `authoritative_contract`;
- evidence attachments remain `captured_untrusted` until human review;
- TXT, Markdown, JSON, DOCX and XLSX have deterministic local extraction paths;
- PDF and images are preserved and hash-bound without invented text extraction;
- ZIP contents are inventoried but never expanded into the workspace;
- Outlook output is `DRAFT_ONLY`, `send_authorized: false`, `sent: false`;
- external release remains `REFUSE` and human release remains `NEEDS_YOU`.

Run:

```bash
python scripts/run_phase11_1.py --output /tmp/dio-phase11-1
```

Acceptance token: `DIO_PHASE11_1_VESPER_ATTACHMENT_DELIVERY_READY`.
