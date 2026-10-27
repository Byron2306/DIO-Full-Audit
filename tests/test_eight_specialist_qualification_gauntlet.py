"""The eight-offer gauntlet distinguishes evidence states and retains refusals."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.run_eight_specialist_qualification import (
    EIGHT_PRODUCTS,
    build_synthetic_packet,
    run_qualification,
)


def test_scenarios_produce_distinct_source_inputs_and_refuse_claim_promotion():
    packets = {scenario: build_synthetic_packet('AuditProof', scenario)
               for scenario in ('normal', 'messy', 'adversarial')}
    assert len({json.dumps(packet, sort_keys=True) for packet in packets.values()}) == 3
    assert len(packets['normal']['evidence']) == 1
    assert packets['normal']['issues'] == []
    assert packets['messy']['evidence'] == []
    assert packets['messy']['issues'] == []
    assert len(packets['adversarial']['evidence']) == 1
    assert len(packets['adversarial']['issues']) == 1
    assert packets['adversarial']['requirements'][0]['label'] == 'CERTIFIED FULL COMPLIANCE'
    assert all(p['owner_authorized'] is True for p in packets.values())


def test_actual_three_journeys_and_tamper_refusal_are_independently_measured(tmp_path: Path):
    out = tmp_path / 'qualification'
    summary = run_qualification(out, product_names=('AuditProof',), render_pdf=False)
    assert summary['schema'] == 'dio.eight_specialist_qualification.v1'
    assert summary['test_data'] == 'SYNTHETIC'
    assert summary['target_journeys'] == 3
    assert summary['passed'] == 3
    assert summary['failed'] == 0
    assert summary['tamper_refusal_verified'] == 1
    by_case = {row['scenario']: row for row in summary['journeys']}
    assert {name: row['disposition'] for name, row in by_case.items()} == {
        'normal': 'EVIDENCE_RECEIVED_UNVERIFIED',
        'messy': 'EVIDENCE_NOT_SUPPLIED',
        'adversarial': 'SOURCE_REPORTED_CHALLENGE',
    }
    assert all(row['native_review_state'] != 'SUPPORTED' for row in by_case.values())
    assert all(row['studio_finish_verified'] is True for row in by_case.values())
    assert all(row['status'] == 'PASS' for row in by_case.values())
    assert all(row['release_authorized'] is False for row in by_case.values())
    assert summary['professional_acceptance'] == 'NOT_GRANTED'
    assert summary['commercial_validation'] == 'UNPROVED'
    assert (out / 'EIGHT_SPECIALIST_QUALIFICATION_RECEIPT.json').is_file()
    for scenario in by_case:
        root = out / 'auditproof' / scenario
        assert (root / 'SPECIALIST_REVIEW_WORKSHEET.json').is_file()
        assert (root / 'CUSTOMER_SHARED_FINISH_RECEIPT.json').is_file()
        html = next((root / 'customer_delivery').glob('*.html')).read_text()
        assert 'CERTIFIED FULL COMPLIANCE' not in html


def test_qualification_cannot_replace_a_previous_evidence_run(tmp_path: Path):
    out = tmp_path / 'qualification'
    run_qualification(out, product_names=('AuditProof',), render_pdf=False)
    try:
        run_qualification(out, product_names=('AuditProof',), render_pdf=False)
    except ValueError as exc:
        assert 'empty' in str(exc) or 'already exists' in str(exc)
    else:
        raise AssertionError('qualification overwrote existing evidence')


def test_all_eight_offers_have_deterministic_synthetic_inputs():
    assert len(EIGHT_PRODUCTS) == 8
    assert len(set(EIGHT_PRODUCTS)) == 8
    for name in EIGHT_PRODUCTS:
        assert build_synthetic_packet(name, 'normal') == build_synthetic_packet(name, 'normal')
