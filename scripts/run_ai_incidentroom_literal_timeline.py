#!/usr/bin/env python3
"""Run a held AI IncidentRoom case with source-bound literal time markers."""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SOURCE = ROOT / 'acceptance_runs/68-product-sellability-20261027/AI_INCIDENTROOM_SOURCE_ISSUE_LINEAGE_20261101_V1/SOURCE_PACKET.json'
OUT = ROOT / 'acceptance_runs/68-product-sellability-20261027/AI_INCIDENTROOM_LITERAL_TIMELINE_20261102_V1'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f'output directory must be new or empty: {OUT}')
    packet = json.loads(SOURCE.read_text(encoding='utf-8'))
    from products.customer_product_router import run_customer_product
    execution = run_customer_product('AI IncidentRoom', packet, OUT, render_pdf=False)
    marker_path = OUT / 'INCIDENT_LITERAL_TIME_MARKERS.json'
    markers = json.loads(marker_path.read_text(encoding='utf-8'))
    sources = {row['source_id']: row['text'] for row in packet['sources']}
    for row in markers['markers']:
        source_bytes = sources[row['source_id']].encode('utf-8')
        exact = source_bytes[row['source_byte_start']:row['source_byte_end_exclusive']].decode('utf-8')
        if exact != row['literal'] or hashlib.sha256(exact.encode('utf-8')).hexdigest() != row['literal_sha256']:
            raise ValueError('literal marker failed exact source byte and hash validation')
    by_source = {row['source_id']: row for row in markers['markers']}
    if (markers.get('schema') != 'dio.incident_review.literal_time_markers.v1'
            or by_source.get('INCIDENT', {}).get('precision') != 'DATE_ONLY'
            or by_source.get('LOG', {}).get('precision') != 'TIME_WITH_EXPLICIT_OFFSET'
            or 'RESPONSE' not in {row['source_id'] for row in markers.get('undated_sources', [])}
            or markers.get('release_authorized') is not False
            or execution.get('release_authorized') is not False
            or execution.get('external_effects') is not False):
        raise ValueError('IncidentRoom literal timeline failed precision or held-release checks')
    package_path = OUT / 'CUSTOMER_PACKAGE_RECEIPT.json'
    evidence = {
        'schema': 'dio.ai_incidentroom.literal_time_marker_execution.v1',
        'product': 'AI IncidentRoom',
        'source_packet_sha256': sha(SOURCE),
        'marker_artifact_sha256': sha(marker_path),
        'customer_package_sha256': sha(package_path),
        'marker_count': len(markers['markers']),
        'undated_source_ids': sorted(row['source_id'] for row in markers['undated_sources']),
        'precision_states': sorted(set(row['precision'] for row in markers['markers'])),
        'every_marker_exact_source_bound': True,
        'domain_or_causality_conclusion_created': False,
        'release_authorized': False,
        'external_effects': False,
        'claim_boundary': markers['claim_boundary'],
        'fixture_boundary': 'Synthetic source packet verifies literal date/time extraction and byte anchoring only; it does not verify occurrence, incident chronology, impact or causation.',
    }
    evidence_path = OUT / 'INCIDENT_LITERAL_TIMELINE_EXECUTION_EVIDENCE.json'
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
