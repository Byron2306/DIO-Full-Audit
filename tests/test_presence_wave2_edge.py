import hashlib,hmac,os,sys,time
from pathlib import Path
import pytest
HF=Path(__file__).resolve().parents[1]/'hf_space'
if not HF.exists(): pytest.skip('HF edge source is shipped beside overlay.',allow_module_level=True)
sys.path.insert(0,str(HF))
from presence_edge.whatsapp import verify_signature,extract_messages
from presence_edge.webchat import issue,verify,campaign_hint
from presence_edge.telegram import extract

def test_whatsapp_signature(monkeypatch):
    monkeypatch.setenv('WHATSAPP_APP_SECRET','s'*40); body=b'{"object":"whatsapp_business_account"}'; sig='sha256='+hmac.new(('s'*40).encode(),body,hashlib.sha256).hexdigest(); assert verify_signature(body,sig); assert not verify_signature(body+b'x',sig)

def test_whatsapp_text_extract():
    p={'entry':[{'changes':[{'value':{'metadata':{'phone_number_id':'42'},'contacts':[{'wa_id':'2782','profile':{'name':'A'}}],'messages':[{'from':'2782','id':'wamid.1','type':'text','text':{'body':'I need HOMS'}}]}}]}]}
    m=extract_messages(p)[0]; assert m['external_user_id']=='2782' and m['text']=='I need HOMS' and m['phone_number_id']=='42'

def test_webchat_session_signed(monkeypatch):
    monkeypatch.setenv('WEBCHAT_SESSION_SECRET','w'*40); t=issue(); assert verify(t); assert verify(t+'x') is None; assert campaign_hint('MKT-HOMS-42')=='MKT-HOMS-42'; assert campaign_hint('../../bad') is None

def test_telegram_document_metadata_preserved():
    u={'message':{'message_id':1,'from':{'id':123},'chat':{'id':123},'document':{'file_id':'f','file_name':'a.pdf','mime_type':'application/pdf','file_size':12}}}
    m=extract(u); assert m['message_type']=='document' and m['document']['file_size']==12
