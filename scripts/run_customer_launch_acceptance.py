#!/usr/bin/env python3
"""Render synthetic source-bound launch kits; no external publication."""
from __future__ import annotations
import argparse,copy,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from products.customer_product_router import run_customer_product
ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    base=ROOT/'config/customer_products/examples'
    normal=json.loads((base/'launch.json').read_text());unseen=json.loads((base/'launch_unseen.json').read_text())
    messy=copy.deepcopy(normal)
    messy['approved_claims'].append({'text':'Guaranteed employment for every participant.','source_id':'BRIEF','quote':'Not actually supplied','approved_by':'Unverified asserted owner'})
    args.out.mkdir(parents=True,exist_ok=True);summary={'synthetic_acceptance_not_customer_evidence':True,'cases':[]}
    for variant,p in [('baseline',normal),('messy-adversarial',messy),('unseen',unseen)]:
        p['brand']['asset_path']=str(base/p['brand']['asset_path'])
        result=run_customer_product('Launch Studio',p,args.out/variant)
        for artifact in result['artifacts']:
            if hashlib.sha256((Path(result['output_dir'])/artifact['path']).read_bytes()).hexdigest()!=artifact['sha256']:raise RuntimeError('hash mismatch')
        receipt=result['receipt']
        summary['cases'].append({'variant':variant,'creative_assets':receipt['creative_assets'],'held_claims':receipt['held_claims'],'qa':receipt['qa'],'release':receipt['release'],'output_dir':result['output_dir']})
    (args.out/'ACCEPTANCE_SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({'cases':len(summary['cases']),'out':str(args.out)},indent=2))


if __name__=='__main__':main()
