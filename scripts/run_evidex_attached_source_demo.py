#!/usr/bin/env python3
"""Exercise Evidex original-file intake with a held synthetic review packet."""
from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / 'acceptance_runs/68-product-sellability-20261027/EVIDEX_ATTACHED_SOURCE_DEMO_20261102_V1'
EVIDENCE = OUT.parent / 'EVIDEX_ATTACHED_SOURCE_DEMO_20261102_V1.json'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def attachment(source_id: str, filename: str, media_type: str, content: str) -> dict:
    return {'source_id': source_id, 'filename': filename, 'media_type': media_type,
            'content_base64': base64.b64encode(content.encode('utf-8')).decode('ascii')}


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f'output directory must be new or empty: {OUT}')
    claim = 'Claim C-2026 reports 10 workshops delivered.'
    register = 'Attendance register records 9 workshops delivered.'
    files = [
        attachment('CLAIM-ORIGINAL', 'claim-summary.txt', 'text/plain', claim),
        attachment('REGISTER-ORIGINAL', 'attendance-register.txt', 'text/plain', register),
        attachment('KPI-CSV', 'quarterly-kpis.csv', 'text/csv', 'KPI,Target,Actual\nWorkshops delivered,8,9\nLearners reached,120,137\n'),
    ]
    packet = {
        'owner_authorized': True,
        'controlled_synthetic_demo': True,
        'case_id': 'SYNTHETIC-EVIDEX-ATTACHED-SOURCE-INTAKE',
        'title': 'Synthetic evidence review from original file attachments',
        'organisation': 'Synthetic QA fixture',
        'reporting_period': {'start': '2026-01-01', 'end': '2026-12-31'},
        'evidence_files': files,
        'records': [
            {'record_id': 'claim-2026', 'source_id': 'CLAIM-ORIGINAL', 'quote': claim,
             'period_start': '2026-01-01', 'period_end': '2026-12-31', 'population_id': 'programme-X'},
            {'record_id': 'register-2026', 'source_id': 'REGISTER-ORIGINAL', 'quote': register,
             'period_start': '2026-01-01', 'period_end': '2026-12-31', 'population_id': 'programme-X'},
        ],
    }
    from products.customer_product_router import run_customer_product

    result = run_customer_product('Evidex EvidenceOps', packet, OUT, render_pdf=False)
    receipt = result.get('receipt') or {}
    manifest = json.loads((OUT / 'EVIDEX_SOURCE_FILE_MANIFEST.json').read_text())
    review = json.loads((OUT / 'CUSTOMER_EVIDENCE_REVIEW.json').read_text())
    persisted_packet = json.loads((OUT / 'SOURCE_PACKET.json').read_text())
    if (result.get('requested_product') != 'Evidex EvidenceOps'
            or result.get('release_authorized') is not False or result.get('external_effects') is not False
            or receipt.get('evidence_file_count') != 3 or receipt.get('original_evidence_files_preserved') is not True
            or manifest.get('file_count') != 3 or manifest.get('source_authenticity_verified') is not False
            or review.get('support_adjudicated') is not False or review.get('release_authorized') is not False
            or len(review.get('quantity_comparisons') or []) != 1
            or review['quantity_comparisons'][0].get('state') != 'DECLARED_SCOPE_MATCH_QUANTITY_DIFFERENCE_REQUIRES_REVIEW'
            or any('content_base64' in row for row in persisted_packet.get('evidence_files') or [])):
        raise ValueError('Evidex attachment route failed source-preservation or held-review contract')
    checked = []
    for row in manifest['files']:
        path = OUT / row['path']
        raw = path.read_bytes()
        if len(raw) != row['bytes'] or sha(raw) != row['sha256']:
            raise ValueError(f'Original source attachment failed byte/hash verification: {row["source_id"]}')
        checked.append({'source_id': row['source_id'], 'path': row['path'], 'bytes': row['bytes'], 'sha256': row['sha256']})
    inventory = []
    for row in result.get('artifacts') or []:
        path = OUT / row['path']
        if not path.is_file() or path.stat().st_size != row['bytes'] or sha(path.read_bytes()) != row['sha256']:
            raise ValueError(f'Evidex customer output inventory mismatch: {row["path"]}')
        inventory.append({'path': row['path'], 'bytes': row['bytes'], 'sha256': row['sha256']})
    evidence = {'schema': 'dio.evidex.attached_source_execution.v1', 'product': 'Evidex EvidenceOps',
        'route': OUT.relative_to(ROOT).as_posix(), 'customer_packet_sha256': result['customer_packet_sha256'],
        'attachment_count': len(checked), 'verified_original_files': checked,
        'comparison_count': len(review['quantity_comparisons']), 'quantity_difference_state': review['quantity_comparisons'][0]['state'],
        'source_authenticity_verified': False, 'support_adjudicated': False, 'release_authorized': False,
        'external_effects': False, 'synthetic_acceptance_only': True, 'artifact_count': len(inventory),
        'artifacts': inventory, 'all_output_hashes_verified': True}
    EVIDENCE.write_text(json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'route': evidence['route'], 'attachment_count': len(checked), 'artifact_count': len(inventory),
                      'all_output_hashes_verified': True, 'support_adjudicated': False, 'release_authorized': False}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
