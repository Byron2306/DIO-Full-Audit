from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from products.regulated_markets_gauntlet import ACCEPTANCE_TOKEN, run_gauntlet

def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,default=Path("state/regulated_markets/phase14"))
    r=run_gauntlet(output_dir=p.parse_args().output)
    print(json.dumps({k:r[k] for k in ("incarnation_count","profile_registry_binding","capability_registry_binding","deterministic_execution","source_authority_lattice","temporal_change_detection","applicability_uncertainty","draft_filing_boundary","ai_trust_binding","external_release")},indent=2,sort_keys=True))
    print(ACCEPTANCE_TOKEN);return 0
if __name__=="__main__":raise SystemExit(main())
