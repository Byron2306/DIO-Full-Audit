#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
import requests
import uvicorn
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from conversation_core.context import write_conversation_context
from conversation_core.presence import append_presence_turn, build_presence_conversation_context, incoming_provider_message_id
from presence_core.config import load_config
from presence_core.engine import process_envelope
from presence_core.identity import create_status_binding, revoke_binding
from presence_core.persona import apply_persona_response
from presence_core.signing import verify_body, SignatureError
from presence_core.state import list_needs_you, operator_summary, read_json, safe

app=FastAPI(title='DIO Presence Bridge',version='2.1.0',docs_url=None,redoc_url=None)
CFG=load_config(); REPLAY:dict[str,float]={}

def bearer_ok(auth:str|None)->bool:
    token=os.getenv('DIO_PRESENCE_OPERATOR_TOKEN','')
    return bool(token and auth==f'Bearer {token}')

def prune():
    cutoff=time.time()-600
    for k,v in list(REPLAY.items()):
        if v<cutoff: REPLAY.pop(k,None)

def core_telegram_replies_enabled() -> bool:
    raw = os.getenv("DIO_PRESENCE_CORE_TELEGRAM_REPLIES", "1")
    return raw.strip().lower() not in {"0", "false", "no", "off"}

def send_telegram_reply_from_core(envelope: dict, result: dict) -> tuple[bool, str | None, str | None]:
    if not core_telegram_replies_enabled():
        return False, "core_telegram_replies_disabled", None
    if envelope.get("channel") != "telegram":
        return False, "not_telegram", None
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = ((envelope.get("metadata") or {}).get("telegram_chat_id"))
    text = (((result.get("reply") or {}).get("text")) or "").strip()
    if not token or not chat_id or not text:
        return False, "missing_token_chat_or_text", None
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text[:4096]},
        timeout=12,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        return False, str(payload.get("description") or "telegram_api_error"), None
    provider_message_id = str(((payload.get("result") or {}).get("message_id")) or "") or None
    return True, None, provider_message_id

def _presence_root() -> Path:
    return ROOT/CFG.get('state_root','state/presence')

def _persist_live_context(envelope: dict, result: dict, sent: bool, provider_message_id: str | None) -> None:
    conversation_id=str(result.get('conversation_id') or '')
    if not conversation_id:
        return
    presence_root=_presence_root()
    append_presence_turn(
        presence_root,
        conversation_id=conversation_id,
        direction='inbound',
        delivery_state='received',
        text=str(envelope.get('text') or ''),
        actor_role='operator' if result.get('role')=='operator' else 'public_user',
        source_message_id=incoming_provider_message_id(envelope),
        observed_at=str(envelope.get('received_at') or ((envelope.get('metadata') or {}).get('received_at')) or '') or None,
    )
    reply_text=str(((result.get('reply') or {}).get('text')) or '')
    if reply_text:
        append_presence_turn(
            presence_root,
            conversation_id=conversation_id,
            direction='outbound',
            delivery_state='sent' if sent else 'prepared',
            text=reply_text,
            actor_role='dio_presence',
            source_message_id=provider_message_id,
        )
    conv_path=presence_root/'conversations'/f'{conversation_id}.json'
    if not conv_path.exists():
        return
    conversation=read_json(conv_path)
    context=build_presence_conversation_context(presence_root,conversation)
    context_path=ROOT/'state'/'conversation_context'/f"{context['context_id']}.json"
    write_conversation_context(context_path,context)
    result['conversation_context']={
        'context_id':context['context_id'],
        'thread_state':context['thread']['state'],
        'channel':context['channel'],
        'authority':'expression_context_only',
    }

@app.get('/api/presence/health')
def health():
    return {'ok':True,'service':'dio-presence-bridge','version':'2.1.0','persona':'Vesper','legacy_codename':'Lilith','automatic_external_actions':False,'attachment_mode':'quarantine_only','public_status':'verified_binding_only','conversation_context':'expression_only'}

@app.post('/api/presence/ingress')
async def ingress(request:Request,x_dio_presence_signature:str=Header(default=''),x_dio_presence_timestamp:str=Header(default=''),x_dio_presence_nonce:str=Header(default=''),x_dio_presence_key_id:str=Header(default='')):
    body=await request.body()
    keymap={'public-edge':(os.getenv('DIO_PRESENCE_PUBLIC_SHARED_SECRET',''),'public'),'operator-edge':(os.getenv('DIO_PRESENCE_OPERATOR_SHARED_SECRET',''),'operator')}
    if x_dio_presence_key_id not in keymap: raise HTTPException(401,'Unknown presence edge key id.')
    secret,trusted_edge_role=keymap[x_dio_presence_key_id]
    if not secret: raise HTTPException(503,'Presence edge key is not configured.')
    try: verify_body(secret,x_dio_presence_timestamp,x_dio_presence_nonce,body,x_dio_presence_signature,int(CFG.get('signature_ttl_seconds',300)))
    except SignatureError as exc: raise HTTPException(401,str(exc))
    prune()
    if x_dio_presence_nonce in REPLAY: raise HTTPException(409,'Replay detected.')
    REPLAY[x_dio_presence_nonce]=time.time()
    try: envelope=json.loads(body)
    except json.JSONDecodeError: raise HTTPException(400,'Invalid JSON.')
    envelope['_trusted_edge_role']=trusted_edge_role; envelope['_trusted_edge_key_id']=x_dio_presence_key_id
    for field in ('channel','external_user_id','text'):
        if field not in envelope: raise HTTPException(422,f'Missing {field}.')
    if len(str(envelope.get('text') or ''))>int(CFG.get('max_message_chars',4000)): raise HTTPException(413,'Message too large.')
    try:
        result=process_envelope(envelope,ROOT,CFG)
        result=apply_persona_response(result,ROOT)
    except Exception as exc: raise HTTPException(400,f'Presence request blocked: {exc}')
    provider_message_id=None
    try:
        sent, error, provider_message_id = send_telegram_reply_from_core(envelope, result)
        result["core_reply_sent"] = sent
        if error:
            result["core_reply_send_error"] = error
    except Exception as exc:
        sent=False
        result["core_reply_sent"] = False
        result["core_reply_send_error"] = str(exc)[:300]
    try:
        _persist_live_context(envelope,result,sent,provider_message_id)
    except Exception as exc:
        result['conversation_context_error']=str(exc)[:300]
    return JSONResponse(result,headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

@app.get('/api/presence/needs-you')
def needs_you(authorization:str|None=Header(default=None)):
    if not bearer_ok(authorization): raise HTTPException(401,'Operator token required.')
    return {'items':list_needs_you(_presence_root(),50)}

@app.get('/api/presence/operator-summary')
def summary(authorization:str|None=Header(default=None)):
    if not bearer_ok(authorization): raise HTTPException(401,'Operator token required.')
    return operator_summary(ROOT,_presence_root())

@app.get('/api/presence/conversations')
def conversations(authorization:str|None=Header(default=None)):
    if not bearer_ok(authorization): raise HTTPException(401,'Operator token required.')
    root=_presence_root()/'conversations'; out=[]
    for p in sorted(root.glob('*.json'),key=lambda x:x.stat().st_mtime,reverse=True) if root.exists() else []:
        try:
            x=read_json(p); out.append({k:x.get(k) for k in ('conversation_id','channel','display_name','updated_at','message_count','last_intent','last_product')})
        except Exception: pass
    return {'items':out[:100]}

@app.post('/api/presence/identity-bindings')
async def bind_identity(request:Request,authorization:str|None=Header(default=None)):
    if not bearer_ok(authorization): raise HTTPException(401,'Operator token required.')
    p=await request.json(); conversation_id=str(p.get('conversation_id') or ''); order_ids=p.get('order_ids') or []; method=str(p.get('verification_method') or '')
    if not conversation_id or not isinstance(order_ids,list) or not method: raise HTTPException(422,'conversation_id, order_ids[], and verification_method are required.')
    conv=_presence_root()/'conversations'/f'{conversation_id}.json'
    if not conv.exists(): raise HTTPException(404,'Conversation not found.')
    missing=[oid for oid in order_ids if not (ROOT/'state'/'commerce'/'orders'/f'{safe(str(oid))}.json').exists()]
    if missing: raise HTTPException(422,f'Order ids not found in local commerce state: {missing}')
    binding=create_status_binding(_presence_root(),conversation_id,[str(x) for x in order_ids],method,'operator_api')
    return JSONResponse(binding,headers={'Cache-Control':'no-store'})

@app.delete('/api/presence/identity-bindings/{conversation_id}')
def revoke_identity(conversation_id:str,authorization:str|None=Header(default=None)):
    if not bearer_ok(authorization): raise HTTPException(401,'Operator token required.')
    try: return revoke_binding(_presence_root(),conversation_id)
    except Exception as exc: raise HTTPException(404,str(exc))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--host',default='127.0.0.1'); ap.add_argument('--port',type=int,default=8787); args=ap.parse_args()
    if args.host not in {'127.0.0.1','localhost','::1'} and os.getenv('DIO_PRESENCE_ALLOW_NONLOCAL')!='1': raise SystemExit('Non-local bind refused. Set DIO_PRESENCE_ALLOW_NONLOCAL=1 only behind a trusted reverse proxy.')
    uvicorn.run(app,host=args.host,port=args.port,log_level='info')
if __name__=='__main__': main()
