#!/usr/bin/env python3
from __future__ import annotations
import json, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from presence_core.config import load_config
from presence_core.engine import process_envelope

def main():
    os.environ.setdefault('DIO_PRESENCE_PUBLIC_SHARED_SECRET','DEMO-ONLY-CHANGE-ME-0123456789-ABCDEFGHIJ')
    cfg=load_config(); env={"schema":"dio.presence_ingress.v1","channel":"telegram","external_user_id":"demo-public-user","display_name":"Demo User","source_message_id":"demo-1","message_type":"text","text":"I need a Grade 8 History lesson plan and worksheet in Afrikaans using HOMS"}
    print(json.dumps(process_envelope(env,ROOT,cfg),indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
