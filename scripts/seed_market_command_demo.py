#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
_ROOT_BOOT = Path(__file__).resolve().parents[1]
if str(_ROOT_BOOT) not in sys.path:
    sys.path.insert(0, str(_ROOT_BOOT))
import json
from pathlib import Path
from market_command.catalog import load_json
from market_command.core import MarketStore
from market_command.intelligence import IntelligenceStore

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/"state"/"market_command"/"market_command.sqlite"
EVENTS=ROOT/"telemetry"/"dio_events.jsonl"
CONFIG=ROOT/"config"/"market_command.json"

def main():
    st=MarketStore(DB,EVENTS,load_json(CONFIG)); intel=IntelligenceStore(DB,EVENTS)
    # All seeded objects are explicitly simulated and have zero approved spend.
    campaigns=[
        ("HOMS_ASSESS","HOMS proof-led founder post","LINKEDIN_ORGANIC","South African academic leaders"),
        ("EVIDEX_PACK","Evidex evidence-mess explainer","FACEBOOK_PAGE","NGO and programme teams"),
        ("SOPHIA_REVIEW","Sophia research-integrity explainer","REDDIT_ORGANIC","Postgraduate research communities"),
    ]
    created=[]
    for product,name,channel,audience in campaigns:
        c=st.create_campaign({"product_line_id":product,"name":"[SIMULATED] "+name,"audience":audience,"channel_id":channel,"objective":"qualified_pilot_conversation","creative_brief":"Controlled demo object. Do not publish as a factual market result."})
        created.append(c)
    c0=created[0]
    intel.record_snapshot({"channel_id":"LINKEDIN_ORGANIC","campaign_id":c0["campaign_id"],"impressions":1800,"clicks":54,"spend_minor":0,"source_mode":"manual_import","evidence_grade":"estimated","raw":{"simulated":True}})
    intel.record_attribution({"campaign_id":c0["campaign_id"],"channel_id":"LINKEDIN_ORGANIC","lead_id":"LEAD-SIM-1","event_type":"lead.qualified","source":"simulated_demo","metadata":{"simulated":True}})
    intel.bind_role({"prospect_id":"PR-SIM","organisation":"Example Education Network","product_line_id":"HOMS_ASSESS","buyer_unit":"Academic","role_title":"Head of Academics","person_name":"Example Person","source":"manual","confidence":"unverified","outreach_permission":"not_recorded","notes":"SIMULATED DEMO ONLY"})
    print(json.dumps({"simulated":True,"campaign_ids":[c["campaign_id"] for c in created],"message":"Demo state seeded. No spend, publication, outreach or real commercial claim was created."},indent=2))
if __name__=="__main__": main()
