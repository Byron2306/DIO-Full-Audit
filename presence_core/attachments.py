from __future__ import annotations
import base64, hashlib, json, os, re, secrets
from pathlib import Path
from typing import Any
from .state import now, write_json

ALLOWED_EXTENSIONS={'.pdf','.docx','.xlsx','.pptx','.csv','.txt','.png','.jpg','.jpeg'}
BLOCKED_EXTENSIONS={'.exe','.com','.bat','.cmd','.sh','.ps1','.js','.mjs','.html','.htm','.svg','.zip','.7z','.rar','.docm','.xlsm','.pptm','.jar','.apk','.deb','.rpm'}
MIME_BY_EXT={
    '.pdf':{'application/pdf'},
    '.docx':{'application/vnd.openxmlformats-officedocument.wordprocessingml.document','application/zip','application/octet-stream'},
    '.xlsx':{'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','application/zip','application/octet-stream'},
    '.pptx':{'application/vnd.openxmlformats-officedocument.presentationml.presentation','application/zip','application/octet-stream'},
    '.csv':{'text/csv','text/plain','application/csv','application/octet-stream'},
    '.txt':{'text/plain','application/octet-stream'},
    '.png':{'image/png','application/octet-stream'},
    '.jpg':{'image/jpeg','application/octet-stream'},
    '.jpeg':{'image/jpeg','application/octet-stream'},
}

class AttachmentError(ValueError): pass

def _safe_filename(name:str)->str:
    name=(name or 'attachment').replace('\\','/').split('/')[-1]
    name=re.sub(r'[^A-Za-z0-9._ -]+','_',name).strip(' .')[:180]
    return name or 'attachment'

def _magic_ok(ext:str,data:bytes)->bool:
    if ext=='.pdf': return data.startswith(b'%PDF-')
    if ext in {'.docx','.xlsx','.pptx'}: return data.startswith(b'PK\x03\x04')
    if ext=='.png': return data.startswith(b'\x89PNG\r\n\x1a\n')
    if ext in {'.jpg','.jpeg'}: return data.startswith(b'\xff\xd8\xff')
    return True

def validate_and_store_attachment(root:Path, conversation_id:str, attachment:dict[str,Any], cfg:dict[str,Any]) -> dict[str,Any]:
    name=_safe_filename(str(attachment.get('file_name') or 'attachment'))
    ext=Path(name).suffix.lower()
    if ext in BLOCKED_EXTENSIONS or ext not in ALLOWED_EXTENSIONS:
        raise AttachmentError(f'Attachment type {ext or "(none)"} is not allowed.')
    try: data=base64.b64decode(str(attachment.get('content_b64') or ''),validate=True)
    except Exception as exc: raise AttachmentError('Attachment payload is not valid base64.') from exc
    max_bytes=int(cfg.get('attachments',{}).get('max_bytes',8*1024*1024))
    if not data: raise AttachmentError('Attachment is empty.')
    if len(data)>max_bytes: raise AttachmentError(f'Attachment exceeds DIO public limit of {max_bytes} bytes.')
    declared=int(attachment.get('file_size') or len(data))
    if declared!=len(data): raise AttachmentError('Attachment byte count does not match provider metadata.')
    actual_sha=hashlib.sha256(data).hexdigest()
    declared_sha=str(attachment.get('sha256') or '').lower()
    if declared_sha and declared_sha!=actual_sha: raise AttachmentError('Attachment SHA-256 mismatch.')
    mime=str(attachment.get('mime_type') or 'application/octet-stream').split(';',1)[0].lower().strip()
    if mime not in MIME_BY_EXT.get(ext,{mime}): raise AttachmentError('Attachment MIME type does not match its extension.')
    if not _magic_ok(ext,data): raise AttachmentError('Attachment file signature does not match its extension.')
    aid='ATT-'+secrets.token_hex(8).upper(); qdir=root/'quarantine'/aid; qdir.mkdir(parents=True,exist_ok=False)
    blob=qdir/'content.blob'; blob.write_bytes(data)
    try: os.chmod(blob,0o600)
    except OSError: pass
    record={
        'schema':'dio.presence_attachment.v2','attachment_id':aid,'conversation_id':conversation_id,
        'state':'quarantined','quarantine_only':True,'safe_to_execute':False,'safe_to_parse':False,
        'original_file_name':name,'extension':ext,'mime_type':mime,'size_bytes':len(data),'sha256':actual_sha,
        'provider':attachment.get('provider'),'provider_file_id':attachment.get('provider_file_id'),
        'created_at':now(),'blob_path':str(blob.relative_to(root)),
        'authority':{'automatic_processing':False,'operator_review_required':True}
    }
    write_json(qdir/'ATTACHMENT.json',record)
    return record
