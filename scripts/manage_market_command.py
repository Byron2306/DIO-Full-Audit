#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
_ROOT_BOOT = Path(__file__).resolve().parents[1]
if str(_ROOT_BOOT) not in sys.path:
    sys.path.insert(0, str(_ROOT_BOOT))
import argparse, json
from pathlib import Path
from market_command.catalog import load_catalogs, load_json
from market_command.core import MarketStore
from market_command.agency import prepare_agency_rfq

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/"config"/"market_command.json"
DB=ROOT/"state"/"market_command"/"market_command.sqlite"
EVENTS=ROOT/"telemetry"/"dio_events.jsonl"

def store(): return MarketStore(DB,EVENTS,load_json(CONFIG))

def payload(path): return json.loads(Path(path).read_text(encoding="utf-8"))

def main():
    p=argparse.ArgumentParser(description="DIO Market Command CLI")
    sub=p.add_subparsers(dest="cmd",required=True)
    sub.add_parser("state")
    c=sub.add_parser("create-campaign"); c.add_argument("spec")
    a=sub.add_parser("approve-campaign"); a.add_argument("campaign_id")
    x=sub.add_parser("activate-campaign"); x.add_argument("campaign_id")
    m=sub.add_parser("measure"); m.add_argument("campaign_id"); m.add_argument("metrics")
    s=sub.add_parser("settle"); s.add_argument("campaign_id")
    b=sub.add_parser("create-media-buy"); b.add_argument("spec")
    ab=sub.add_parser("approve-media-buy"); ab.add_argument("media_buy_id")
    q=sub.add_parser("record-media-quote"); q.add_argument("media_buy_id"); q.add_argument("quote_minor",type=int); q.add_argument("quote_reference"); q.add_argument("--approved-cap-minor",type=int,default=0)
    rfq=sub.add_parser("prepare-agency-rfq"); rfq.add_argument("campaign_id"); rfq.add_argument("agency_id"); rfq.add_argument("--placement",default=""); rfq.add_argument("--route-confirmed",action="store_true")
    pol=sub.add_parser("policy"); pol.add_argument("key"); pol.add_argument("value")
    args=p.parse_args(); st=store(); catalogs=load_catalogs(ROOT)
    if args.cmd=="state": out=st.state(catalogs)
    elif args.cmd=="create-campaign": out=st.create_campaign(payload(args.spec))
    elif args.cmd=="approve-campaign": out=st.approve_campaign(args.campaign_id,True)
    elif args.cmd=="activate-campaign": out=st.activate_campaign(args.campaign_id,True)
    elif args.cmd=="measure": out=st.record_measurement(args.campaign_id,payload(args.metrics))
    elif args.cmd=="settle": out=st.settle_campaign(args.campaign_id,True)
    elif args.cmd=="create-media-buy": out=st.create_media_buy(payload(args.spec))
    elif args.cmd=="approve-media-buy": out=st.approve_media_buy(args.media_buy_id,True)
    elif args.cmd=="record-media-quote": out=st.record_media_quote(args.media_buy_id,args.quote_minor,args.quote_reference,args.approved_cap_minor)
    elif args.cmd=="prepare-agency-rfq": out=prepare_agency_rfq(ROOT,st,args.campaign_id,args.agency_id,args.placement,"DIO operator via CLI",args.route_confirmed)
    else: out=st.set_policy(args.key,args.value)
    print(json.dumps(out,indent=2))
if __name__=="__main__": main()
