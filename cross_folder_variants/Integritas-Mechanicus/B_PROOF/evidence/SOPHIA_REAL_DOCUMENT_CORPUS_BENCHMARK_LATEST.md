# Sophia Real Document Corpus Benchmark

Timestamp: `2026-08-03T20:30:35.689839+00:00`

## Summary

| Metric | Value |
|---|---:|
| Cases | 8 |
| Passed | 8 |
| Failed | 0 |
| Pass rate | 100.00% |
| Corpus files | 3 |
| Fixture mode | True |

## Case Results

| Case | Result | Key signal |
|---|---:|---|
| `messy_corpus_bundle_builds_cross_modal_witnesses` | PASS | documents=3 native_status=native_vision_text_conflict |
| `chart_image_extraction_from_pdf_or_declared_proxy` | PASS | statuses=['fixture_chart_proxy'] |
| `figure_to_text_claim_mapping_runs_on_corpus` | PASS | status=figure_claim_conflict_requires_verification conflicts=1 |
| `merged_header_scientific_tables_and_footnotes_flagged` | PASS | flags=['footnote_markers_present', 'statistical_notation_present'] |
| `zotero_csv_jsonl_audit_exports_written` | PASS | rows=8 zotero=3 |
| `blinded_human_visual_inspection_packet_written` | PASS | items=1 |
| `native_gemini_vs_blinded_human_inspection_contract` | PASS | status=not_computable_without_blinded_human_rows agreement=None |
| `optional_live_gemini_native_vision_probe_contract` | PASS | status=skipped |

## Truth Boundary

This benchmark can run over a real corpus directory, but the default no-corpus mode uses deterministic fixtures. Native Gemini comparison is only live when `--probe-gemini` is enabled and keys are configured. Human inspection agreement is only computable when a blinded inspection CSV is supplied.

## Blinded Human Packet

- CSV: `/home/byron/Integritas-Mechanicus/evidence/document_audit_exports/sophia_blinded_visual_inspection_latest.csv`
- Instructions: `/home/byron/Integritas-Mechanicus/evidence/document_audit_exports/sophia_blinded_visual_inspection_latest_instructions.md`
- Key: `/home/byron/Integritas-Mechanicus/evidence/document_audit_exports/sophia_blinded_visual_inspection_latest_key.json`
