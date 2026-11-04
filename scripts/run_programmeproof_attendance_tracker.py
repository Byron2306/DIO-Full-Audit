#!/usr/bin/env python3
"""Run ProgrammeProof with a source-bound missing attendance-sheet request."""
from __future__ import annotations
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SOURCE = ROOT / 'acceptance_runs/68-product-sellability-20261027/PROGRAMMEPROOF_SOURCE_ISSUE_LINEAGE_20261101_V1/SOURCE_PACKET.json'
OUT = ROOT / 'acceptance_runs/68-product-sellability-20261027/PROGRAMMEPROOF_ATTENDANCE_TRACKER_20261102_V1'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f'output directory must be new or empty: {OUT}')
    packet = json.loads(SOURCE.read_text(encoding='utf-8'))
    from products.customer_product_router import run_customer_product
    execution = run_customer_product('ProgrammeProof', packet, OUT, render_pdf=False)
    tracker_path = OUT / 'PROGRAMMEPROOF_ATTENDANCE_EVIDENCE_TRACKER.json'
    csv_path = OUT / 'PROGRAMMEPROOF_ATTENDANCE_EVIDENCE_TRACKER.csv'
    package_path = OUT / 'CUSTOMER_PACKAGE_RECEIPT.json'
    tracker = json.loads(tracker_path.read_text(encoding='utf-8'))
    package = json.loads(package_path.read_text(encoding='utf-8'))
    review = tracker['review']
    request = tracker['request']
    sources = {row['source_id']: row['text'].encode('utf-8') for row in packet['sources']}
    for row in [review['plan_source'], review['delivery_log_source'], review['exception_source'], review['missing_count_anchor']]:
        if sources[row['source_id']][row['source_byte_start']:row['source_byte_end_exclusive']].decode('utf-8') != row.get('quote', row.get('literal')):
            raise ValueError('ProgrammeProof tracker failed exact source-byte anchoring')
    with csv_path.open(encoding='utf-8-sig', newline='') as handle:
        csv_rows = list(csv.DictReader(handle))
    fields = ('missing_session_ids_and_log_rows','session_dates_and_sites','received_attendance_refs',
              'received_attendance_sha256','participant_count_reconciliation','reviewer_decision',
              'reviewer_name','reviewed_at_iso8601','reviewer_rationale')
    declared = {row['path']: row.get('sha256') for row in package.get('outputs') or []}
    if (tracker.get('schema') != 'dio.programmeproof.attendance_evidence_tracker.v1'
            or review.get('reported_sessions') != 18
            or review.get('reported_site_count') != 5
            or review.get('sessions_with_sheets_reported') != 15
            or review.get('sessions_without_sheets_reported') != 3
            or review.get('count_arithmetic_reconciles') is not True
            or review.get('participant_reach_count') is not None
            or review.get('fabricated_session_rows_created') is not False
            or any(request['review_fields'].get(field) for field in fields)
            or len(csv_rows) != 1
            or declared.get(tracker_path.name) != sha(tracker_path)
            or declared.get(csv_path.name) != sha(csv_path)
            or tracker.get('professional_approval') != 'NOT_GRANTED'
            or tracker.get('release_authorized') is not False
            or execution.get('release_authorized') is not False
            or execution.get('external_effects') is not False):
        raise ValueError('ProgrammeProof attendance tracker failed count, package or review-boundary checks')
    evidence = {
        'schema': 'dio.programmeproof.attendance_tracker_execution.v1',
        'product': 'ProgrammeProof',
        'source_packet_sha256': sha(SOURCE),
        'tracker_sha256': sha(tracker_path),
        'csv_sha256': sha(csv_path),
        'customer_package_sha256': sha(package_path),
        'reported_sessions': review['reported_sessions'],
        'reported_sheets_supplied': review['sessions_with_sheets_reported'],
        'reported_missing_sheets': review['sessions_without_sheets_reported'],
        'reported_counts_reconcile': review['count_arithmetic_reconciles'],
        'session_level_evidence_supplied': False,
        'session_rows_fabricated': False,
        'participant_reach_calculated': False,
        'all_source_anchors_exact': True,
        'review_fields_left_blank': True,
        'professional_approval': 'NOT_GRANTED',
        'release_authorized': False,
        'external_effects': False,
        'claim_boundary': tracker['claim_boundary'],
        'fixture_boundary': 'Synthetic packet verifies source anchoring and aggregate arithmetic only; session delivery and participant reach remain unverified.',
    }
    evidence_path = OUT / 'PROGRAMMEPROOF_ATTENDANCE_TRACKER_EXECUTION_EVIDENCE.json'
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
