from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from products.self_expanding_factory_gauntlet import ACCEPTANCE_TOKEN,run_gauntlet

def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,default=Path("state/factory/phase15"))
    r=run_gauntlet(output_dir=p.parse_args().output)
    print(json.dumps({k:r[k] for k in ("reference_product","generated_product_count","generated_profile_count","declarative_materialisation","deterministic_materialisation","canonical_compiler_binding","profile_registry_generation","capability_registry_generation","validation_contract_generation","goldeneye_registration_generation","deterministic_execution","tamper_detection","maturity_promotion_refusal","path_escape_refusal","unearned_capability_refusal","external_release")},indent=2,sort_keys=True))
    print(ACCEPTANCE_TOKEN);return 0
if __name__=="__main__":raise SystemExit(main())
