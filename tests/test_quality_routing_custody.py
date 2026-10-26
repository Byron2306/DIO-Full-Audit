import base64
import json
import pytest
from presence_core import router
from products.vesper_web_chat import create_session, post_message, load_session

FAILURES=['ControlDrift','DIO RegOps','DORA Vendor Assurance','Document Studio Localize','DossierOps','HOMS Curriculum','IncidentProof','Market Radar','ModelProof','Opportunity Foundry','PermitProof','PolicyProof','ProjectProof','PromotionProof','ReleaseProof']

@pytest.mark.parametrize('product', FAILURES)
@pytest.mark.parametrize('intent', ['general_info','status_request','intake_request'])
def test_explicit_site_context_survives_advisory_and_upload(tmp_path,monkeypatch,product,intent):
    monkeypatch.setenv('DIO_STATE_ROOT',str(tmp_path/'state'))
    monkeypatch.setenv('DIO_EVENT_LOG',str(tmp_path/'events.jsonl'))
    monkeypatch.setenv('DIO_PRESENCE_LLM_DRAFTS','0')
    monkeypatch.setattr(router,'classify_with_ollama',lambda *a,**k: {'intent':intent,'product':None,'confidence':.9})
    state=tmp_path/'sessions'; cid='VWC-QUALITY-00000001'
    create_session({'surface':'product_site','incarnation_hint':product},state_root=state,conversation_id=cid)
    result=post_message(cid,{'message':'Please review the supplied records for this request.','incarnation_hint':product,'attachments':[{'filename':'register.csv','mime_type':'text/csv','role':'customer_source','content_base64':base64.b64encode(b'id,note\nA,needs review\n').decode()}]},state_root=state,quarantine_output_root=tmp_path/'quarantine')
    session=load_session(cid,state_root=state)
    assert session['route']['incarnation']==product
    assert session['route']['state']=='RESOLVED'
    assert result['receipt']['authority_created'] is False
    for p in (state/'presence'/'quarantine').rglob('ATTACHMENT.json'):
        held=json.loads(p.read_text()); assert held['state']=='quarantined' and held['safe_to_parse'] is False and held['safe_to_execute'] is False
    assert session['external_send']=='REFUSE' and session['external_release']=='REFUSE'

@pytest.mark.parametrize('followup', ['Additional customer source files for the same governed request.','Actually, this is for a nonprofit. Does that change what you need?'])
def test_site_context_persists_and_explicit_change_wins(tmp_path,monkeypatch,followup):
    monkeypatch.setenv('DIO_STATE_ROOT',str(tmp_path/'state')); monkeypatch.setenv('DIO_EVENT_LOG',str(tmp_path/'events.jsonl')); monkeypatch.setenv('DIO_PRESENCE_LLM_DRAFTS','0')
    monkeypatch.setattr(router,'classify_with_ollama',lambda *a,**k: {'intent':'general_info','product':None,'confidence':.9})
    state=tmp_path/'sessions';cid='VWC-QUALITY-00000002'
    create_session({'surface':'product_site','incarnation_hint':'ContractProof'},state_root=state,conversation_id=cid)
    attachment={'filename':'source.txt','mime_type':'text/plain','role':'customer_source','content_base64':base64.b64encode(b'Untrusted source text.').decode()}
    for text in ['What do you need for ContractProof?',followup]:
        post_message(cid,{'message':text,'incarnation_hint':'ContractProof','attachments':[attachment]},state_root=state,quarantine_output_root=tmp_path/'quarantine')
        assert load_session(cid,state_root=state)['route']['incarnation']=='ContractProof'
    post_message(cid,{'message':'Switch to GrantProof, please.','incarnation_hint':'ContractProof'},state_root=state,quarantine_output_root=tmp_path/'quarantine')
    assert load_session(cid,state_root=state)['route']['incarnation']=='GrantProof'


def test_ambiguous_products_do_not_get_resolved_by_site_hint(tmp_path,monkeypatch):
    monkeypatch.setenv('DIO_STATE_ROOT',str(tmp_path/'state')); monkeypatch.setenv('DIO_EVENT_LOG',str(tmp_path/'events.jsonl')); monkeypatch.setenv('DIO_PRESENCE_LLM_DRAFTS','0')
    monkeypatch.setattr(router,'classify_with_ollama',lambda *a,**k: {'intent':'status_request','product':None,'confidence':.9})
    state=tmp_path/'sessions';cid='VWC-QUALITY-00000003'
    create_session({'surface':'product_site','incarnation_hint':'ContractProof'},state_root=state,conversation_id=cid)
    post_message(cid,{'message':'ContractProof or GrantProof?','incarnation_hint':'ContractProof'},state_root=state,quarantine_output_root=tmp_path/'quarantine')
    assert load_session(cid,state_root=state)['route']['state']=='NEEDS_YOU'


def test_sealed_ingress_custody_survives_wal_lifecycle(tmp_path):
    import gc,hashlib,sqlite3
    from products.professional_evidence_executor import _artifact_inventory
    root=tmp_path/'case';live=root/'VESPER_WEB_CHAT/sessions/VWC-QUALITY/INGRESS.sqlite';live.parent.mkdir(parents=True)
    con=sqlite3.connect(live);con.execute('pragma journal_mode=WAL')
    con.execute('create table ingress_receipts(event_key text primary key,body_sha256 text,state text,response_json text,created_at text,updated_at text)')
    con.execute('insert into ingress_receipts values(?,?,?,?,?,?)',('a','abc','completed','{}','now','now'));con.commit()
    rows=_artifact_inventory(root)
    con.close();gc.collect()
    for row in rows:
        p=root/row['path'];assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
    manifest=json.loads((root/'VESPER_WEB_CHAT/PROOF_CUSTODY/MANIFEST.json').read_text())
    assert manifest['snapshots'][0]['completed_events']==1
    assert not any(row['path'].endswith('sessions/VWC-QUALITY/INGRESS.sqlite') for row in rows)
    snapshot=root/manifest['snapshots'][0]['path']
    with sqlite3.connect(snapshot) as db: assert db.execute('select state from ingress_receipts').fetchone()[0]=='completed'
    snapshot.write_bytes(b'tampered')
    with pytest.raises(ValueError,match='custody'): _artifact_inventory(root)


def test_incomplete_ingress_cannot_be_sealed(tmp_path):
    import sqlite3
    from products.professional_evidence_executor import _artifact_inventory
    root=tmp_path/'case';live=root/'VESPER_WEB_CHAT/sessions/VWC-QUALITY/INGRESS.sqlite';live.parent.mkdir(parents=True)
    with sqlite3.connect(live) as con:
        con.execute('create table ingress_receipts(state text)');con.execute("insert into ingress_receipts values('received')")
    with pytest.raises(ValueError,match='incomplete'): _artifact_inventory(root)

@pytest.mark.parametrize('product', FAILURES)
def test_literal_customer_packet_reaches_exact_route(tmp_path,monkeypatch,product):
    from products.professional_evidence_vesper_gate import _prepare_vesper_front_door
    monkeypatch.setenv('DIO_STATE_ROOT',str(tmp_path/'state')); monkeypatch.setenv('DIO_EVENT_LOG',str(tmp_path/'events.jsonl')); monkeypatch.setenv('DIO_PRESENCE_LLM_DRAFTS','0')
    monkeypatch.setattr(router,'classify_with_ollama',lambda *a,**k: {'intent':'general_info','product':None,'confidence':.9})
    binding,case=_prepare_vesper_front_door(product,tmp_path/'out',now='2026-08-19T00:00:00+00:00')
    assert binding['resolved_incarnation']==product
    assert binding['all_product_source_bytes_rehydrated_from_vesper_quarantine'] is True
    assert binding['authority_created'] is False
