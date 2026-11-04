#!/usr/bin/env python3
"""Run AuditProof with a source-bound access-review exception handoff."""
from __future__ import annotations
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SOURCE = ROOT / 'acceptance_runs/68-product-sellability-20261027/AUDITPROOF_SOURCE_ISSUE_LINEAGE_20261101_V1/SOURCE_PACKET.json'
OUT = ROOT / 'acceptance_runs/68-product-sellability-20261027/AUDITPROOF_ACCESS_REVIEW_TRACKER_20261102_V1'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f'output directory must be new or empty: {OUT}')
    packet = json.loads(SOURCE.read_text(encoding='utf-8'))
    from products.customer_product_router import run_customer_product
    execution = run_customer_product('AuditProof', packet, OUT, render_pdf=False)
    tracker_path = OUT / 'AUDITPROOF_ACCESS_REVIEW_EXCEPTION_TRACKER.json'
    csv_path = OUT / 'AUDITPROOF_ACCESS_REVIEW_EXCEPTION_TRACKER.csv'
    package_path = OUT / 'CUSTOMER_PACKAGE_RECEIPT.json'
    tracker = json.loads(tracker_path.read_text(encoding='utf-8'))
    package = json.loads(package_path.read_text(encoding='utf-8'))
    source_bytes = {row['source_id']: row['text'].encode('utf-8') for row in packet['sources']}
    anchors = [tracker['control_requirement'], tracker['review_sample'], tracker['exception_group'], *tracker['reported_counts']['count_anchors']]
    if any(source_bytes[row['source_id']][row['source_byte_start']:row['source_byte_end_exclusive']].decode('utf-8') != row.get('quote', row.get('literal', row.get('source_quote', row.get('issue_quote')))) for row in anchors):
        raise ValueError('AuditProof tracker failed exact source-byte anchoring')
    fields = ('original_worksheet_ref', 'identified_account_rows', 'owner_outcomes', 'closure_evidence_ref',
              'closure_evidence_sha256', 'auditor_test_result', 'auditor_name', 'reviewed_at_iso8601', 'auditor_rationale')
    with csv_path.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    declared = {row['path']: row.get('sha256') for row in package.get('outputs') or []}
    counts = tracker['reported_counts']
    if (tracker.get('schema') != 'dio.auditproof.access_review_exception_tracker.v1'
            or counts != {**counts, 'total_listed': 42, 'marked_reviewed': 39, 'no_outcome_reported': 3, 'arithmetic_reconciles': True}
            or tracker['exception_group'].get('account_identifier_state') != 'NOT_PRESENT_IN_EXCEPTION_EXCERPT'
            or tracker['exception_group'].get('fabricated_account_rows_created') is not False
            or any(tracker['review_fields'].get(field) for field in fields)
            or len(rows) != 1
            or declared.get(tracker_path.name) != sha(tracker_path)
            or declared.get(csv_path.name) != sha(csv_path)
            or tracker.get('professional_approval') != 'NOT_GRANTED'
            or tracker.get('release_authorized') is not False
            or execution.get('release_authorized') is not False
            or execution.get('external_effects') is not False):
        raise ValueError('AuditProof tracker failed count, package, blank-field or held-boundary checks')
    evidence = {
        'schema': 'dio.auditproof.exception_tracker_execution.v1',
        'product': 'AuditProof',
        'source_packet_sha256': sha(SOURCE),
        'tracker_sha256': sha(tracker_path),
        'csv_sha256': sha(csv_path),
        'customer_package_sha256': sha(package_path),
        'reported_counts': counts,
        'all_source_anchors_exact': True,
        'account_ids_invented': False,
        'review_fields_left_blank': True,
        'professional_approval': 'NOT_GRANTED',
        'release_authorized': False,
        'external_effects': False,
        'claim_boundary': tracker['claim_boundary'],
        'fixture_boundary': 'Synthetic control-review packet verifies exact source anchors and aggregate arithmetic only; it does not establish account-level review outcomes, closure evidence, or control effectiveness.',
    }
    evidence_path = OUT / 'AUDITPROOF_EXCEPTION_TRACKER_EXECUTION_EVIDENCE.json'
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
