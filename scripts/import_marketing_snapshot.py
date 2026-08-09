#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
_ROOT_BOOT = Path(__file__).resolve().parents[1]
if str(_ROOT_BOOT) not in sys.path:
    sys.path.insert(0, str(_ROOT_BOOT))
import argparse,json
from pathlib import Path
from market_command.intelligence import IntelligenceStore

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/"state"/"market_command"/"market_command.sqlite"
EVENTS=ROOT/"telemetry"/"dio_events.jsonl"

def main():
    ap=argparse.ArgumentParser(description="Import a normalized manual/platform marketing snapshot")
    ap.add_argument("json_file",type=Path)
    args=ap.parse_args()
    payload=json.loads(args.json_file.read_text(encoding="utf-8"))
    result=IntelligenceStore(DB,EVENTS).record_snapshot(payload)
    print(json.dumps(result,indent=2,ensure_ascii=True))
if __name__=="__main__": main()
