import sys
from pathlib import Path
import pytest
HF=Path(__file__).resolve().parents[1]/'hf_space'
if not HF.exists():
    pytest.skip('HF edge source is shipped beside the overlay, not installed into the DIO core.', allow_module_level=True)
sys.path.insert(0,str(HF))
from presence_edge.telegram import extract

def test_telegram_start_payload_is_bounded_hint():
    u={'message':{'message_id':1,'from':{'id':123,'first_name':'A'},'chat':{'id':123},'text':'/start MKT-HOMS-42'}}
    m=extract(u); assert m['start_payload']=='MKT-HOMS-42'

def test_telegram_start_payload_rejects_weird_characters():
    u={'message':{'message_id':1,'from':{'id':123},'chat':{'id':123},'text':'/start ../../bad'}}
    m=extract(u); assert m['start_payload'] is None
