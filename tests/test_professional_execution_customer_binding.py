from __future__ import annotations

import json
from pathlib import Path

from products.professional_evidence_corpus import materialize_customer_packet
from products.professional_evidence_enrichment import enrich_customer_packet
from products.professional_evidence_projection import load_packet


def packet_for(name: str, root: Path):
    receipt = materialize_customer_packet(name, root)
    packet_dir = root / name.lower().replace(' ', '-') / 'CUSTOMER_PACKET'
    enrich_customer_packet(name, packet_dir)
    return load_packet(packet_dir)


def test_hymark_local_output_budget_can_complete_multi_criterion_json(monkeypatch, tmp_path):
    from scripts.run_homs_hymark_batch import configure_provider
    monkeypatch.delenv('HOMS_AI_MAX_TOKENS', raising=False)
    configure_provider(tmp_path / 'absent.env', 'ollama', 'granite3.2:2b')
    import os
    assert int(os.environ['HOMS_AI_MAX_TOKENS']) >= 3000


def test_campaign_inputs_follow_customer_semantic_brief(tmp_path):
    from products.professional_evidence_red13_compat import _campaign_inputs
    packet = packet_for('Campaign Lab', tmp_path)
    brief = packet['packet_dir'] / 'SOURCES' / 'campaign_brief.json'
    assert brief.is_file(), 'customer offer needs explicit semantic input, not a hardcoded executor offer'
    supplied = json.loads(brief.read_text())
    product, audience = _campaign_inputs(packet)
    assert product['promise'] == supplied['product']['promise']
    assert audience['pain'] == supplied['audience']['pain']
    supplied['product']['promise'] = 'Prepare a bounded inventory reconciliation pilot.'
    supplied['audience']['pain'] = 'Warehouse stock counts conflict across shifts.'
    brief.write_text(json.dumps(supplied))
    product2, audience2 = _campaign_inputs(packet)
    assert product2['promise'] == supplied['product']['promise']
    assert audience2['pain'] == supplied['audience']['pain']
    assert product2['proof_asset'] == product['proof_asset']


def test_vesper_draft_and_route_use_supplied_intake_not_bluebird_template(tmp_path):
    from products.professional_evidence_execution import _run_vesper
    packet = packet_for('Vesper Desk', tmp_path)
    packet['intake']['organisation'] = 'Mosaic Research'
    packet['intake']['request'] = 'Route the research chapter to academic review before Tuesday.'
    source = packet['packet_dir'] / 'SOURCES' / 'intake_email.json'
    source.write_text(json.dumps({'subject': 'Research chapter for Tuesday review', 'sender': 'Research coordinator', 'body': 'Please review the literature chapter and source references.', 'attachment_names': 'chapter.md;references.bib', 'urgency': 'Tuesday', 'intent': 'academic literature review'}))
    output = tmp_path / 'vesper-output'
    output.mkdir()
    result = _run_vesper(packet, output)
    draft = Path(result['receipt']['draft_path']).read_text()
    assert 'Research chapter for Tuesday review' in draft
    assert 'Bluebird' not in draft
    assert 'Amendment 1' not in draft
    job = json.loads(Path(result['receipt']['job_path']).read_text())
    assert 'Research chapter for Tuesday review' in json.dumps(job)
    assert job['approval']['state'] == 'pending'


def test_profile_review_surfaces_source_reported_defects_as_issues(tmp_path):
    from products.professional_evidence_projection import review_projection
    packet = packet_for('HOMS Moderate', tmp_path)
    projection = review_projection(packet, profile_id='homs_moderate')
    concerns = ' '.join(item['hypothesis'] for item in projection['issues'])
    assert '10 marks in the paper but 8 marks' in concerns
    assert 'supplies no starting quantity' in concerns


def test_profile_review_flags_late_evidence_for_auditor_without_issuing_opinion(tmp_path):
    from products.professional_evidence_projection import review_projection
    packet = packet_for('AuditProof', tmp_path)
    projection = review_projection(packet, profile_id='auditproof')
    concerns = ' '.join(item['hypothesis'] for item in projection['issues'])
    assert '19 days after the policy deadline' in concerns
    assert 'disabled 6 days late' in concerns
    assert all(item['challenge_type'] == 'alternative_hypothesis' for item in projection['issues'])


def test_homs_assessment_preserves_customer_mark_scale(tmp_path):
    from products.professional_evidence_projection import homs_assess_projection
    packet = packet_for('HOMS Assess', tmp_path)
    original = json.loads((packet['packet_dir'] / 'SOURCES/hymark_input/rubric.json').read_text())
    target = tmp_path / 'hymark-projected'
    homs_assess_projection(packet, target)
    projected = json.loads((target / 'rubric.json').read_text())
    assert [row['weight'] for row in projected['criteria']] == [row['marks'] for row in original['criteria']]
    assert projected['total_marks'] == sum(row['marks'] for row in original['criteria'])


def test_market_radar_fetches_customer_scope_and_records_source_hash(tmp_path, monkeypatch):
    import io
    from market_sensorium.cycle import MarketSensoriumCycle
    import urllib.request
    feed = b'<rss><channel><item><title>SME evidence management offer</title><link>https://example.org/offer</link><pubDate>Tue, 27 Oct 2026 09:00:00 GMT</pubDate></item></channel></rss>'
    requests = []
    def fetch(request, timeout):
        requests.append(request.full_url)
        return io.BytesIO(feed)
    monkeypatch.setattr(urllib.request, 'urlopen', fetch)
    result = MarketSensoriumCycle(tmp_path).run_customer_scope(
        queries=['South Africa evidence management SME pricing'],
        packet_fingerprint='sha256:customer', output_dir=tmp_path / 'scoped',
    )
    assert len(requests) == 1
    assert 'South+Africa+evidence+management+SME+pricing' in requests[0]
    assert result['observations'][0]['url'] == 'https://example.org/offer'
    assert len(result['sources'][0]['sha256']) == 64
    assert result['market_demand_claimed'] is False
    assert result['authority_created'] is False
    assert result['mail_ingress_refresh'] == 'not_requested'
    from products.professional_evidence_final_compat import _normalise_market_receipt
    assert _normalise_market_receipt(result)['market_demand_claimed'] is False


def test_market_radar_refuses_empty_refresh_instead_of_claiming_live_signals(tmp_path, monkeypatch):
    import io
    import urllib.request
    import pytest
    from market_sensorium.cycle import MarketSensoriumCycle
    monkeypatch.setattr(urllib.request, 'urlopen', lambda *args, **kwargs: io.BytesIO(b'<rss><channel/></rss>'))
    with pytest.raises(RuntimeError, match='no public observations'):
        MarketSensoriumCycle(tmp_path).run_customer_scope(queries=['scope'], packet_fingerprint='sha256:customer', output_dir=tmp_path / 'scoped')


def test_hymark_refuses_fabricated_submission_quotes():
    from scripts.run_homs_hymark_batch import assessment_response_is_complete
    rubric = {'criteria': [{'name': 'Q5', 'weight': 3}], 'total_marks': 3}
    raw = {'criteria_scores': {'Q5': {'score': 2, 'feedback': 'Check direction.', 'quotes': ['The student used no units.']}}}
    assert assessment_response_is_complete(raw, rubric, submission_text='Q5: v = 14 m.s^-1 east.') is False
    raw['criteria_scores']['Q5']['quotes'] = ['v = 14 m.s^-1 east.']
    assert assessment_response_is_complete(raw, rubric, submission_text='Q5: v = 14 m.s^-1 east.') is True


def test_vamp_customer_projection_registers_actual_legacy_sha1(tmp_path):
    import sqlite3
    from products.professional_evidence_customer_surface_compat import _build_vamp_database_v2
    from adapters.vamp.snapshot_pipeline import _verify_source_integrity
    packet = packet_for('VAMP Performance', tmp_path)
    db = _build_vamp_database_v2(packet, tmp_path / 'vamp-projection' / 'progress.db')
    with sqlite3.connect(db) as connection:
        rows = connection.execute('SELECT file_path,sha1 FROM evidence').fetchall()
    assert rows
    for path, registered_hash in rows:
        ok, reason = _verify_source_integrity(Path(path), registered_hash)
        assert ok, reason
