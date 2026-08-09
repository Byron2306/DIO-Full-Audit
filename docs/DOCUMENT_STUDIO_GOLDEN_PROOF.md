# DIO Document Studio Golden Proof

## Product Route

```text
authorised document
-> paragraph anchors
-> technical edit
-> clean copy + visible redline + change ledger
-> controlled terminology
-> translation
-> bilingual review copy + language QA
-> technical and target-language review
-> client approval
-> delivery
```

Document Studio is distinct from Sophia Academic Review. Sophia diagnoses academic argument, evidence and references without replacing authorship. Document Studio performs owner-authorised professional editing and translation on existing business, institutional and technical documents.

## Golden Review Candidate

- Job: `DIO-DOC-GOLDEN-001`
- Source: synthetic community water-quality monitoring procedure
- Route: English technical edit plus Afrikaans translation
- Paragraphs: 7
- Protected tokens: `pH`, `NTU`, `QMS-07`
- Outputs: clean copy, visible redline, change ledger, translated copy, bilingual copy, glossary, QA, receipt and ZIP
- Provider: Gemini through Sophia's configured provider runtime
- Remote source processing: explicitly authorised for the synthetic proof

The model translation was not accepted silently. Bilingual proof review corrected six paragraphs, including a materially incorrect instruction verb. The raw model draft and reviewed wording remain together in `PROVIDER_OUTPUT.json` and `DOCUMENT_STUDIO_QA.json`.

## Passed Gates

- Every required paragraph returned exactly once
- All numbers and operational thresholds preserved
- Protected tokens preserved in source and target outputs
- Preferred terminology present
- English clean copy and redline generated
- Afrikaans clean copy and bilingual review generated
- DOCX and PDF outputs rendered successfully
- Controlled source and target-language semantic objects rendered through shared Format Core profiles
- Post-render semantic completeness checks applied to DOCX, PDF and accessible HTML
- Client DOCX template, PowerPoint master and logo hooks available with hashed lineage
- Provider drafts and reviewer overrides receipted
- Public intake uses `dio.public_intake.v1`
- Live Cloudflare Worker and D1 accept `product: document_studio`
- Certified-translation claims explicitly blocked

## Remaining Gates

1. A qualified Afrikaans language reviewer must inspect the complete translation.
2. A water-quality subject-matter owner must verify operational meaning and safety instructions.
3. The client must approve final wording and layout.
4. Any client-specific layout claim must be proven with that client's clean template and approved rendered output; arbitrary pixel-identical source reconstruction is not claimed.
5. The first paid pilot must record words, processing time, manual review time, revisions and effective hourly return.

## Review

- Site: `http://127.0.0.1:8765/sites/document-studio/`
- Pack: `deliverables/document_studio/DIO-DOC-GOLDEN-001`
- Shared format proof: `deliverables/format_core/DIO-FORMAT-GOLDEN-001`
- Release ZIP: `DIO-DOC-GOLDEN-001_DOCUMENT_STUDIO_REVIEW_PACK.zip`

## Rebuild

```bash
./.venv/bin/python scripts/run_document_studio.py \
  samples/document_studio/water_quality_edit_translate_request.json
```
