#!/usr/bin/env python3
"""Project independent readiness verdicts from the current 68-product proof index."""
from __future__ import annotations
import argparse,csv,hashlib,json,zipfile
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT/'deliverables/product_proof_portfolio_20261104.zip'

def read_index(path:Path)->dict:
    with zipfile.ZipFile(path) as archive:
        matches=[n for n in archive.namelist() if n.endswith('/PRODUCT_PROOF_INDEX.json')]
        if len(matches)!=1: raise ValueError('expected exactly one product proof index in portfolio ZIP')
        return json.loads(archive.read(matches[0]))

def verdict(row:dict)->dict:
    route=str(row.get('route_status') or '').upper()
    execution='PASS' if route=='PASS_FULL_PIPELINE' else ('FAIL' if route.startswith(('FAIL','ERROR')) else 'UNVERIFIED')
    signoff=bool(row.get('independent_professional_signoff'))
    output_quality='PASS' if signoff else 'UNVERIFIED'
    acceptance=str(row.get('buyer_acceptance') or '').upper()
    customer='PASS' if acceptance in {'ESTABLISHED','PROVED','PROVEN'} else ('FAIL' if acceptance in {'REJECTED','FAILED'} else 'UNVERIFIED')
    release='PASS' if bool(row.get('release_authorized')) else 'HELD'
    evidence='UNVERIFIED'
    if row.get('product_evidence') and row.get('artifact_sha256') and row.get('artifact_bytes'):
        evidence='TRACEABLE_UNVALIDATED'
    return {
      'product_id':row['product_id'],'name':row['name'],
      'execution':{'verdict':execution,'evidence':row.get('route_status')},
      'output_quality':{'verdict':output_quality,'evidence':'independent_professional_signoff' if signoff else 'no_independent_quality_signoff_recorded'},
      'evidence_validity':{'verdict':evidence,'evidence':'hash-bound artifact/receipt where available; semantic correctness not independently validated'},
      'customer_acceptance':{'verdict':customer,'evidence':acceptance or 'NOT_ESTABLISHED'},
      'release':{'verdict':release,'evidence':'release_authorized' if release=='PASS' else 'release authorization absent'},
      'professional_readiness':'READY' if all(x=='PASS' for x in (execution,output_quality,evidence,customer,release)) else 'NOT_ESTABLISHED',
      'limitations':list(row.get('quality_limits') or []),
      'source_artifact':row.get('source_artifact'),'artifact_sha256':row.get('artifact_sha256'),
      'product_evidence':row.get('product_evidence'),
    }

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--portfolio-zip',type=Path,default=DEFAULT); ap.add_argument('--out',type=Path,default=ROOT/'deliverables/product_readiness_verdicts_20261104'); a=ap.parse_args()
    index=read_index(a.portfolio_zip); rows=[verdict(r) for r in index['products']]
    if len(rows)!=68: raise ValueError(f'expected 68 products, got {len(rows)}')
    counts={key:{} for key in ('execution','output_quality','evidence_validity','customer_acceptance','release','professional_readiness')}
    for row in rows:
        for key in counts:
            value=row[key] if key=='professional_readiness' else row[key]['verdict']
            counts[key][value]=counts[key].get(value,0)+1
    a.out.mkdir(parents=True,exist_ok=True)
    report={'schema':'dio.product_readiness_verdicts.v1','generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'qualification_snapshot_sha256':index.get('qualification_snapshot_sha256'),'method':'Execution, output quality, evidence validity, customer acceptance and release are independent verdicts. A route PASS never promotes another dimension. TRACEABLE_UNVALIDATED means byte lineage exists, not that the interpretation is correct.','summary':counts,'products':rows}
    (a.out/'PRODUCT_READINESS_VERDICTS.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    fields=['product_id','name','execution','output_quality','evidence_validity','customer_acceptance','release','professional_readiness','source_artifact','artifact_sha256']
    with (a.out/'PRODUCT_READINESS_VERDICTS.csv').open('w',newline='',encoding='utf-8-sig') as f:
      w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
      for r in rows:w.writerow({**{k:r[k] for k in ('product_id','name','professional_readiness','source_artifact','artifact_sha256')},**{k:r[k]['verdict'] for k in ('execution','output_quality','evidence_validity','customer_acceptance','release')}})
    (a.out/'README.md').write_text('# Product readiness verdicts\n\nThis report separates execution, output quality, evidence validity, customer acceptance, and release. Hash-bound traceability alone never proves semantic correctness. `UNVERIFIED` and `HELD` are explicit states, not implied passes.\n\nThese verdicts are independently sourced from the curated product proof index and do not convert pipeline receipts into professional approval. `TRACEABLE_UNVALIDATED` means there is a byte-linked artifact/receipt; no independent semantic correctness review is recorded.\n')
    return 0
if __name__=='__main__': raise SystemExit(main())
