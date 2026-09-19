#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
import uvicorn
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from presence_core.config import load_config, state_path
from presence_core.authority import (
    bind_external_action_receipt,
    telegram_reply_switch_enabled,
)
from presence_core.engine import process_envelope
from presence_core.identity import create_status_binding, revoke_binding
from presence_core.fulfilment_release import record_successful_delivery
from presence_core.local_ingress import LocalIngressLedger
from presence_core.signing import verify_body, SignatureError
from presence_core.state import list_needs_you, operator_summary, read_json, safe
from presence_core.telegram_transport import send_telegram_reply, telegram_voice_reply_switch_enabled


def finalize_fulfilment_delivery(
    state_root: Path,
    *,
    result: dict,
    sent: bool,
    reply_receipt: dict,
):
    if not sent:
        return None

    artifact = result.get("outbound_artifact") or {}

    if (
        str(artifact.get("purpose") or "").strip().lower()
        != "product_fulfilment"
    ):
        return None

    authority_id = str(
        artifact.get("release_authority_id") or ""
    ).strip()

    if not authority_id:
        return None

    if (
        str(reply_receipt.get("delivery_mode") or "").strip().lower()
        != "document"
    ):
        return None

    document = reply_receipt.get("document") or {}

    delivered_sha = str(
        document.get("sha256") or ""
    ).strip().lower()

    expected_sha = str(
        artifact.get("sha256") or ""
    ).strip().lower()

    if not delivered_sha or delivered_sha != expected_sha:
        raise ValueError(
            "Telegram delivery receipt SHA-256 "
            "does not match outbound fulfilment artifact"
        )

    return record_successful_delivery(
        Path(state_root),
        authority_id,
        delivery_receipt={
            "channel": "telegram",
            "message_id": document.get(
                "telegram_message_id"
            ),
            "file_id": document.get(
                "telegram_file_id"
            ),
            "artifact_sha256": delivered_sha,
        },
    )



def send_bind_and_finalize(
    envelope: dict,
    result: dict,
    *,
    state_root: Path,
) -> tuple[bool, str | None, dict]:
    sent, error, reply_receipt = (
        send_telegram_reply_from_core(
            envelope,
            result,
        )
    )

    bind_external_action_receipt(
        result,
        reply_receipt,
        sent=sent,
        error=error,
    )

    try:
        finalize_fulfilment_delivery(
            Path(state_root),
            result=result,
            sent=sent,
            reply_receipt=reply_receipt,
        )
    except Exception as exc:
        if sent:
            result["fulfilment_completion_state"] = (
                "post_send_reconciliation_failed"
            )
            result["fulfilment_completion_error"] = str(exc)[:500]
        else:
            raise

    return sent, error, reply_receipt


app=FastAPI(title='DIO Presence Bridge',version='2.0.0',docs_url=None,redoc_url=None)
CFG=load_config(); REPLAY:dict[str,float]={}

def bearer_ok(auth:str|None)->bool:
    token=os.getenv('DIO_PRESENCE_OPERATOR_TOKEN','')
    return bool(token and auth==f'Bearer {token}')

def prune():
    cutoff=time.time()-600
    for k,v in list(REPLAY.items()):
        if v<cutoff: REPLAY.pop(k,None)

def core_telegram_replies_enabled() -> bool:
    return telegram_reply_switch_enabled()

def send_telegram_reply_from_core(
    envelope: dict,
    result: dict,
) -> tuple[bool, str | None, dict]:
    return send_telegram_reply(
        envelope,
        result,
        root=ROOT,
        state_root=ROOT/CFG.get('state_root','state/presence'),
    )

@app.get('/api/presence/health')
def health():
    return {
        'ok': True,
        'service': 'dio-presence-bridge',
        'version': '2.0.0',
        'presence_identity': 'Vesper',
        'automatic_external_actions': False,
        'telegram_reply_switch_enabled': core_telegram_replies_enabled(),
        'telegram_voice_reply_switch_enabled': telegram_voice_reply_switch_enabled(),
        'telegram_reply_authority': 'explicit_environment_gate',
        'telegram_voice_renderer': 'vera_pocket_public',
        'attachment_mode': 'quarantine_only',
        'public_status': 'verified_binding_only',
    }

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
    event_key=str(((envelope.get('metadata') or {}).get('provider_event_key')) or '').strip()
    ledger=LocalIngressLedger(ROOT/CFG.get('state_root','state/presence')/'local_ingress.sqlite')
    if event_key:
        try:
            cached=ledger.cached_response(event_key,body)
        except ValueError as exc:
            raise HTTPException(409,str(exc))
        if cached is not None:
            return JSONResponse(
                cached,
                headers={
                    'Cache-Control':'no-store',
                    'X-Content-Type-Options':'nosniff',
                    'X-DIO-Idempotent-Replay':'1',
                },
            )
        try:
            ledger.begin(event_key,body)
        except ValueError as exc:
            raise HTTPException(409,str(exc))
    envelope['_trusted_edge_role']=trusted_edge_role; envelope['_trusted_edge_key_id']=x_dio_presence_key_id
    for field in ('channel','external_user_id','text'):
        if field not in envelope: raise HTTPException(422,f'Missing {field}.')
    if len(str(envelope.get('text') or ''))>int(CFG.get('max_message_chars',4000)): raise HTTPException(413,'Message too large.')
    try: result=process_envelope(envelope,ROOT,CFG)
    except Exception as exc: raise HTTPException(400,f'Presence request blocked: {exc}')
    try:
        sent, error, reply_receipt = send_bind_and_finalize(
            envelope,
            result,
            state_root=ROOT / CFG.get(
                "state_root",
                "state/presence",
            ),
        )
    except Exception as exc:
        bind_external_action_receipt(
            result,
            {
                "schema": "dio.vesper.external_reply_authority.v1",
                "identity": {"name": "Vesper", "role": "DIO Presence Core"},
                "authorized": False,
                "channel": envelope.get("channel"),
                "intent": ((result.get("decision") or {}).get("intent")),
                "reasons": ["external_reply_exception"],
                "external_action_type": "telegram_reply",
            },
            sent=False,
            error=str(exc),
        )
    if event_key:
        ledger.complete(event_key,body,result)
    return JSONResponse(result,headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

@app.get('/api/presence/needs-you')
def needs_you(authorization:str|None=Header(default=None)):
    if not bearer_ok(authorization): raise HTTPException(401,'Operator token required.')
    return {'items':list_needs_you(ROOT/CFG.get('state_root','state/presence'),50)}

@app.get('/api/presence/operator-summary')
def summary(authorization:str|None=Header(default=None)):
    if not bearer_ok(authorization): raise HTTPException(401,'Operator token required.')
    return operator_summary(ROOT,ROOT/CFG.get('state_root','state/presence'))

@app.get('/api/presence/conversations')
def conversations(authorization:str|None=Header(default=None)):
    if not bearer_ok(authorization): raise HTTPException(401,'Operator token required.')
    root=ROOT/CFG.get('state_root','state/presence')/'conversations'; out=[]
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
    conv=ROOT/CFG.get('state_root','state/presence')/'conversations'/f'{conversation_id}.json'
    if not conv.exists(): raise HTTPException(404,'Conversation not found.')
    missing=[oid for oid in order_ids if not state_path('commerce', 'orders', f'{safe(str(oid))}.json', dio_root=ROOT).exists()]
    if missing: raise HTTPException(422,f'Order ids not found in local commerce state: {missing}')
    binding=create_status_binding(ROOT/CFG.get('state_root','state/presence'),conversation_id,[str(x) for x in order_ids],method,'operator_api')
    return JSONResponse(binding,headers={'Cache-Control':'no-store'})

@app.delete('/api/presence/identity-bindings/{conversation_id}')
def revoke_identity(conversation_id:str,authorization:str|None=Header(default=None)):
    if not bearer_ok(authorization): raise HTTPException(401,'Operator token required.')
    try: return revoke_binding(ROOT/CFG.get('state_root','state/presence'),conversation_id)
    except Exception as exc: raise HTTPException(404,str(exc))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--host',default='127.0.0.1'); ap.add_argument('--port',type=int,default=8787); args=ap.parse_args()
    if args.host not in {'127.0.0.1','localhost','::1'} and os.getenv('DIO_PRESENCE_ALLOW_NONLOCAL')!='1': raise SystemExit('Non-local bind refused. Set DIO_PRESENCE_ALLOW_NONLOCAL=1 only behind a trusted reverse proxy.')
    uvicorn.run(app,host=args.host,port=args.port,log_level='info')
if __name__=='__main__': main()
