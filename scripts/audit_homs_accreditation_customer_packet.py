#!/usr/bin/env python3
"""Verify the held HOMS Accreditation source-mapped customer packet."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'acceptance_runs/68-product-sellability-20261027'
JOB = BASE / 'HOMS_ACCREDITATION_CUSTOMER_PACKET_EXECUTION_20261101_V4'
SOURCE_DIR = ROOT / 'acceptance_runs/68-product-integration-20261027/post-review-repaired/normal/homs-accreditation/CUSTOMER_PACKET/SOURCES'
OUTPUT = BASE / 'HOMS_ACCREDITATION_CUSTOMER_PACKET_EVIDENCE_20261101.json'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    execution = json.loads((JOB / 'CUSTOMER_EXECUTION_RECEIPT.json').read_text(encoding='utf-8'))
    package = execution['receipt']
    source_bindings = json.loads((JOB / 'ACCREDITATION_SOURCE_BINDINGS.json').read_text(encoding='utf-8'))
    pack = json.loads((JOB / 'accreditation_engine/ACCREDITATION_REVIEW_PACK.json').read_text(encoding='utf-8'))
    native = json.loads((JOB / 'accreditation_engine/ACCREDITATION_PROCESSING_RECEIPT.json').read_text(encoding='utf-8'))
    proof = json.loads((JOB / 'accreditation_engine/PROOF_MANIFEST.json').read_text(encoding='utf-8'))
    source_inventory = {row['source_id']: row for row in package['source_inventory']}
    expected_sources = {
        'CONTEXT': '01_customer_context.md', 'REGISTER': '02_evidence_register.csv',
        'EXCEPTION': '03_exception_note.md', 'INSTRUMENT': 'source_instrument.md',
        'CHECKLIST': 'criterion_4_checklist.md', 'STAFF': 'staff_records.csv',
    }
    source_hashes = {source_id: sha256(SOURCE_DIR / filename) for source_id, filename in expected_sources.items()}
    matrix = pack['standards_evidence_matrix']
    checks = {
        'catalog_customer_contract_is_enabled': execution.get('customer_packet_contract') == 'accreditation_framework_and_source_mapped_evidence',
        'held_customer_package_rendered': package.get('status') == 'HELD_REVIEW_PACKAGE_RENDERED',
        'framework_source_is_customer_checklist_and_unverified': source_bindings.get('framework', {}).get('source_kind') == 'customer_defined_checklist' and source_bindings.get('framework', {}).get('authority_and_applicability') == 'UNVERIFIED_REQUIRES_QUALITY_ASSURANCE_REVIEW',
        'criterion_is_quoted_from_framework_source': len(source_bindings.get('criteria', [])) == 1 and source_bindings['criteria'][0]['source_anchor']['source_id'] == source_bindings['framework']['source_id'],
        'evidence_is_separately_mapped_with_engine_ids': len(source_bindings.get('evidence', [])) == 3 and all(row.get('engine_evidence_id') for row in source_bindings['evidence']),
        'all_source_hashes_match_controlled_packet': all(source_inventory.get(source_id, {}).get('sha256') == digest for source_id, digest in source_hashes.items()),
        'unmapped_files_are_explicit': len(source_bindings.get('unmapped_sources', [])) == 3,
        'criterion_stays_contested_with_two_open_gaps': len(matrix) == 1 and matrix[0]['readiness_state'] == 'CONTESTED' and len(pack.get('gap_register', [])) == 2,
        'no_accreditation_decision_or_attestation': native.get('accreditation_decision_created') is False and native.get('institutional_attestation_created') is False and native.get('signatory_receipt_created') is False and proof.get('authority_created') is False,
        'external_release_refused': native.get('external_release_gate') == 'REFUSE' and proof.get('external_release') is False and execution.get('release_authorized') is False,
    }
    output_records = []
    for item in package.get('outputs', []):
        path = JOB / item['path']
        output_records.append({'path': str(path.relative_to(ROOT)), 'declared_sha256': item['sha256'], 'actual_sha256': sha256(path), 'hash_matches': sha256(path) == item['sha256']})
    checks['every_customer_output_hash_matches'] = bool(output_records) and all(item['hash_matches'] for item in output_records)
    if not all(checks.values()):
        raise SystemExit('HOMS Accreditation customer packet audit failed: ' + json.dumps(checks, sort_keys=True))
    artifacts = [
        {'path': str((SOURCE_DIR / filename).relative_to(ROOT)), 'sha256': digest}
        for source_id, filename in expected_sources.items() for digest in [source_hashes[source_id]]
    ]
    artifacts.extend({'path': row['path'], 'sha256': row['actual_sha256']} for row in output_records)
    artifacts.extend({'path': str(path.relative_to(ROOT)), 'sha256': sha256(path)} for path in [
        JOB / 'CUSTOMER_EXECUTION_RECEIPT.json', JOB / 'CUSTOMER_PACKAGE_RECEIPT.json',
        JOB / 'ACCREDITATION_SOURCE_BINDINGS.json', JOB / 'accreditation_engine/ACCREDITATION_PROCESSING_RECEIPT.json',
        JOB / 'accreditation_engine/PROOF_MANIFEST.json', JOB / 'accreditation_engine/ACCREDITATION_REVIEW_PACK.json',
    ])
    report = {
        'schema': 'dio.homs.accreditation.customer_packet_evidence.v1',
        'created_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        'product': 'HOMS Accreditation',
        'execution': {'framework_id': package['framework_id'], 'criterion_count': len(matrix), 'criterion_state': matrix[0]['readiness_state'], 'mapped_evidence_count': len(source_bindings['evidence']), 'open_gap_count': len(pack['gap_register']), 'unmapped_source_count': len(source_bindings['unmapped_sources'])},
        'checks': checks,
        'all_checks_pass': True,
        'outputs': output_records,
        'artifacts': artifacts,
        'claim_boundary': 'Controlled Ubuntu Skills Institute Criterion 4 case. The customer checklist is not an independently verified regulator standard; source statements are untrusted and unknown in freshness. This evidence establishes a current held source-mapped preparation route, not accreditation readiness, regulator acceptance, institutional attestation, or professional sign-off.',
    }
    OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(OUTPUT.relative_to(ROOT)), 'all_checks_pass': True, 'checks': len(checks), 'outputs': len(output_records), 'artifacts': len(artifacts)}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
