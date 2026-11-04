#!/usr/bin/env python3
"""Run VendorProof with source-bound DPA and annual-review document requests."""
from __future__ import annotations
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SOURCE = ROOT / 'acceptance_runs/68-product-sellability-20261027/VENDORPROOF_SOURCE_ISSUE_LINEAGE_20261101_V1/SOURCE_PACKET.json'
OUT = ROOT / 'acceptance_runs/68-product-sellability-20261027/VENDORPROOF_DOCUMENT_REQUESTS_20261102_V1'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f'output directory must be new or empty: {OUT}')
    packet = json.loads(SOURCE.read_text(encoding='utf-8'))
    from products.customer_product_router import run_customer_product
    execution = run_customer_product('VendorProof', packet, OUT, render_pdf=False)
    register_path = OUT / 'VENDORPROOF_DOCUMENT_REQUEST_REGISTER.json'
    csv_path = OUT / 'VENDORPROOF_DOCUMENT_REQUEST_REGISTER.csv'
    package_path = OUT / 'CUSTOMER_PACKAGE_RECEIPT.json'
    register = json.loads(register_path.read_text(encoding='utf-8'))
    package = json.loads(package_path.read_text(encoding='utf-8'))
    requests = {row['request_id']: row for row in register.get('requests', [])}
    sources = {row['source_id']: row['text'].encode('utf-8') for row in packet.get('sources', [])}
    for row in register.get('requests', []):
        for anchor in row.get('source_anchors', []):
            if sources[anchor['source_id']][anchor['source_byte_start']:anchor['source_byte_end_exclusive']].decode('utf-8') != anchor['quote']:
                raise ValueError('VendorProof document request quote failed source-byte verification')
        for anchor in row.get('date_candidates', []):
            if (sources[anchor['source_id']][anchor['source_byte_start']:anchor['source_byte_end_exclusive']].decode('utf-8') != anchor['literal']
                    or hashlib.sha256(anchor['literal'].encode('utf-8')).hexdigest() != anchor['literal_sha256']):
                raise ValueError('VendorProof request date failed source-byte verification')
        if any(row['request_fields'].values()):
            raise ValueError('VendorProof request fields must remain blank for customer completion')
    with csv_path.open(encoding='utf-8-sig', newline='') as handle:
        csv_rows = list(csv.DictReader(handle))
    declared = {row['path']: row.get('sha256') for row in package.get('outputs') or []}
    if (register.get('schema') != 'dio.vendorproof.document_request_register.v1'
            or set(requests) != {'VREQ-DPA', 'VREQ-SECURITY'}
            or requests['VREQ-DPA']['request_status'] != 'SOURCE_REPORTS_NOT_INCLUDED'
            or requests['VREQ-SECURITY']['request_status'] != 'CUSTOMER_ASSERTION_RECORDED_DATE_UNVERIFIED'
            or [row['literal'] for row in requests['VREQ-SECURITY']['date_candidates']] != ['2026-08-01']
            or len(csv_rows) != 2
            or declared.get(register_path.name) != sha(register_path)
            or declared.get(csv_path.name) != sha(csv_path)
            or register.get('professional_approval') != 'NOT_GRANTED'
            or register.get('release_authorized') is not False
            or execution.get('release_authorized') is not False
            or execution.get('external_effects') is not False):
        raise ValueError('VendorProof document request register failed source, package or review-boundary checks')
    evidence = {
        'schema': 'dio.vendorproof.document_request_execution.v1',
        'product': 'VendorProof',
        'source_packet_sha256': sha(SOURCE),
        'register_sha256': sha(register_path),
        'csv_sha256': sha(csv_path),
        'customer_package_sha256': sha(package_path),
        'request_count': len(register['requests']),
        'request_ids': sorted(requests),
        'all_source_anchors_exact': True,
        'review_fields_left_blank': True,
        'source_authenticity_verified': False,
        'professional_approval': 'NOT_GRANTED',
        'release_authorized': False,
        'external_effects': False,
        'claim_boundary': register['claim_boundary'],
        'fixture_boundary': 'Synthetic procurement packet verifies request formation and source byte anchors only; no supplier document, authenticity check, security conclusion or legal sufficiency is established.',
    }
    evidence_path = OUT / 'VENDORPROOF_DOCUMENT_REQUEST_EXECUTION_EVIDENCE.json'
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
