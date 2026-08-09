#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
_ROOT_BOOT = Path(__file__).resolve().parents[1]
if str(_ROOT_BOOT) not in sys.path:
    sys.path.insert(0, str(_ROOT_BOOT))
import argparse,json
from pathlib import Path
from market_command.catalog import load_catalogs,load_json
from market_command.core import MarketStore
from market_command.procurement import build_media_brief

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/"state"/"market_command"/"market_command.sqlite"
EVENTS=ROOT/"telemetry"/"dio_events.jsonl"
CONFIG=ROOT/"config"/"market_command.json"

def main():
    ap=argparse.ArgumentParser(description="Export a governed request-for-quote brief for a South African publisher/agency")
    ap.add_argument("campaign_id")
    ap.add_argument("vendor_id")
    ap.add_argument("--placement",default="")
    args=ap.parse_args()
    campaign=MarketStore(DB,EVENTS,load_json(CONFIG)).get_campaign(args.campaign_id)
    catalogs=load_catalogs(ROOT)
    vendor=next((v for v in catalogs["sa_media"]["vendors"] if v["id"]==args.vendor_id),None)
    if not vendor:
        vendor=next((v for v in catalogs["agencies"]["partners"] if v["id"]==args.vendor_id),None)
    if not vendor: raise SystemExit(f"Unknown vendor_id: {args.vendor_id}")
    print(json.dumps(build_media_brief(ROOT,campaign,vendor,args.placement),indent=2))
if __name__=="__main__": main()
