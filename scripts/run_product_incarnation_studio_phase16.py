from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from products.incarnation_studio_gauntlet import run_gauntlet
from products.incarnation_studio import ACCEPTANCE_TOKEN

def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,default=Path("state/incarnation_studio/phase16"))
    r=run_gauntlet(output_dir=p.parse_args().output)
    keys=("engine_count","full_corpus_binding","truthful_invocation_semantics","deterministic_generation","responsive_marketfront","local_attachment_intake","nichefoundry_positioning","market_command_campaign","document_studio_assets","sophia_claim_boundary","homs_customer_education","evidex_proof_binding","vesper_fulfilment_binding","outlook_draft_boundary","presence_release_package","commercial_measurement_contract","tamper_detection","external_publication","external_send","media_spend","payment")
    print(json.dumps({k:r[k] for k in keys},indent=2,sort_keys=True));print(ACCEPTANCE_TOKEN);return 0
if __name__=="__main__":raise SystemExit(main())
