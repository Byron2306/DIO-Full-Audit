# Report, pitch and publication customer delivery pathway

Date: 2026-10-27. Scope: Report & Pitch Studio and Article & Publication Studio.

The new local service converts a supplied customer packet into an editable report, presentation and attributed article draft. It reuses DIO Format Core for DOCX, HTML, PDF and PPTX rendering, and Document Studio for PPTX-to-PDF conversion. It makes no external model calls, sends nothing and grants no approval. Existing native-product canon and maturity classifications are unchanged.

## Callable entry point

```python
from products.report_pitch_pipeline import build_report_pitch_package

receipt = build_report_pitch_package(
    {
        "title": "Customer decision brief",
        "audience": "Accountable decision committee",
        "objective": "The decision this packet should support",
        "domain": "general",
        "sources": [
            {"source_id": "S1", "title": "Supplied record",
             "citation": "Customer supplied record, date and owner",
             "visibility": "review_only",
             "text": "Actual supplied source paragraph.\nIts qualification or limitation."}
        ],
        "recommendations": [
            {"text": "A customer-proposed option for reviewer consideration",
             "claim_ids": ["S1-P1", "S1-P2"]}
        ],
    },
    "/empty/customer/output/directory",
    render_pdf=True,
)
```

`sources` must contain actual supplied text. Paragraph IDs use source ID and nonempty line position (`S1-P1`). The output directory must be empty so a rerun cannot accidentally ship another customer's old files. Invalid packets are rejected before output is created. The caller must provide the source text; this entry point does not fetch or OCR attachments.

Optional source `metrics` contain `metric`, finite numeric `value`, `unit`, `period` and an exact `quote`. Values must actually appear in the source quotation. Metric labels and units remain customer-supplied interpretations requiring review. Optional `calculations` support explicit ratios of uniquely identified source metrics with matching periods. The generated analysis includes formula, source inputs, derived value and limits. Zero denominators and incompatible periods produce a review hold. No metric is invented, averaged across conflicting sources or forecast.

## Customer deliverables

- Report: actual source-derived observations, executive evidence brief, measurements, optional source-bound arithmetic analysis, proposed decision options with rationale references, review questions and references. DOCX, HTML and PDF when LibreOffice is present.
- Pitch: real editable PPTX with decision, every retained source observation and qualifier, native measurement tables, source coverage figure, optional arithmetic analysis, proposed options, review flags and references. A separate PDF is produced through Document Studio when available.
- Article: attributed editorial draft in DOCX/HTML/PDF, using the eligible supplied source record. Explicitly restricted sources are omitted from this projection. All output remains subject to rights and editorial review.
- Review evidence: original customer packet, source register and hashes, exact source offsets in a claim map, held unsupported assertions, quarantined instruction-like material, reviewer checklist, typed semantic objects, renderer receipts, file hashes and a ZIP review package.

This is a sellable **source-bound briefing and editorial preparation service**. It is not a substitute for original investigative reporting, commissioned long-form expert synthesis, independent fact checking or expert advice. The article is an attributed draft for an editor, not an independently reported feature. Domain-specific expert approval, editorial acceptance and final release remain explicit pending gates. Automated source attribution is never presented as factual verification.

## Verification

Fail-first tests initially failed because the new module did not exist. Further fail-first checks covered numeric analysis and the pre-existing renderer's unpopulated contents-field page. The compact report/article projection now selects the existing Minimal Print profile, eliminating that placeholder. The deck retains the existing professional profile. The figure canvas was corrected after visual inspection to avoid distorting the source-coverage labels.

```bash
.venv/bin/python -m unittest tests.test_report_pitch_pipeline tests.test_format_core -v
.venv/bin/python scripts/run_report_pitch_acceptance.py --out /new/empty/acceptance/root
```

The focused suite covers real editable output, unsupported assertion holds, instruction quarantine, restricted-source omission from the article, exact metric support, duplicate identifiers, stale output, unseen content changes, metric conflicts, ratio arithmetic and zero denominators. Format Core compatibility tests exercise existing multilingual source projection and existing rendering.

The final inspected acceptance run is `acceptance_runs/68-product-sellability-20261027/report-pitch/reviewed/`. The earlier top-level and `final/` runs are retained as implementation/visual-review history; `reviewed/` is the current result.

| Synthetic case | Retained source claims | Changed content and exercised boundary |
|---|---:|---|
| baseline | 5 | Clinic capacity and cost brief; 180000 / 240 = 750 ZAR per appointment, with explicit limitations |
| messy-adversarial | 7 | Conflicting appointment counts, quarantined source instructions, held invented cure assertion and restricted patient example |
| unseen | 6 | Archive humidity, expired instrument calibration and non-comparable readings; no clinic content survives |

All three runs produced DOCX, HTML, PPTX and actual PDFs; all renderer checks passed. Every retained source statement survived editable deck → PDF text extraction. Slide previews and a report PDF page were visually inspected. The final baseline report is two pages without the empty contents placeholder. Figures are labelled as retained source-paragraph counts, not quality scores or clinical outcomes. Deck layouts are restrained and readable; complex customer material still requires layout review.

## Authority and remaining work

The production receipt records `externally_released=false`, `expert_approved=false`, `publication_authorized=false` and `canon_promoted=false`. The checklist separately denies publish, send, spend and maturity promotion. Restricted material remains in the internal report, deck and reviewer package, which are explicitly labelled controlled drafts; the entire ZIP is not a public artifact.

Source-instruction quarantine is a conservative pattern guard, not a complete prompt-injection classifier. This service never executes or delegates source text. Bibliographic fields are retained exactly as supplied and are not verified against external catalogues. Proposed paraphrases without exact support remain held for editorial judgment. Customer-proposed recommendations are attributed as options, not approved professional conclusions. These are contractual service boundaries, not evidence that an expert or editor has already approved a deliverable.

The API is ready for root-level routing integration. No shared native-grade registry, storefront route or maturity state was changed by this scoped implementation.
