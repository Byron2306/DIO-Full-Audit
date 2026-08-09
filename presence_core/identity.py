from __future__ import annotations
import secrets
from pathlib import Path
from typing import Any
from .state import now, read_json, write_json, safe

class IdentityBindingError(ValueError): pass

def binding_path(root:Path,conversation_id:str)->Path:
    return root/'identity_bindings'/f'{safe(conversation_id)}.json'

def create_status_binding(root:Path,conversation_id:str,order_ids:list[str],verification_method:str,verified_by:str='operator')->dict[str,Any]:
    cleaned=[]
    for oid in order_ids:
        oid=str(oid).strip()
        if oid and oid not in cleaned: cleaned.append(oid)
    if not cleaned: raise IdentityBindingError('At least one order id is required.')
    payload={
        'schema':'dio.presence_identity_binding.v2','binding_id':'BIND-'+secrets.token_hex(7).upper(),
        'conversation_id':conversation_id,'state':'verified','capabilities':['status_lookup'],
        'order_ids':cleaned,'verification_method':verification_method,'verified_by':verified_by,
        'verified_at':now(),'revoked_at':None
    }
    write_json(binding_path(root,conversation_id),payload); return payload

def load_status_binding(root:Path,conversation_id:str)->dict[str,Any]|None:
    p=binding_path(root,conversation_id)
    if not p.exists(): return None
    item=read_json(p)
    if item.get('state')!='verified' or 'status_lookup' not in item.get('capabilities',[]): return None
    return item

def revoke_binding(root:Path,conversation_id:str)->dict[str,Any]:
    item=load_status_binding(root,conversation_id)
    if not item: raise IdentityBindingError('No verified binding exists for this conversation.')
    item['state']='revoked'; item['revoked_at']=now(); write_json(binding_path(root,conversation_id),item); return item

def bound_order_status(dio_root:Path,binding:dict[str,Any])->list[dict[str,Any]]:
    out=[]
    for oid in binding.get('order_ids',[]):
        p=dio_root/'state'/'commerce'/'orders'/f'{safe(str(oid))}.json'
        if not p.exists():
            out.append({'order_id':oid,'state':'not_found_in_local_commerce_state'}); continue
        raw=read_json(p)
        out.append({
            'order_id':raw.get('order_id',oid),
            'payment_state':raw.get('payment_state','unknown'),
            'fulfilment_released':bool(raw.get('fulfilment_released',False)),
            'state':'found'
        })
    return out
