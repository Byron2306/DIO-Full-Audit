#!/usr/bin/env python3
"""Run ModelProof with a source-bound evaluation/change review queue."""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SOURCE = ROOT / 'acceptance_runs/68-product-sellability-20261027/MODELPROOF_SOURCE_ISSUE_LINEAGE_20261101_V1/SOURCE_PACKET.json'
OUT = ROOT / 'acceptance_runs/68-product-sellability-20261027/MODELPROOF_SPECIALIST_REVIEW_20261102_V1'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f'output directory must be new or empty: {OUT}')
    packet = json.loads(SOURCE.read_text(encoding='utf-8'))
    from products.customer_product_router import run_customer_product
    execution = run_customer_product('ModelProof', packet, OUT, render_pdf=False)
    worksheet_path = OUT / 'SPECIALIST_REVIEW_WORKSHEET.json'
    worksheet = json.loads(worksheet_path.read_text(encoding='utf-8'))
    package_path = OUT / 'CUSTOMER_PACKAGE_RECEIPT.json'
    package = json.loads(package_path.read_text(encoding='utf-8'))
    rows = worksheet.get('rows') or []
    if (worksheet.get('schema') != 'dio.customer_evidence.specialist_worksheet.v1'
            or worksheet.get('product_name') != 'ModelProof'
            or len(rows) != 3
            or {row.get('requirement_id') for row in rows} != {'R1', 'R2', 'R3'}
            or any(row.get('record_trust_state') != 'captured_untrusted' for row in rows)
            or worksheet.get('professional_approval') != 'NOT_GRANTED'
            or worksheet.get('release_authorized') is not False
            or not any('two supported languages' in row['requirement_quote'] for row in rows)
            or not any(any('No post-change regression run' in issue for issue in row['source_reported_issues']) for row in rows)):
        raise ValueError('ModelProof specialist review worksheet failed its source coverage or held boundary')
    declared = {row['path']: row.get('sha256') for row in package.get('outputs') or []}
    if (declared.get(worksheet_path.name) != sha(worksheet_path)
            or execution.get('release_authorized') is not False
            or execution.get('external_effects') is not False):
        raise ValueError('ModelProof worksheet is not package-bound or execution crossed the held boundary')
    source_text = {row['source_id']: row['text'].encode('utf-8') for row in packet.get('sources', [])}
    for row in rows:
        src = row['requirement_source_id']
        a, b = row['requirement_source_span']
        quote = row['requirement_quote'].encode('utf-8')
        if source_text[src][a:b] != quote:
            raise ValueError('ModelProof worksheet requirement failed exact source-byte check')
    evidence = {
        'schema': 'dio.modelproof.specialist_review_execution.v1',
        'product': 'ModelProof',
        'source_packet_sha256': sha(SOURCE),
        'worksheet_sha256': sha(worksheet_path),
        'customer_package_sha256': sha(package_path),
        'review_row_count': len(rows),
        'covered_requirement_ids': sorted(row['requirement_id'] for row in rows),
        'requirement_quotes_exact_source_bound': True,
        'source_assertions_verified': False,
        'professional_approval': 'NOT_GRANTED',
        'release_authorized': False,
        'external_effects': False,
        'fixture_boundary': 'Synthetic source-bound review queue only; it does not evaluate model performance or establish subgroup fairness, regression adequacy, rollback readiness or approval.',
    }
    evidence_path = OUT / 'MODELPROOF_SPECIALIST_REVIEW_EXECUTION_EVIDENCE.json'
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
