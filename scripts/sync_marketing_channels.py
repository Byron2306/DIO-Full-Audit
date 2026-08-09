#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
_ROOT_BOOT = Path(__file__).resolve().parents[1]
if str(_ROOT_BOOT) not in sys.path:
    sys.path.insert(0, str(_ROOT_BOOT))
import argparse, json
from datetime import date, timedelta
from market_command.intelligence import IntelligenceStore
from market_command.channel_sync import sync_channel

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/"state"/"market_command"/"market_command.sqlite"
EVENTS=ROOT/"telemetry"/"dio_events.jsonl"


def main():
    ap=argparse.ArgumentParser(description="Read-only sync from an approved marketing platform into DIO Market Command")
    ap.add_argument("channel", choices=["META_ADS","FACEBOOK_PAGE","INSTAGRAM_ORGANIC","GOOGLE_ADS","REDDIT_ADS","TIKTOK_ADS","LINKEDIN_ORGANIC","YOUTUBE_ORGANIC"])
    ap.add_argument("--start-date")
    ap.add_argument("--end-date")
    args=ap.parse_args()
    end=args.end_date or date.today().isoformat()
    start=args.start_date or (date.today()-timedelta(days=7)).isoformat()
    result=sync_channel(IntelligenceStore(DB,EVENTS),args.channel,start,end)
    print(json.dumps(result,indent=2,ensure_ascii=True))

if __name__=="__main__": main()
