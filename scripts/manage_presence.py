#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from presence_core.config import load_config
from presence_core.identity import create_status_binding, revoke_binding
from presence_core.state import list_needs_you, operator_summary, read_json

def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True)
    sub.add_parser('needs-you')
    sub.add_parser('summary')
    ls=sub.add_parser('conversations'); ls.add_argument('--limit',type=int,default=30)
    b=sub.add_parser('bind-status'); b.add_argument('--conversation',required=True); b.add_argument('--order',action='append',required=True); b.add_argument('--method',required=True,help='How the operator verified the person/order relationship.')
    r=sub.add_parser('revoke-binding'); r.add_argument('--conversation',required=True)
    args=ap.parse_args(); cfg=load_config(); pr=ROOT/cfg.get('state_root','state/presence')
    if args.cmd=='needs-you': print(json.dumps({'items':list_needs_you(pr,50)},indent=2)); return
    if args.cmd=='summary': print(json.dumps(operator_summary(ROOT,pr),indent=2)); return
    if args.cmd=='conversations':
        items=[]; d=pr/'conversations'
        for p in sorted(d.glob('*.json'),key=lambda x:x.stat().st_mtime,reverse=True) if d.exists() else []:
            x=read_json(p); items.append({k:x.get(k) for k in ('conversation_id','channel','display_name','updated_at','message_count','last_intent','last_product')})
        print(json.dumps({'items':items[:args.limit]},indent=2)); return
    if args.cmd=='bind-status':
        for oid in args.order:
            if not (ROOT/'state'/'commerce'/'orders'/f'{oid}.json').exists(): raise SystemExit(f'Order not found in DIO local commerce state: {oid}')
        print(json.dumps(create_status_binding(pr,args.conversation,args.order,args.method,'operator_cli'),indent=2)); return
    if args.cmd=='revoke-binding': print(json.dumps(revoke_binding(pr,args.conversation),indent=2))
if __name__=='__main__': main()
