#!/usr/bin/env python3
"""Run ImpactProof with a source-bound six-month cohort follow-up request."""
from __future__ import annotations
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SOURCE = ROOT / 'acceptance_runs/68-product-sellability-20261027/IMPACTPROOF_SOURCE_ISSUE_LINEAGE_20261101_V1/SOURCE_PACKET.json'
OUT = ROOT / 'acceptance_runs/68-product-sellability-20261027/IMPACTPROOF_FOLLOWUP_REQUEST_20261102_V1'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f'output directory must be new or empty: {OUT}')
    packet = json.loads(SOURCE.read_text(encoding='utf-8'))
    from products.customer_product_router import run_customer_product
    execution = run_customer_product('ImpactProof', packet, OUT, render_pdf=False)
    request_path = OUT / 'IMPACTPROOF_FOLLOWUP_EVIDENCE_REQUEST.json'
    csv_path = OUT / 'IMPACTPROOF_FOLLOWUP_EVIDENCE_REQUEST.csv'
    package_path = OUT / 'CUSTOMER_PACKAGE_RECEIPT.json'
    register = json.loads(request_path.read_text(encoding='utf-8'))
    package = json.loads(package_path.read_text(encoding='utf-8'))
    cohort = register['cohort_request']
    sources = {row['source_id']: row['text'].encode('utf-8') for row in packet['sources']}
    anchors = [cohort['outcome_definition'], cohort['reported_placement'], cohort['followup_gap']]
    if any(sources[row['source_id']][row['source_byte_start']:row['source_byte_end_exclusive']].decode('utf-8') != row['quote'] for row in anchors):
        raise ValueError('ImpactProof request failed exact source-byte anchoring')
    with csv_path.open(encoding='utf-8-sig', newline='') as handle:
        csv_rows = list(csv.DictReader(handle))
    fields = ('requested_from','request_owner','request_sent_at','received_record_refs','received_record_sha256',
              'reviewer_comparability_decision','reviewer_outcome_decision','reviewer_name','reviewed_at_iso8601','reviewer_rationale')
    declared = {row['path']: row.get('sha256') for row in package.get('outputs') or []}
    if (register.get('schema') != 'dio.impactproof.followup_evidence_request.v1'
            or cohort.get('reported_cohort_size') != 27
            or cohort.get('reported_cohort_period') != '2026 Q3'
            or cohort.get('required_followup_duration_months') != 6
            or cohort.get('followup_records_state') != 'SOURCE_REPORTS_NO_RECORDS_INCLUDED'
            or cohort.get('sustained_outcome_count') is not None
            or any(cohort['request_fields'].get(field) for field in fields)
            or len(csv_rows) != 1
            or declared.get(request_path.name) != sha(request_path)
            or declared.get(csv_path.name) != sha(csv_path)
            or register.get('professional_approval') != 'NOT_GRANTED'
            or register.get('release_authorized') is not False
            or execution.get('release_authorized') is not False
            or execution.get('external_effects') is not False):
        raise ValueError('ImpactProof follow-up request failed cohort, package or review-boundary checks')
    evidence = {
        'schema': 'dio.impactproof.followup_request_execution.v1',
        'product': 'ImpactProof',
        'source_packet_sha256': sha(SOURCE),
        'request_sha256': sha(request_path),
        'csv_sha256': sha(csv_path),
        'customer_package_sha256': sha(package_path),
        'reported_cohort_size': cohort['reported_cohort_size'],
        'reported_period': cohort['reported_cohort_period'],
        'followup_threshold_months': cohort['required_followup_duration_months'],
        'followup_records_supplied': False,
        'sustained_outcome_count_calculated': False,
        'all_source_anchors_exact': True,
        'review_fields_left_blank': True,
        'professional_approval': 'NOT_GRANTED',
        'release_authorized': False,
        'external_effects': False,
        'claim_boundary': register['claim_boundary'],
        'fixture_boundary': 'Synthetic packet verifies request formation and source anchoring only; no participant-level outcome, follow-up duration or programme impact is established.',
    }
    evidence_path = OUT / 'IMPACTPROOF_FOLLOWUP_REQUEST_EXECUTION_EVIDENCE.json'
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
