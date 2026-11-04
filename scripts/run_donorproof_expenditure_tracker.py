#!/usr/bin/env python3
"""Run DonorProof with a source-bound missing-invoice reconciliation request."""
from __future__ import annotations
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SOURCE = ROOT / 'acceptance_runs/68-product-sellability-20261027/DONORPROOF_SOURCE_ISSUE_LINEAGE_20261101_V1/SOURCE_PACKET.json'
OUT = ROOT / 'acceptance_runs/68-product-sellability-20261027/DONORPROOF_EXPENDITURE_TRACKER_20261102_V1'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f'output directory must be new or empty: {OUT}')
    packet = json.loads(SOURCE.read_text(encoding='utf-8'))
    from products.customer_product_router import run_customer_product
    execution = run_customer_product('DonorProof', packet, OUT, render_pdf=False)
    tracker_path = OUT / 'DONORPROOF_EXPENDITURE_RECONCILIATION_REQUEST.json'
    csv_path = OUT / 'DONORPROOF_EXPENDITURE_RECONCILIATION_REQUEST.csv'
    package_path = OUT / 'CUSTOMER_PACKAGE_RECEIPT.json'
    tracker = json.loads(tracker_path.read_text(encoding='utf-8'))
    package = json.loads(package_path.read_text(encoding='utf-8'))
    request = tracker['requests'][0]
    sources = {row['source_id']: row['text'].encode('utf-8') for row in packet['sources']}
    anchors = list(request['source_anchors']) + [request['restricted_use_wording'], request['reported_expenditure'], request['missing_invoice_count_anchor']]
    for row in anchors:
        literal = row.get('quote', row.get('literal'))
        if sources[row['source_id']][row['source_byte_start']:row['source_byte_end_exclusive']].decode('utf-8') != literal:
            raise ValueError('DonorProof tracker failed exact source-byte anchoring')
    with csv_path.open(encoding='utf-8-sig', newline='') as handle:
        csv_rows = list(csv.DictReader(handle))
    blank_fields = ('invoice_ids_and_amounts','received_invoice_refs','received_invoice_sha256','payment_evidence_refs',
                    'ledger_reconciliation','eligible_use_review','reviewer_decision','reviewer_name','reviewed_at_iso8601','reviewer_rationale')
    declared = {row['path']: row.get('sha256') for row in package.get('outputs') or []}
    if (tracker.get('schema') != 'dio.donorproof.expenditure_reconciliation_request.v1'
            or request.get('reported_expenditure', {}).get('currency') != 'ZAR'
            or request.get('reported_expenditure', {}).get('amount') != 145000
            or request.get('reported_expenditure', {}).get('period') != 'Q3 2026'
            or request.get('reported_invoice_image_count') != 3
            or request.get('invoice_level_amounts_supplied') is not False
            or request.get('reconciliation_state') != 'NOT_COMPUTABLE_MISSING_INVOICE_VALUES'
            or any(request['review_fields'].get(field) for field in blank_fields)
            or len(csv_rows) != 1
            or declared.get(tracker_path.name) != sha(tracker_path)
            or declared.get(csv_path.name) != sha(csv_path)
            or tracker.get('professional_approval') != 'NOT_GRANTED'
            or tracker.get('release_authorized') is not False
            or execution.get('release_authorized') is not False
            or execution.get('external_effects') is not False):
        raise ValueError('DonorProof expenditure tracker failed source, package or held-review checks')
    evidence = {
        'schema': 'dio.donorproof.expenditure_tracker_execution.v1',
        'product': 'DonorProof',
        'source_packet_sha256': sha(SOURCE),
        'tracker_sha256': sha(tracker_path),
        'csv_sha256': sha(csv_path),
        'customer_package_sha256': sha(package_path),
        'reported_amount': request['reported_expenditure'],
        'missing_invoice_count': request['reported_invoice_image_count'],
        'invoice_level_amounts_supplied': False,
        'all_source_anchors_exact': True,
        'review_fields_left_blank': True,
        'eligibility_or_compliance_determination': False,
        'professional_approval': 'NOT_GRANTED',
        'release_authorized': False,
        'external_effects': False,
        'claim_boundary': tracker['claim_boundary'],
        'fixture_boundary': 'Synthetic packet verifies source binding and request formation only; missing invoices prevent invoice-level reconciliation and no grant-use eligibility decision is made.',
    }
    evidence_path = OUT / 'DONORPROOF_EXPENDITURE_TRACKER_EXECUTION_EVIDENCE.json'
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
