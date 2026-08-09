# Sophia Phase 7/8 Native Vision, Table, Figure, and Citation Gauntlet

Timestamp: `2026-08-03T20:28:17.368974+00:00`

## Summary

| Metric | Value |
|---|---:|
| Cases | 5 |
| Passed | 5 |
| Failed | 0 |
| Pass rate | 100.00% |

## Case Results

| Case | Result | Key signal |
|---|---:|---|
| `native_vision_conflict_detected` | PASS | native_only=['43%'] text_or_ocr_only=['12', '42%'] |
| `figure_to_text_conflict_mapping` | PASS | conflicts=2 |
| `rendered_context_exposes_native_comparison` | PASS | native comparison visible to provider prompt |
| `complex_table_cell_citations_exported` | PASS | cells=10 |
| `advanced_report_includes_page_cell_export` | PASS | cells=10 |

## Interpretation

This run validates the next hardening slice for Sophia's document intelligence. The important change is not that Sophia can merely read more text; it is that she now keeps visual, OCR, caption, table, and page evidence as separate inspectable witnesses.

What is proven here:

- Native vision comparison can represent Gemini/native-vision output as one witness rather than a silent override.
- Conflicting chart/caption numbers trigger a verification hold instead of a confident visual claim.
- Parsed tables export page/table/row/column/cell citation leads.
- Figure-to-text claim mapping returns candidate page/span anchors and conflict status.
- The advanced evidence report surfaces cell citations alongside span ranking, NLI-style support, and vision readiness.

What is not yet proven:

- This deterministic fixture suite does not prove real-world scanned-PDF accuracy across a large corpus.
- It does not benchmark native Gemini vision against human visual inspection on real figures.
- It does not yet parse complex merged scientific table headers with statistical footnotes as robustly as specialist layout models.
- Page/cell exports remain citation leads for human verification, not finalized bibliographic claims.
