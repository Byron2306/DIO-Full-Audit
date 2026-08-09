import json
from presence_core.engine import process_envelope
from presence_core.identity import create_status_binding, revoke_binding

def make_root(tmp_path):
    (tmp_path/'config').mkdir(); (tmp_path/'telemetry').mkdir(); (tmp_path/'state/commerce/orders').mkdir(parents=True)
    (tmp_path/'config/routes.json').write_text(json.dumps({'routes':[{'product':'homs','keywords':['homs']}]},indent=2))
    (tmp_path/'state/commerce/orders/ORDER-1.json').write_text(json.dumps({'schema':'dio.local_commerce_order_state.v1','order_id':'ORDER-1','payment_state':'paid','amount_minor':999900,'currency':'ZAR','provider':'paypal','fulfilment_released':False}))
    return tmp_path

def cfg(): return {'state_root':'state/presence','event_log':'telemetry/dio_events.jsonl','routes_path':'config/routes.json','attachments':{'max_bytes':1024}}

def test_status_requires_binding_then_discloses_minimal_state(tmp_path,monkeypatch):
    root=make_root(tmp_path); monkeypatch.setenv('DIO_PRESENCE_IDENTITY_SALT','i'*40)
    env={'channel':'telegram','external_user_id':'123','text':'where is my order?','message_type':'text','_trusted_edge_role':'public'}
    first=process_envelope(env,root,cfg()); assert 'identity' in first['reply']['text'].lower(); cid=first['conversation_id']
    create_status_binding(root/'state/presence',cid,['ORDER-1'],'operator matched customer against payment receipt')
    second=process_envelope(env,root,cfg()); assert second['status'][0]['payment_state']=='paid'; assert '999900' not in second['reply']['text']; assert 'paypal' not in second['reply']['text'].lower()

def test_revoked_binding_closes_status_again(tmp_path,monkeypatch):
    root=make_root(tmp_path); monkeypatch.setenv('DIO_PRESENCE_IDENTITY_SALT','i'*40)
    env={'channel':'whatsapp','external_user_id':'27820000000','text':'payment status please','message_type':'text','_trusted_edge_role':'public'}
    first=process_envelope(env,root,cfg()); cid=first['conversation_id']; create_status_binding(root/'state/presence',cid,['ORDER-1'],'manual phone verification'); revoke_binding(root/'state/presence',cid)
    again=process_envelope(env,root,cfg()); assert again['status'] is None and 'identity' in again['reply']['text'].lower()
