import json
from pathlib import Path
from products.professional_evidence_corpus import materialize_customer_packet
from products.professional_evidence_projection import load_packet, ai_trust_projection
from products.ai_trust.core import build_trust_envelope


def test_narrative_ai_packet_never_becomes_invented_fingerprints_or_pass(tmp_path):
    packet=load_packet(Path(materialize_customer_packet('Agent Authority',tmp_path)['packet_dir']))
    projected=ai_trust_projection(packet,source_type='ai_agent',intended_use='Internal claim review',inject_actions=True,changed=True)
    assert projected['evaluations']==[]
    assert not projected['baseline']
    assert not projected['system'].get('model',{}).get('fingerprint')
    assert not projected.get('claimed_output_sha256') and not projected.get('observed_output_sha256')
    assert projected['requested_actions']==[] and projected['allowed_capabilities']==[]
    assert projected['customer_declarations'][0]['source_locator']=='R-01'
    env=build_trust_envelope('dio_agentauthority',projected,now='2026-08-19T00:00:00+00:00')
    states={r['dimension']:r['state'] for r in env['dimensions']}
    assert states['identity']!='SUPPORTED' and states['evaluation']=='UNKNOWN'
    assert states['integrity']=='UNKNOWN' and states['drift']=='UNKNOWN'
    assert states['tool_safety']=='REFUSE' # poisoned source is still detected without inventing a tool request
    assert env['authority_created'] is False and env['external_release']=='REFUSE'


def test_offer_customer_view_preserves_inputs_and_unvalidated_price_tests(tmp_path):
    from products.professional_evidence_native import run_offer_lab
    packet=load_packet(Path(materialize_customer_packet('Offer Lab',tmp_path/'in')['packet_dir']))
    run_offer_lab(packet,tmp_path/'out',now='2026-08-19T00:00:00+00:00')
    offer=json.loads((tmp_path/'out/BOUNDED_OFFER.json').read_text()); view=(tmp_path/'out/BOUNDED_OFFER.md').read_text()
    for field in ['target_buyer_hypothesis','required_inputs','allowed_claims','price_test_options_zar','customer_constraints']:
        values=offer[field] if isinstance(offer[field],list) else [offer[field]]
        assert all(str(v) in view for v in values)
    assert 'not validated' in view.lower()


def test_ai_customer_declarations_reach_all_customer_views(tmp_path):
    from products.ai_trust.runner import run_ai_trust
    from pypdf import PdfReader
    import io,zipfile
    packet=load_packet(Path(materialize_customer_packet('DIO AI Assurance',tmp_path/'in')['packet_dir']))
    projected=ai_trust_projection(packet,source_type='ai_system',intended_use='Internal customer review')
    result=run_ai_trust('dio_aitrustproof',projected,output_dir=tmp_path/'out',operator_id='quality-test',now='2026-08-19T00:00:00+00:00')
    with zipfile.ZipFile(tmp_path/'out/AI_TRUST_DOSSIER.docx') as z: word=z.read('word/document.xml').decode()
    pdf='\n'.join(p.extract_text() for p in PdfReader(tmp_path/'out/AI_TRUST_DOSSIER.pdf').pages)
    html=(tmp_path/'out/AI_TRUST_DOSSIER.html').read_text()
    for view in (word,pdf,html):
        assert 'Customer Operations' in view and 'R-01' in view
        assert 'Customer declarations' in view
    data=json.loads((tmp_path/'out/AI_TRUST_DOSSIER.json').read_text())
    assert data['provenance_manifest']['customer_declarations']==projected['customer_declarations']
