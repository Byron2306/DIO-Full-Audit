import base64, hashlib
from pathlib import Path
import pytest
from presence_core.attachments import validate_and_store_attachment, AttachmentError

def env(data:bytes,name='proof.pdf',mime='application/pdf'):
    return {'provider':'telegram','provider_file_id':'f1','file_name':name,'mime_type':mime,'file_size':len(data),'sha256':hashlib.sha256(data).hexdigest(),'content_b64':base64.b64encode(data).decode()}

def test_pdf_is_quarantined_not_processed(tmp_path):
    data=b'%PDF-1.7\nDIO TEST\n'; rec=validate_and_store_attachment(tmp_path,'CONV-X',env(data),{'attachments':{'max_bytes':1024}})
    assert rec['state']=='quarantined' and rec['safe_to_parse'] is False and rec['safe_to_execute'] is False
    assert (tmp_path/rec['blob_path']).read_bytes()==data
    assert Path(rec['blob_path']).name=='content.blob'

def test_executable_extension_rejected(tmp_path):
    with pytest.raises(AttachmentError): validate_and_store_attachment(tmp_path,'CONV-X',env(b'MZ','invoice.exe','application/octet-stream'),{'attachments':{'max_bytes':1024}})

def test_bad_magic_rejected(tmp_path):
    with pytest.raises(AttachmentError): validate_and_store_attachment(tmp_path,'CONV-X',env(b'not a pdf'),{'attachments':{'max_bytes':1024}})

def test_oversize_rejected(tmp_path):
    with pytest.raises(AttachmentError): validate_and_store_attachment(tmp_path,'CONV-X',env(b'%PDF-'+b'x'*2000),{'attachments':{'max_bytes':100}})
