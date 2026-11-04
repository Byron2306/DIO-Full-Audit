#!/usr/bin/env python3
"""Run QualityProof with a source-bound CAPA action tracker."""
from __future__ import annotations
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SOURCE = ROOT / 'acceptance_runs/68-product-sellability-20261027/QUALITYPROOF_SOURCE_ISSUE_LINEAGE_20261101_V1/SOURCE_PACKET.json'
OUT = ROOT / 'acceptance_runs/68-product-sellability-20261027/QUALITYPROOF_CAPA_TRACKER_20261102_V1'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f'output directory must be new or empty: {OUT}')
    packet = json.loads(SOURCE.read_text(encoding='utf-8'))
    from products.customer_product_router import run_customer_product
    execution = run_customer_product('QualityProof', packet, OUT, render_pdf=False)
    tracker_path = OUT / 'QUALITYPROOF_CAPA_REVIEW_TRACKER.json'
    csv_path = OUT / 'QUALITYPROOF_CAPA_REVIEW_TRACKER.csv'
    package_path = OUT / 'CUSTOMER_PACKAGE_RECEIPT.json'
    tracker = json.loads(tracker_path.read_text(encoding='utf-8'))
    package = json.loads(package_path.read_text(encoding='utf-8'))
    item = tracker['items'][0]
    with csv_path.open(encoding='utf-8-sig', newline='') as handle:
        csv_rows = list(csv.DictReader(handle))
    src = {row['source_id']: row['text'].encode('utf-8') for row in packet['sources']}
    anchors = [item['source_reported_finding'], item['closure_evidence_issue'], *item['assigned_date_candidates'], item['planned_effectiveness_date'], item['review_note_date']]
    if any(src[row['source_id']][row['source_byte_start']:row['source_byte_end_exclusive']].decode('utf-8') != row['literal' if 'literal' in row else 'quote'] for row in anchors):
        raise ValueError('QualityProof CAPA tracker failed exact source-byte validation')
    blank_fields = ('verified_owner', 'verified_action_due_date', 'closure_evidence_reference', 'effectiveness_check_result', 'reviewer_decision', 'reviewer_name', 'reviewed_at_iso8601', 'reviewer_rationale')
    declared = {row['path']: row.get('sha256') for row in package.get('outputs') or []}
    if (tracker.get('schema') != 'dio.qualityproof.capa_review_tracker.v1'
            or item.get('capa_id') != 'CAPA-204'
            or item.get('owner_state') != 'OWNER_ASSIGNMENT_REPORTED_NAME_NOT_SUPPLIED'
            or item.get('closure_evidence_state') != 'SOURCE_REPORTS_RECORD_NOT_FOUND'
            or item.get('date_relation') != 'PLANNED_DATE_PRECEDES_REVIEW_NOTE_DATE'
            or any(item['review_fields'].get(field) for field in blank_fields)
            or len(csv_rows) != 1
            or declared.get(tracker_path.name) != sha(tracker_path)
            or declared.get(csv_path.name) != sha(csv_path)
            or tracker.get('professional_approval') != 'NOT_GRANTED'
            or tracker.get('release_authorized') is not False
            or execution.get('release_authorized') is not False
            or execution.get('external_effects') is not False):
        raise ValueError('QualityProof CAPA tracker failed completeness, package-binding or held-boundary checks')
    evidence = {
        'schema': 'dio.qualityproof.capa_tracker_execution.v1',
        'product': 'QualityProof',
        'source_packet_sha256': sha(SOURCE),
        'tracker_sha256': sha(tracker_path),
        'csv_sha256': sha(csv_path),
        'customer_package_sha256': sha(package_path),
        'capa_count': len(tracker['items']),
        'capa_ids': [row['capa_id'] for row in tracker['items']],
        'all_source_anchors_exact': True,
        'owner_identity_supplied': False,
        'closure_evidence_status': item['closure_evidence_state'],
        'review_fields_left_blank': True,
        'professional_approval': 'NOT_GRANTED',
        'release_authorized': False,
        'external_effects': False,
        'claim_boundary': tracker['claim_boundary'],
        'fixture_boundary': 'Synthetic packet confirms source binding and date comparison only; it does not establish CAPA overdue status, effectiveness, adequacy or closure.',
    }
    evidence_path = OUT / 'QUALITYPROOF_CAPA_TRACKER_EXECUTION_EVIDENCE.json'
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
